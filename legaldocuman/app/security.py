"""Upload malware scanning hooks.

The built-in scanner catches the standard EICAR test string and obvious empty
files. For production, set MALWARE_SCANNER=clamav and CLAMSCAN_PATH to a local
clamscan executable in the web/worker container.
"""
from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from flask import current_app, jsonify, request


EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
EICAR_MARKER = b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"


@dataclass
class ScanResult:
    status: str
    message: str

    @property
    def clean(self) -> bool:
        return self.status == "clean"


class MalwareScanner:
    def scan(self, path: str) -> ScanResult:
        mode = current_app.config.get("MALWARE_SCANNER", "builtin")
        if mode in {"off", "disabled", "none"}:
            return ScanResult("clean", "Malware scanning disabled")
        if mode == "clamav":
            return self._scan_clamav(path)
        return self._scan_builtin(path)

    def _scan_builtin(self, path: str) -> ScanResult:
        file_path = Path(path)
        if file_path.stat().st_size == 0:
            return ScanResult("error", "Uploaded file is empty")
        with file_path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                if EICAR in chunk or EICAR_MARKER in chunk:
                    return ScanResult("infected", "EICAR test signature detected")
        return ScanResult("clean", "Built-in scan passed")

    def _scan_clamav(self, path: str) -> ScanResult:
        exe = current_app.config.get("CLAMSCAN_PATH", "clamscan")
        completed = subprocess.run([exe, "--no-summary", path], capture_output=True, text=True, timeout=120)
        output = (completed.stdout or completed.stderr or "").strip()
        if completed.returncode == 0:
            return ScanResult("clean", output or "ClamAV scan passed")
        if completed.returncode == 1:
            return ScanResult("infected", output or "ClamAV detected malware")
        return ScanResult("error", output or f"ClamAV failed with exit code {completed.returncode}")


def _client_key() -> str:
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    ip = forwarded_for.split(",", 1)[0].strip() if forwarded_for else request.remote_addr
    return ip or "unknown"


def _rate_limited(app, bucket_name: str, limit: int) -> bool:
    if not app.config.get("RATE_LIMIT_ENABLED", True) or limit <= 0:
        return False
    window = int(app.config.get("RATE_LIMIT_WINDOW_SECONDS", 60))
    now = time.monotonic()
    store = app.extensions.setdefault("legaldocuman_rate_limits", {})
    key = (bucket_name, _client_key())
    entries = [ts for ts in store.get(key, []) if now - ts < window]
    if len(entries) >= limit:
        store[key] = entries
        return True
    entries.append(now)
    store[key] = entries
    return False


def init_security(app):
    """Install simple in-memory rate limits and baseline security headers."""

    @app.before_request
    def enforce_basic_rate_limits():
        if request.endpoint == "api.login":
            if _rate_limited(app, "auth", int(app.config.get("RATE_LIMIT_AUTH_PER_MINUTE", 10))):
                return jsonify({"error": "Too many requests"}), 429
        if request.endpoint == "api.upload_file":
            if _rate_limited(app, "upload", int(app.config.get("RATE_LIMIT_UPLOAD_PER_MINUTE", 30))):
                return jsonify({"error": "Too many requests"}), 429

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
        )
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return response
