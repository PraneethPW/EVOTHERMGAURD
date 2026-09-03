"""Labelled paired RGB/thermal dataset contract.

Environmental values belong to each paired observation. They are contextual
features, not a separately claimed environmental dataset.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import torch
from PIL import Image
from torch.utils.data import Dataset
from torchvision.transforms import functional as TF

from app.ml.model import ENVIRONMENT_FEATURES, RISK_CLASSES


REQUIRED_COLUMNS = {
    "sample_id",
    "rgb_path",
    "thermal_path",
    "ambient_temperature",
    "humidity",
    "weather",
    "season",
    "time_of_day",
    "sun_exposure",
    "label",
    "split",
}
SPLITS = {"train", "validation", "test"}
CATEGORIES = {
    "weather": ("clear", "cloudy", "rain", "windy", "unknown"),
    "season": ("summer", "monsoon", "winter", "spring", "unknown"),
    "time_of_day": ("morning", "afternoon", "evening", "night", "unknown"),
    "sun_exposure": ("none", "low", "partial", "direct", "unknown"),
}


def _normalise(value: object) -> str:
    return str(value).strip().lower().replace(" ", "_")


def encode_environment(row: pd.Series | dict) -> torch.Tensor:
    """Encode context using bounded numerics and fixed, auditable categories."""
    values = [
        float(np.clip((float(row["ambient_temperature"]) - 20.0) / 60.0, -1, 1)),
        float(np.clip(float(row["humidity"]) / 100.0, 0, 1)),
    ]
    for field, options in CATEGORIES.items():
        selected = _normalise(row.get(field, "unknown"))
        if selected not in options:
            selected = "unknown"
        values.extend(float(selected == option) for option in options)
    result = torch.tensor(values, dtype=torch.float32)
    if result.numel() != ENVIRONMENT_FEATURES:
        raise RuntimeError("Environment encoder and model feature sizes disagree")
    return result


class ManifestValidationError(ValueError):
    pass


def validate_manifest(frame: pd.DataFrame, root: Path) -> None:
    missing = sorted(REQUIRED_COLUMNS.difference(frame.columns))
    if missing:
        raise ManifestValidationError(f"Manifest is missing columns: {', '.join(missing)}")
    if frame.empty:
        raise ManifestValidationError("Manifest contains no labelled samples")
    if frame["sample_id"].astype(str).duplicated().any():
        raise ManifestValidationError("sample_id values must be unique")
    invalid_labels = sorted(set(frame["label"].astype(str).str.upper()) - set(RISK_CLASSES))
    if invalid_labels:
        raise ManifestValidationError(f"Unsupported labels: {', '.join(invalid_labels)}")
    invalid_splits = sorted(set(frame["split"].map(_normalise)) - SPLITS)
    if invalid_splits:
        raise ManifestValidationError(f"Unsupported splits: {', '.join(invalid_splits)}")
    missing_splits = sorted(SPLITS - set(frame["split"].map(_normalise)))
    if missing_splits:
        raise ManifestValidationError(
            f"Manifest must include held-out splits: {', '.join(missing_splits)}"
        )
    for field in ("ambient_temperature", "humidity"):
        values = pd.to_numeric(frame[field], errors="coerce")
        if values.isna().any():
            raise ManifestValidationError(f"{field} contains non-numeric values")
    humidity = frame["humidity"].astype(float)
    if ((humidity < 0) | (humidity > 100)).any():
        raise ManifestValidationError("humidity must be between 0 and 100")
    missing_files: list[str] = []
    for field in ("rgb_path", "thermal_path"):
        for value in frame[field].astype(str):
            path = Path(value)
            resolved = path if path.is_absolute() else root / path
            if not resolved.is_file():
                missing_files.append(str(resolved))
                if len(missing_files) == 10:
                    break
    if missing_files:
        raise ManifestValidationError(
            "Referenced evidence files are missing (first 10): " + ", ".join(missing_files)
        )


def manifest_summary(manifest_path: str | Path) -> dict:
    path = Path(manifest_path).resolve()
    if not path.is_file():
        return {
            "ready": False,
            "sample_count": 0,
            "labelled": False,
            "reason": "No labelled manifest has been supplied.",
        }
    try:
        frame = pd.read_csv(path)
        validate_manifest(frame, path.parent)
    except (OSError, pd.errors.ParserError, ManifestValidationError) as exc:
        return {
            "ready": False,
            "sample_count": 0,
            "labelled": False,
            "reason": str(exc),
        }
    return {
        "ready": True,
        "sample_count": int(len(frame)),
        "labelled": True,
        "split_counts": {
            split: int((frame["split"].map(_normalise) == split).sum()) for split in SPLITS
        },
        "class_counts": {
            label: int((frame["label"].str.upper() == label).sum())
            for label in RISK_CLASSES
        },
        "context_is_associated_metadata": True,
    }


class MultimodalDataset(Dataset):
    def __init__(
        self,
        manifest_path: str | Path,
        split: str,
        image_size: int = 224,
        augment: bool = False,
    ) -> None:
        self.manifest_path = Path(manifest_path).resolve()
        frame = pd.read_csv(self.manifest_path)
        validate_manifest(frame, self.manifest_path.parent)
        split = _normalise(split)
        self.frame = frame[frame["split"].map(_normalise) == split].reset_index(drop=True)
        if self.frame.empty:
            raise ManifestValidationError(f"No samples were assigned to the {split} split")
        self.root = self.manifest_path.parent
        self.image_size = image_size
        self.augment = augment
        self.label_to_index = {label: index for index, label in enumerate(RISK_CLASSES)}

    def __len__(self) -> int:
        return len(self.frame)

    def _path(self, value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.root / path

    def __getitem__(self, index: int) -> dict[str, object]:
        row = self.frame.iloc[index]
        rgb = Image.open(self._path(str(row.rgb_path))).convert("RGB")
        thermal = Image.open(self._path(str(row.thermal_path))).convert("L")
        rgb = TF.resize(rgb, [self.image_size, self.image_size], antialias=True)
        thermal = TF.resize(thermal, [self.image_size, self.image_size], antialias=True)
        if self.augment and bool(torch.rand(()) < 0.5):
            rgb, thermal = TF.hflip(rgb), TF.hflip(thermal)
        rgb_tensor = TF.normalize(
            TF.to_tensor(rgb), mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)
        )
        thermal_tensor = TF.normalize(TF.to_tensor(thermal), mean=(0.5,), std=(0.25,))
        sample: dict[str, object] = {
            "sample_id": str(row.sample_id),
            "rgb": rgb_tensor,
            "thermal": thermal_tensor,
            "environment": encode_environment(row),
            "label": self.label_to_index[str(row.label).upper()],
            "mask": torch.zeros((1, self.image_size, self.image_size), dtype=torch.float32),
            "has_mask": False,
        }
        mask_path = str(row.get("mask_path", "")).strip()
        if mask_path and mask_path.lower() != "nan":
            mask = Image.open(self._path(mask_path)).convert("L")
            mask = TF.resize(mask, [self.image_size, self.image_size], antialias=False)
            sample["mask"] = (TF.to_tensor(mask) > 0.5).float()
            sample["has_mask"] = True
        return sample


def class_weights(dataset: MultimodalDataset) -> torch.Tensor:
    labels: Iterable[int] = (
        dataset.label_to_index[str(value).upper()] for value in dataset.frame["label"]
    )
    counts = np.bincount(list(labels), minlength=len(RISK_CLASSES)).astype(np.float32)
    counts[counts == 0] = 1
    weights = counts.sum() / (len(RISK_CLASSES) * counts)
    return torch.tensor(weights, dtype=torch.float32)
