"""Upload malware scanning hooks.

The built-in scanner catches the standard EICAR test string and obvious empty
files. For production, set MALWARE_SCANNER=clamav and CLAMSCAN_PATH to a local
clamscan executable in the web/worker container.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from flask import current_app


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
