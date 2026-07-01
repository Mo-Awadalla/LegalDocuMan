"""Authentication and RBAC helpers."""
from __future__ import annotations

from functools import wraps
from hmac import compare_digest
from typing import Iterable

from flask import current_app, g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .extensions import db
from .models import AuditEvent, Tenant, User, UserRole


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="legaldocuman-auth")


def _download_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="legaldocuman-download")


def issue_token(user: User) -> str:
    return _serializer().dumps({"user_id": user.id})


def issue_download_token(document_id: int, tenant_id: int | None, user_id: int | None = None) -> str:
    """Issue a short-lived, signed browser-download token for one document."""
    return _download_serializer().dumps({
        "document_id": document_id,
        "tenant_id": tenant_id,
        "user_id": user_id,
    })


def load_download_token(token: str) -> dict | None:
    if not token:
        return None
    try:
        data = _download_serializer().loads(
            token,
            max_age=int(current_app.config.get("DOWNLOAD_TOKEN_TTL_SECONDS", 300)),
        )
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(data, dict) or "document_id" not in data:
        return None
    return data


def current_user() -> User | None:
    return getattr(g, "current_user", None)


def current_tenant_id() -> int | None:
    user = current_user()
    return user.tenant_id if user else None


def api_key_authenticated() -> bool:
    return bool(getattr(g, "api_key_authenticated", False))


def _configured_api_key() -> str | None:
    key = current_app.config.get("API_KEY")
    if isinstance(key, str):
        key = key.strip()
    return key or None


def bootstrap_default_identity() -> None:
    """Create the first tenant/admin from env when configured.

    Required env/config:
      BOOTSTRAP_ADMIN_EMAIL
      BOOTSTRAP_ADMIN_PASSWORD
    """
    email = current_app.config.get("BOOTSTRAP_ADMIN_EMAIL")
    password = current_app.config.get("BOOTSTRAP_ADMIN_PASSWORD")
    if not email or not password or User.query.first():
        return

    tenant = Tenant(name=current_app.config.get("BOOTSTRAP_TENANT_NAME") or "Default Tenant", slug="default")
    db.session.add(tenant)
    db.session.flush()
    user = User(
        tenant_id=tenant.id,
        email=email.lower(),
        name=current_app.config.get("BOOTSTRAP_ADMIN_NAME") or "Admin",
        role=UserRole.ADMIN,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()


def _load_user_from_token(token: str) -> User | None:
    if not token:
        return None
    try:
        data = _serializer().loads(token, max_age=int(current_app.config.get("AUTH_TOKEN_TTL_SECONDS", 86400)))
    except (BadSignature, SignatureExpired):
        return None
    user = db.session.get(User, data.get("user_id"))
    if user and user.is_active:
        return user
    return None


def _load_user_from_bearer(auth_header: str) -> User | None:
    if not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header.split(" ", 1)[1].strip()
    return _load_user_from_token(token)


def _api_key_is_valid() -> bool:
    expected = _configured_api_key()
    if not expected:
        return False
    supplied = request.headers.get("X-API-Key", "") or request.args.get("api_key", "")
    if not supplied:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            supplied = auth_header.split(" ", 1)[1].strip()
    return bool(supplied and compare_digest(supplied, expected))


def _legacy_open_dev_mode() -> bool:
    return bool(current_app.config.get("ALLOW_OPEN_DEV_MODE")) and not _configured_api_key() and User.query.count() == 0


def authenticate_request(roles: Iterable[UserRole | str] | None = None):
    """Authenticate the current request.

    Returns None when access is allowed, otherwise a Flask response tuple.
    """
    allowed = {r.value if isinstance(r, UserRole) else r for r in roles} if roles else None

    user = _load_user_from_bearer(request.headers.get("Authorization", "")) or _load_user_from_token(request.args.get("api_key", ""))
    if user:
        g.current_user = user
        if allowed and user.role.value not in allowed:
            return jsonify({"error": "Forbidden"}), 403
        return None

    if _api_key_is_valid() or _legacy_open_dev_mode():
        if allowed:
            return jsonify({"error": "Forbidden"}), 403
        g.current_user = None
        g.api_key_authenticated = True
        return None

    return jsonify({"error": "Unauthorized"}), 401


def auth_required(roles: Iterable[UserRole | str] | None = None):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            auth_error = authenticate_request(roles)
            if auth_error:
                return auth_error
            return view(*args, **kwargs)

        return wrapped

    return decorator


# Backwards-compatible alias used by existing routes/tests.
def api_auth_required(view):
    return auth_required()(view)


def audit(action: str, document_id: int | None = None, details: dict | None = None) -> AuditEvent:
    user = current_user()
    event = AuditEvent(
        tenant_id=user.tenant_id if user else None,
        user_id=user.id if user else None,
        document_id=document_id,
        action=action,
        details=details or {},
        ip_address=request.headers.get("X-Forwarded-For", request.remote_addr) if request else None,
        user_agent=request.headers.get("User-Agent") if request else None,
    )
    db.session.add(event)
    return event
