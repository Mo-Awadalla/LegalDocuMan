import io

import pytest

from legaldocuman.app import create_app
from legaldocuman.app.extensions import db
from legaldocuman.app.models import Document, ReviewStatus, Tenant, User, UserRole
from legaldocuman.config import Config


def _app(tmp_path, monkeypatch, **env):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'saas.db'}")
    monkeypatch.setenv("UPLOAD_FOLDER", str(tmp_path / "uploads"))
    monkeypatch.setenv("PROCESSED_FOLDER", str(tmp_path / "processed"))
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("JOB_BACKEND", "sync")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "password123")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    for key, value in env.items():
        monkeypatch.setenv(key, str(value))
    Config._instance = None
    app = create_app()
    app.config.update(TESTING=True)
    return app


def _login(client, email="admin@example.com", password="password123"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["token"]


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _upload(client, token, name="Acme_NDA.txt", body=b"Acme NDA digitally signed by Jane Doe"):
    response = client.post(
        "/api/v1/upload",
        headers=_headers(token),
        data={"file": (io.BytesIO(body), name)},
        content_type="multipart/form-data",
    )
    assert response.status_code == 201, response.get_data(as_text=True)
    return response.get_json()["id"]


def test_production_config_validation_rejects_unsafe_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'prod.db'}")
    monkeypatch.setenv("SECRET_KEY", "dev-key-change-in-production")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "change-me-in-production")
    monkeypatch.setenv("AUTO_CREATE_DB", "1")
    monkeypatch.setenv("CORS_ORIGINS", "")
    Config._instance = None
    with pytest.raises(RuntimeError) as exc:
        create_app()
    assert "Invalid production configuration" in str(exc.value)
    assert "SQLite" in str(exc.value)
    assert "SECRET_KEY" in str(exc.value)


def test_health_ready_and_public_config(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch, MAX_UPLOAD_MB="7")
    client = app.test_client()
    assert client.get("/healthz").status_code == 200
    ready = client.get("/readyz")
    assert ready.status_code == 200
    public = client.get("/api/v1/config/public")
    assert public.status_code == 200
    assert public.get_json()["max_upload_mb"] == 7
    assert ".pdf" in public.get_json()["allowed_extensions"]


