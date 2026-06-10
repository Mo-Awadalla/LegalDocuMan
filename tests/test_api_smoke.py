"""Smoke tests for the Flask document API foundation."""
import io

from legaldocuman.app import create_app
from legaldocuman.app.extensions import db
from legaldocuman.app.models import Document


STATIC_UPLOAD = lambda doc_id: None


def _make_app(tmp_path, monkeypatch):
    db_path = tmp_path / "api-smoke.db"
    upload_dir = tmp_path / "uploads"
    processed_dir = tmp_path / "processed"

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("UPLOAD_FOLDER", str(upload_dir))
    monkeypatch.setenv("PROCESSED_FOLDER", str(processed_dir))
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("ALLOW_OPEN_DEV_MODE", "1")

    import legaldocuman.app.api.routes as api_routes
    monkeypatch.setattr(api_routes, "process_document_async", STATIC_UPLOAD)

    app = create_app()
    app.config.update(TESTING=True)
    return app


def test_upload_sanitizes_filename_and_downloads_file(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()

    response = client.post(
        "/api/v1/upload",
        data={"file": (io.BytesIO(b"hello contract"), "../unsafe contract.txt")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    doc_id = response.get_json()["id"]

    with app.app_context():
        doc = db.session.get(Document, doc_id)
        assert doc.original_name == "unsafe_contract.txt"
        assert doc.stored_path.endswith("unsafe_contract.txt")
        assert doc.file_size == len(b"hello contract")

    download = client.get(f"/api/v1/documents/{doc_id}/download")
    assert download.status_code == 200
    assert download.data == b"hello contract"


def test_rejects_unsupported_upload_type(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()

    response = client.post(
        "/api/v1/upload",
        data={"file": (io.BytesIO(b"bad"), "malware.exe")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert "Unsupported file type" in response.get_json()["error"]
