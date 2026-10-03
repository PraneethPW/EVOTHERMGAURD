"""Validate evidence and split integrity without requiring a training runtime."""

import csv
import hashlib
import math
from collections import Counter
from pathlib import Path

from PIL import Image

from app.ml.constants import RISK_CLASSES

REQUIRED_COLUMNS = {
    "sample_id", "capture_group", "rgb_path", "thermal_path",
    "ambient_temperature", "humidity", "weather", "season",
    "time_of_day", "sun_exposure", "label", "split",
}
SPLITS = {"train", "validation", "test"}


class ManifestValidationError(ValueError):
    pass


def validate_rows(rows: list[dict], root: Path) -> None:
    if not rows:
        raise ManifestValidationError("Manifest contains no labelled samples")
    missing = REQUIRED_COLUMNS - set(rows[0])
    if missing:
        raise ManifestValidationError("Manifest is missing columns: " + ", ".join(sorted(missing)))
    seen_ids, group_splits, image_splits, cache = set(), {}, {}, {}
    splits = set()
    for row in rows:
        sample_id = str(row["sample_id"]).strip()
        if not sample_id or sample_id.lower() == "nan" or sample_id in seen_ids:
            raise ManifestValidationError("sample_id values must be nonempty and unique")
        seen_ids.add(sample_id)
        split = str(row["split"]).strip().lower()
        if split not in SPLITS:
            raise ManifestValidationError(f"Unsupported split: {split}")
        splits.add(split)
        if str(row["label"]).strip().upper() not in RISK_CLASSES:
            raise ManifestValidationError(f"Unsupported label for {sample_id}")
        group = str(row["capture_group"]).strip()
        if not group or group.lower() == "nan":
            raise ManifestValidationError("capture_group must identify an asset/recording session")
        if group_splits.setdefault(group, split) != split:
            raise ManifestValidationError(f"Capture group {group} occurs across splits")
        for field in ("ambient_temperature", "humidity"):
            try:
                value = float(row[field])
            except (TypeError, ValueError):
                raise ManifestValidationError(f"{field} must be finite numeric data") from None
            if not math.isfinite(value):
                raise ManifestValidationError(f"{field} must be finite numeric data")
        if not 0 <= float(row["humidity"]) <= 100:
            raise ManifestValidationError("humidity must be between 0 and 100")
        fingerprints = []
        for field in ("rgb_path", "thermal_path"):
            path = Path(str(row[field]))
            path = (path if path.is_absolute() else root / path).resolve()
            if not path.is_file():
                raise ManifestValidationError(f"Referenced evidence file is missing: {path}")
            if path not in cache:
                try:
                    with Image.open(path) as image:
                        # Decoded pixels catch identical images saved under new names/formats.
                        pixels = image.convert("RGB")
                        digest = hashlib.sha256(str(pixels.size).encode() + pixels.tobytes()).hexdigest()
                except (OSError, ValueError) as exc:
                    raise ManifestValidationError(f"Evidence image cannot be decoded: {path}") from exc
                cache[path] = digest
            digest = cache[path]
            if image_splits.setdefault(digest, split) != split:
                raise ManifestValidationError(f"Image content occurs across splits: {path}")
            fingerprints.append(digest)
        if fingerprints[0] == fingerprints[1]:
            raise ManifestValidationError(f"RGB and thermal evidence are identical for {sample_id}")
    if splits != SPLITS:
        raise ManifestValidationError("Manifest must include train, validation and test splits")


def manifest_summary(manifest_path: str | Path) -> dict:
    path = Path(manifest_path).resolve()
    try:
        with path.open(newline="", encoding="utf-8-sig") as source:
            rows = list(csv.DictReader(source))
        validate_rows(rows, path.parent)
    except (OSError, ValueError, csv.Error) as exc:
        return {"ready": False, "labelled": False, "sample_count": 0, "reason": str(exc)}
    return {
        "ready": True, "labelled": True, "sample_count": len(rows),
        "split_counts": dict(Counter(str(row["split"]).strip().lower() for row in rows)),
        "class_counts": {label: sum(str(row["label"]).strip().upper() == label for row in rows) for label in RISK_CLASSES},
        "split_integrity_checked": True,
        "context_is_associated_metadata": True,
        "note": "Group identifiers and risk labels must be verified by the dataset curator; near duplicates are not automatically detected.",
    }
