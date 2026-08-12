"""Customer-readiness feature tests."""
import io
import shutil

import pytest

from legaldocuman.app import create_app
from legaldocuman.app.extensions import db
from legaldocuman.app.models import AuditEvent, Document, Tenant, User, UserRole
from legaldocuman.config import Config


def _write_minimal_pdf(path):
    """Write a synthetic scanned-style PDF with a raster image XObject."""
    import zlib

    width, height = 600, 220
    pixels = bytearray([255] * width * height * 3)
    # Draw simple black bars to mimic scanned text lines without relying on PIL.
    for y in [50, 56, 92, 98, 134]:
        for x in range(30, 520):
            pos = (y * width + x) * 3
            pixels[pos:pos + 3] = b"\x00\x00\x00"
    compressed = zlib.compress(bytes(pixels))
    contents = b"q 500 0 0 183 56 520 cm /Im0 Do Q"

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>",
        (f"<< /Type /XObject /Subtype /Image /Width {width} /Height {height} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode /Length {len(compressed)} >>".encode()
         + b"\nstream\n" + compressed + b"\nendstream"),
        f"<< /Length {len(contents)} >>\nstream\n".encode() + contents + b"\nendstream",
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{idx} 0 obj\n".encode())
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref_at = len(pdf)
    pdf.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(f"trailer << /Root 1 0 R /Size {len(objects)+1} >>\nstartxref\n{xref_at}\n%%EOF\n".encode())
    path.write_bytes(bytes(pdf))


def _app(tmp_path, monkeypatch, **env):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'readiness.db'}")
    monkeypatch.setenv("UPLOAD_FOLDER", str(tmp_path / "uploads"))
    monkeypatch.setenv("PROCESSED_FOLDER", str(tmp_path / "processed"))
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("JOB_BACKEND", env.pop("JOB_BACKEND", "sync"))
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "password123")
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    Config._instance = None
    app = create_app()
    app.config.update(TESTING=True)
    return app


def _login(client):
    response = client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "password123"})
    assert response.status_code == 200
    return response.get_json()["token"]


def test_user_login_rbac_review_and_audit_flow(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    client = app.test_client()
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    upload = client.post(
        "/api/v1/upload",
        headers=headers,
        data={"file": (io.BytesIO(b"Acme NDA digitally signed by Jane Doe"), "Acme_NDA.txt")},
        content_type="multipart/form-data",
    )
    assert upload.status_code == 201
    doc_id = upload.get_json()["id"]

    patch = client.patch(
        f"/api/v1/documents/{doc_id}",
        headers=headers,
        json={"vendor": "Acme Legal", "review_notes": "Verified by reviewer", "mark_reviewed": True},
    )
    assert patch.status_code == 200
    body = patch.get_json()
    assert body["vendor"] == "Acme Legal"
    assert body["review_status"] == "reviewed"

    audit = client.get(f"/api/v1/documents/{doc_id}/audit", headers=headers)
    assert audit.status_code == 200
    actions = [event["action"] for event in audit.get_json()["events"]]
    assert "document.upload" in actions
    assert "document.update" in actions

    with app.app_context():
        assert AuditEvent.query.filter_by(document_id=doc_id).count() >= 2


def test_tenant_isolation_between_users(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    client = app.test_client()
    admin_token = _login(client)

    with app.app_context():
        tenant = Tenant(name="Other Tenant", slug="other")
        db.session.add(tenant)
        db.session.flush()
        user = User(tenant_id=tenant.id, email="other@example.com", name="Other", role=UserRole.REVIEWER)
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()

    other_login = client.post("/api/v1/auth/login", json={"email": "other@example.com", "password": "password123"})
    other_token = other_login.get_json()["token"]

    upload = client.post(
        "/api/v1/upload",
        headers={"Authorization": f"Bearer {admin_token}"},
        data={"file": (io.BytesIO(b"Tenant one MSA signed"), "TenantOne_MSA.txt")},
        content_type="multipart/form-data",
    )
    doc_id = upload.get_json()["id"]

    denied = client.get(f"/api/v1/documents/{doc_id}", headers={"Authorization": f"Bearer {other_token}"})
    assert denied.status_code == 404


def test_eicar_upload_is_rejected_by_builtin_malware_scanner(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    client = app.test_client()
    token = _login(client)
    eicar = b"contains EICAR-STANDARD-ANTIVIRUS-TEST-FILE marker"
    response = client.post(
        "/api/v1/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"file": (io.BytesIO(eicar), "eicar.txt")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert response.get_json()["scan_status"] == "infected"


def test_scanned_pdf_fixture_can_be_generated(tmp_path):
    pdf_path = tmp_path / "scanned-acme-msa.pdf"
    _write_minimal_pdf(pdf_path)
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract is not installed")
def test_scanned_pdf_fixture_ocr_smoke(tmp_path):
    from legaldocuman.extractors import TextExtractor

    pdf_path = tmp_path / "scanned-acme-msa.pdf"
    _write_minimal_pdf(pdf_path)
    text = TextExtractor().extract_text(str(pdf_path))
    assert text is not None
