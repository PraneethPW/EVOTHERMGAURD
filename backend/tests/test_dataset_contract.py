from pathlib import Path

import pandas as pd
import pytest
from PIL import Image

from ml_training.dataset import ManifestValidationError, MultimodalDataset, manifest_summary


def _write_image(path: Path, mode: str) -> None:
    Image.new(mode, (40, 40), 128 if mode == "L" else (40, 80, 120)).save(path)


def test_manifest_requires_held_out_splits_and_loads_associated_context(tmp_path):
    rows = []
    for index, split in enumerate(("train", "validation", "test")):
        rgb = tmp_path / f"rgb{index}.png"
        thermal = tmp_path / f"thermal{index}.png"
        Image.new("RGB", (40, 40), (40 + index, 80, 120)).save(rgb)
        Image.new("L", (40, 40), 128 + index).save(thermal)
        rows.append(
            {
                "sample_id": f"sample-{index}",
                "capture_group": f"session-{index}",
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


def test_augmentation_flips_localization_mask_with_both_images(tmp_path, monkeypatch):
    import numpy as np
    import torch
    from ml_training.dataset import TF

    rows = []
    for index, split in enumerate(("train", "validation", "test")):
        pixels = np.zeros((32, 32), dtype=np.uint8)
        pixels[:, :8] = 255 - index
        Image.fromarray(pixels).save(tmp_path / f"thermal{index}.png")
        rgb = np.stack([pixels, np.full_like(pixels, 10 + index), pixels], axis=2)
        Image.fromarray(rgb).save(tmp_path / f"rgb{index}.png")
        Image.fromarray(pixels).save(tmp_path / f"mask{index}.png")
        rows.append(dict(sample_id=str(index), capture_group=f"session{index}",
                         rgb_path=f"rgb{index}.png", thermal_path=f"thermal{index}.png",
                         mask_path=f"mask{index}.png", ambient_temperature=30, humidity=50,
                         weather="clear", season="summer", time_of_day="morning",
                         sun_exposure="none", label="NORMAL", split=split))
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame(rows).to_csv(manifest, index=False)
    unflipped = MultimodalDataset(manifest, "train", image_size=32)[0]
    monkeypatch.setattr(torch, "rand", lambda *args: torch.tensor(0.1))
    flipped = MultimodalDataset(manifest, "train", image_size=32, augment=True)[0]
    for key in ("rgb", "thermal", "mask"):
        assert torch.equal(flipped[key], TF.hflip(unflipped[key]))
