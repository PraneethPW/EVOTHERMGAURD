"""Read immutable training artifacts for the authenticated model laboratory."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings


def list_experiments(limit: int = 25) -> list[dict]:
    root = Path(settings.experiments_path)
    if not root.is_dir():
        return []
    records = []
    for path in sorted(root.glob("experiment-*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(record, dict) or record.get("status") != "completed":
            continue
        record.pop("checkpoint", None)
        config = record.get("config")
        if isinstance(config, dict):
            config.pop("manifest_path", None)
            config.pop("output_dir", None)
        records.append(record)
        if len(records) >= limit:
            break
    return records
