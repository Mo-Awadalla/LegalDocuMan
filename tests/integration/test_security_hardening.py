"""Security hardening tests: signed downloads, rate limits, headers."""
import io

from legaldocuman.app import create_app
from legaldocuman.app.extensions import db
from legaldocuman.app.models import Tenant, User, UserRole
from legaldocuman.config import Config


def _app(tmp_path, monkeypatch, **env):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'security.db'}")
    monkeypatch.setenv("UPLOAD_FOLDER", str(tmp_path / "uploads"))
    monkeypatch.setenv("PROCESSED_FOLDER", str(tmp_path / "processed"))
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("JOB_BACKEND", "sync")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "password123")
    for key, value in env.items():
        monkeypatch.setenv(key, str(value))
    Config._instance = None
    app = create_app()
    app.config.update(TESTING=True)
    return app


def _login(client, email="admin@example.com", password="password123"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.get_json()["token"]


def _upload(client, token, name="Acme_NDA.txt", body=b"Acme NDA digitally signed by Jane Doe"):
    response = client.post(
        "/api/v1/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"file": (io.BytesIO(body), name)},
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    return response.get_json()["id"]


def test_unauthenticated_download_token_mint_fails(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    client = app.test_client()
    token = _login(client)
    doc_id = _upload(client, token)

    response = client.post(f"/api/v1/documents/{doc_id}/download-token")

    assert response.status_code == 401


def test_download_token_mint_and_download_succeed_with_auth(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch, DOWNLOAD_TOKEN_TTL_SECONDS="120")
    client = app.test_client()
    token = _login(client)
    doc_id = _upload(client, token)

    mint = client.post(f"/api/v1/documents/{doc_id}/download-token", headers={"Authorization": f"Bearer {token}"})
    assert mint.status_code == 200
    body = mint.get_json()
    assert body["download_token"]
    assert body["expires_in"] == 120

    download = client.get(f"/api/v1/documents/{doc_id}/download?download_token={body['download_token']}")
    assert download.status_code == 200
    assert b"Acme NDA" in download.data


def test_cross_tenant_download_token_and_mint_fail(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    client = app.test_client()
    admin_token = _login(client)
    doc_id = _upload(client, admin_token, body=b"Tenant one confidential NDA")

    with app.app_context():
        tenant = Tenant(name="Other Tenant", slug="other")
        db.session.add(tenant)
        db.session.flush()
        other = User(tenant_id=tenant.id, email="other@example.com", name="Other", role=UserRole.REVIEWER)
        other.set_password("password123")
        db.session.add(other)
        db.session.commit()

    other_token = _login(client, "other@example.com", "password123")
    other_doc_id = _upload(client, other_token, name="Other_NDA.txt", body=b"Tenant two confidential NDA")

    denied_mint = client.post(f"/api/v1/documents/{doc_id}/download-token", headers={"Authorization": f"Bearer {other_token}"})
    assert denied_mint.status_code == 404

    mint = client.post(f"/api/v1/documents/{doc_id}/download-token", headers={"Authorization": f"Bearer {admin_token}"})
    assert mint.status_code == 200
    download_token = mint.get_json()["download_token"]

    denied_download = client.get(f"/api/v1/documents/{other_doc_id}/download?download_token={download_token}")
    assert denied_download.status_code == 401


def test_auth_rate_limit_can_block_when_set_low(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch, RATE_LIMIT_AUTH_PER_MINUTE="1")
    client = app.test_client()

    first = client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "wrong"})
    second = client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "wrong"})

    assert first.status_code == 401
    assert second.status_code == 429


def test_upload_rate_limit_can_block_when_set_low(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch, RATE_LIMIT_UPLOAD_PER_MINUTE="1")
    client = app.test_client()
    token = _login(client)

    first_id = _upload(client, token, name="One.txt", body=b"First upload body")
    second = client.post(
        "/api/v1/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"file": (io.BytesIO(b"Second upload body"), "Two.txt")},
        content_type="multipart/form-data",
    )

    assert first_id
    assert second.status_code == 429


def test_security_headers_are_present(tmp_path, monkeypatch):
    app = _app(tmp_path, monkeypatch)
    client = app.test_client()

    response = client.get("/api/v1/documents")

    assert response.headers["Content-Security-Policy"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"
