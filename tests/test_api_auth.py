"""Tests for API-key authentication behavior."""
import io

from legaldocuman.app import create_app
from legaldocuman.app.extensions import db


def _make_app(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'auth.db'}")
    monkeypatch.setenv("UPLOAD_FOLDER", str(tmp_path / "uploads"))
    monkeypatch.setenv("PROCESSED_FOLDER", str(tmp_path / "processed"))
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("API_KEY", "secret-token")
    monkeypatch.setenv("JOB_BACKEND", "sync")

    from legaldocuman.config import Config
    Config._instance = None

    app = create_app()
    app.config.update(TESTING=True)
    return app


def test_api_key_required_when_configured(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()

    response = client.get("/api/v1/documents")
    assert response.status_code == 401


def test_api_key_header_allows_request(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()

    response = client.get("/api/v1/documents", headers={"X-API-Key": "secret-token"})
    assert response.status_code == 200


def test_api_key_query_allows_download(tmp_path, monkeypatch):
    app = _make_app(tmp_path, monkeypatch)
    client = app.test_client()

    upload = client.post(
        "/api/v1/upload",
        headers={"X-API-Key": "secret-token"},
        data={"file": (io.BytesIO(b"Acme NDA digitally signed by Jane Doe"), "Acme_NDA.txt")},
        content_type="multipart/form-data",
    )
    assert upload.status_code == 201
    doc_id = upload.get_json()["id"]

    download = client.get(f"/api/v1/documents/{doc_id}/download?api_key=secret-token")
    assert download.status_code == 200
