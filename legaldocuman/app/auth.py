"""Small API-key authentication layer for pilot deployments."""
from __future__ import annotations

from functools import wraps
from hmac import compare_digest

from flask import current_app, jsonify, request


def _configured_api_key() -> str | None:
    key = current_app.config.get("API_KEY")
    if isinstance(key, str):
        key = key.strip()
    return key or None


def api_auth_required(view):
    """Protect API routes when API_KEY is configured.

    Local development stays frictionless when API_KEY is unset. Pilot/shared
    deployments should set API_KEY and clients must pass either:
      Authorization: Bearer <key>
    or:
      X-API-Key: <key>
    """

    @wraps(view)
    def wrapped(*args, **kwargs):
        expected = _configured_api_key()
        if not expected:
            return view(*args, **kwargs)

        supplied = request.headers.get("X-API-Key", "") or request.args.get("api_key", "")
        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            supplied = auth_header.split(" ", 1)[1].strip()

        if not supplied or not compare_digest(supplied, expected):
            return jsonify({"error": "Unauthorized"}), 401

        return view(*args, **kwargs)

    return wrapped
