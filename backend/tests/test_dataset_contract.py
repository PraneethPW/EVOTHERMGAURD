from pathlib import Path

import pandas as pd
import pytest
from PIL import Image

from ml_training.dataset import ManifestValidationError, MultimodalDataset, manifest_summary


def _write_image(path: Path, mode: str) -> None:
    Image.new(mode, (40, 40), 128 if mode == "L" else (40, 80, 120)).save(path)


def test_manifest_requires_held_out_splits_and_loads_associated_context(tmp_path):
    rgb = tmp_path / "rgb.png"
    thermal = tmp_path / "thermal.png"
    _write_image(rgb, "RGB")
    _write_image(thermal, "L")
    rows = []
    for index, split in enumerate(("train", "validation", "test")):
        rows.append(
            {
                "sample_id": f"sample-{index}",
                "rgb_path": rgb.name,
                "thermal_path": thermal.name,
                "ambient_temperature": 31,
                "humidity": 48,
                "weather": "clear",
                "season": "summer",
                "time_of_day": "afternoon",
                "sun_exposure": "partial",
                "label": "NORMAL",
                "split": split,
            }
        )
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame(rows).to_csv(manifest, index=False)
    summary = manifest_summary(manifest)
    assert summary["ready"] is True
    assert summary["sample_count"] == 3
    sample = MultimodalDataset(manifest, "train", image_size=32)[0]
    assert tuple(sample["rgb"].shape) == (3, 32, 32)
    assert tuple(sample["thermal"].shape) == (1, 32, 32)
    assert tuple(sample["environment"].shape) == (22,)


def test_manifest_rejects_unlabelled_or_unsplit_data(tmp_path):
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame([{"sample_id": "one"}]).to_csv(manifest, index=False)
    summary = manifest_summary(manifest)
    assert summary["ready"] is False
    with pytest.raises(ManifestValidationError):
        MultimodalDataset(manifest, "train")