def test_tenant_and_user_admin_apis_are_tenant_scoped(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    client = app.test_client()
    token = _login(client)

    tenant = client.patch("/api/v1/tenant", headers=_headers(token), json={"name": "Acme Legal", "slug": "acme"})
    assert tenant.status_code == 200
    assert tenant.get_json()["name"] == "Acme Legal"

    short = client.post("/api/v1/users", headers=_headers(token), json={"email": "short@example.com", "password": "short"})
    assert short.status_code == 400

    created = client.post("/api/v1/users", headers=_headers(token), json={"email": "reviewer@example.com", "password": "password123", "role": "reviewer"})
    assert created.status_code == 201
    user_id = created.get_json()["id"]
    users = client.get("/api/v1/users", headers=_headers(token)).get_json()["users"]
    assert {u["email"] for u in users} == {"admin@example.com", "reviewer@example.com"}

    patched = client.patch(f"/api/v1/users/{user_id}", headers=_headers(token), json={"name": "Reviewer One", "role": "user"})
    assert patched.status_code == 200
    assert patched.get_json()["role"] == "user"
    deactivated = client.post(f"/api/v1/users/{user_id}/deactivate", headers=_headers(token))
    assert deactivated.status_code == 200
    assert deactivated.get_json()["is_active"] is False

    with app.app_context():
        other_tenant = Tenant(name="Other", slug="other")
        db.session.add(other_tenant)
        db.session.flush()
        other = User(tenant_id=other_tenant.id, email="other@example.com", name="Other", role=UserRole.USER)
        other.set_password("password123")
        db.session.add(other)
        db.session.commit()
        other_id = other.id
    assert client.patch(f"/api/v1/users/{other_id}", headers=_headers(token), json={"name": "Nope"}).status_code == 404
    duplicate_slug = client.patch("/api/v1/tenant", headers=_headers(token), json={"slug": "other"})
    assert duplicate_slug.status_code == 409


def test_document_validation_review_queue_and_export(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    client = app.test_client()
    token = _login(client)
    doc_id = _upload(client, token)

    invalid_date = client.patch(f"/api/v1/documents/{doc_id}", headers=_headers(token), json={"effective_date": "not-a-date"})
    assert invalid_date.status_code == 400
    invalid_order = client.patch(f"/api/v1/documents/{doc_id}", headers=_headers(token), json={"effective_date": "2025-01-01", "expiration_date": "2024-01-01"})
    assert invalid_order.status_code == 400
    invalid_type = client.patch(f"/api/v1/documents/{doc_id}", headers=_headers(token), json={"document_type": "BAD"})
    assert invalid_type.status_code == 400
    too_long = client.patch(f"/api/v1/documents/{doc_id}", headers=_headers(token), json={"review_notes": "x" * 4001})
    assert too_long.status_code == 400

    ok = client.patch(
        f"/api/v1/documents/{doc_id}",
        headers=_headers(token),
        json={"document_type": "NDA", "execution_status": "signed", "retention_category": "indefinite", "effective_date": "2024-01-01", "expiration_date": "2025-01-01"},
    )
    assert ok.status_code == 200
    with app.app_context():
        doc = db.session.get(Document, doc_id)
        doc.review_status = ReviewStatus.NEEDS_REVIEW
        db.session.commit()
    queue = client.get("/api/v1/documents/review-queue", headers=_headers(token))
    assert queue.status_code == 200
    queue_body = queue.get_json()
    assert queue_body["documents"][0]["id"] == doc_id
    assert queue_body["total"] == 1
    assert queue_body["page"] == 1
    export = client.get("/api/v1/documents/export.csv", headers=_headers(token))
    assert export.status_code == 200
    assert b"original_name" in export.data and b"Acme_NDA.txt" in export.data


def test_upload_content_validation_rejects_empty_and_mismatched_files(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    client = app.test_client()
    token = _login(client)
    empty = client.post("/api/v1/upload", headers=_headers(token), data={"file": (io.BytesIO(b""), "empty.txt")}, content_type="multipart/form-data")
    assert empty.status_code == 400
    mismatch = client.post("/api/v1/upload", headers=_headers(token), data={"file": (io.BytesIO(b"not a pdf"), "fake.pdf")}, content_type="multipart/form-data")
    assert mismatch.status_code == 400
    txt_binary = client.post("/api/v1/upload", headers=_headers(token), data={"file": (io.BytesIO(b"abc\x00def"), "bad.txt")}, content_type="multipart/form-data")
    assert txt_binary.status_code == 400


def test_api_key_cannot_cross_tenant_or_use_role_protected_document_mutation(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch, API_KEY="secret-token")
    client = app.test_client()
    admin_token = _login(client)
    tenant_doc_id = _upload(client, admin_token, name="Tenant_NDA.txt", body=b"Tenant confidential NDA")

    api_upload = client.post(
        "/api/v1/upload",
        headers={"X-API-Key": "secret-token"},
        data={"file": (io.BytesIO(b"API key document"), "Api_Doc.txt")},
        content_type="multipart/form-data",
    )
    assert api_upload.status_code == 201

    listed = client.get("/api/v1/documents", headers={"X-API-Key": "secret-token"})
    assert listed.status_code == 200
    names = {doc["original_name"] for doc in listed.get_json()["documents"]}
    assert "Api_Doc.txt" in names
    assert "Tenant_NDA.txt" not in names

    mutation = client.patch(
        f"/api/v1/documents/{tenant_doc_id}",
        headers={"X-API-Key": "secret-token"},
        json={"document_type": "NDA"},
    )
    assert mutation.status_code == 403
