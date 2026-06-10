"""Utilities for inspecting LegalDocuMan backend tracking registries."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

try:
    import pandas as pd
except ImportError:  # pragma: no cover - tests patch this symbol directly
    pd = None


REGISTRY_FILE_NAME = "_backend_tracking_registry.json"


def load_tracking_registry(base_dir: str) -> Optional[Dict[str, Any]]:
    """Load the backend tracking registry from a processed/input directory."""
    path = os.path.join(base_dir, REGISTRY_FILE_NAME)
    if not os.path.exists(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _parse_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        try:
            return datetime.strptime(str(value), "%Y-%m-%d")
        except ValueError:
            return None


def _documents(registry: Optional[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
    if not registry:
        return []
    return registry.get("expiration_tracking") or []


def query_expiring_documents(
    registry: Optional[Dict[str, Any]], months_ahead: int = 12
) -> List[Dict[str, Any]]:
    """Return non-expired documents expiring within the next N months."""
    now = datetime.now()
    cutoff = now + timedelta(days=months_ahead * 31)
    results: List[Dict[str, Any]] = []

    for doc in _documents(registry):
        exp = _parse_datetime(doc.get("expiration_date"))
        if not exp or exp < now or exp > cutoff:
            continue
        item = dict(doc)
        item["days_until_expiration"] = (exp - now).days
        results.append(item)

    return sorted(results, key=lambda d: d.get("expiration_date") or "")


def query_by_retention_category(
    registry: Optional[Dict[str, Any]], category: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Return documents filtered by retention category, or all documents."""
    docs = list(_documents(registry))
    if not category:
        return docs
    needle = category.lower()
    return [
        doc for doc in docs
        if str(doc.get("retention_category", "")).lower() == needle
    ]


def generate_excel_report(
    registry: Optional[Dict[str, Any]], output_path: str = "backend_tracking_report.xlsx"
) -> Optional[str]:
    """Generate an Excel report for tracked documents."""
    docs = list(_documents(registry))
    if not docs or pd is None:
        return None

    today = datetime.now()
    rows = []
    for doc in docs:
        row = dict(doc)
        exp = _parse_datetime(doc.get("expiration_date"))
        if exp:
            row["days_until_expiration"] = (exp - today).days
            if exp < today:
                row["expiration_status"] = "expired"
            elif exp <= today + timedelta(days=90):
                row["expiration_status"] = "expiring_soon"
            else:
                row["expiration_status"] = "active"
        else:
            row["days_until_expiration"] = None
            row["expiration_status"] = "no_expiration"
        rows.append(row)

    df = pd.DataFrame(rows)
    with pd.ExcelWriter(output_path) as writer:
        df.to_excel(writer, index=False, sheet_name="Documents")
    return output_path


def print_summary(registry: Optional[Dict[str, Any]]) -> None:
    """Print a concise registry summary."""
    if registry is None:
        return

    print("BACKEND TRACKING SUMMARY")
    print("=" * 50)
    print(f"Total documents: {registry.get('total_documents', 0)}")
    print(f"Documents with expiration: {registry.get('documents_with_expiration', 0)}")

    categories: Dict[str, int] = {}
    for doc in _documents(registry):
        cat = doc.get("retention_category") or "unknown"
        categories[cat] = categories.get(cat, 0) + 1

    if categories:
        print("Retention categories:")
        for category, count in sorted(categories.items()):
            print(f"  {category}: {count}")
