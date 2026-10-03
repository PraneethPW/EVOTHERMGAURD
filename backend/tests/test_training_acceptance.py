"""Small fixtures exercise code paths; their predictions are not accuracy evidence."""

import csv
from dataclasses import replace

import pytest
from PIL import Image

torch = pytest.importorskip("torch")

from app.ml.constants import RISK_CLASSES
from app.ml.inference import ModelService
from app.core.config import settings
from ml_training.config import TrainingConfig
from ml_training.train import run_training


def test_training_candidates_leave_test_untouched_and_final_run_is_not_auto_validated(tmp_path, monkeypatch):
    torch.set_num_threads(1)
    rows = []
    for split in ("train", "validation", "test"):
        for label in RISK_CLASSES:
            index = len(rows)
            Image.new("RGB", (32, 32), (20 + index, 40, 100)).save(tmp_path / f"rgb{index}.png")
            Image.new("L", (32, 32), 100 + index).save(tmp_path / f"thermal{index}.png")
            rows.append(dict(sample_id=str(index), capture_group=f"session{index}",
                             rgb_path=f"rgb{index}.png", thermal_path=f"thermal{index}.png",
                             ambient_temperature=30, humidity=50, weather="clear",
                             season="summer", time_of_day="morning", sun_exposure="none",
                             label=label, split=split))
    manifest = tmp_path / "manifest.csv"
    with manifest.open("w", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    config = TrainingConfig(manifest_path=str(manifest), output_dir=str(tmp_path / "models"),
                            image_size=32, batch_size=4, epochs=1, evaluate_test=False)
    from ml_training import train
    original_classify = train.classify
    def validation_only(model, loader, *args):
        assert set(loader.dataset.frame["split"]) == {"validation"}
        return original_classify(model, loader, *args)
    with monkeypatch.context() as isolated:
        isolated.setattr(train, "classify", validation_only)
        candidate = run_training(config)
    assert candidate["held_out_evaluated"] is False
    assert candidate["metrics"] is None
    assert candidate["quality_gate"]["passed"] is False

    final = run_training(replace(config, evaluate_test=True))
    checkpoint = torch.load(final["checkpoint"], map_location="cpu", weights_only=True)
    assert final["metrics"]["sample_count"] == 4
    assert final["held_out_evaluated"] is True
    assert final["quality_gate"]["passed"] is False
    assert checkpoint["validated"] is False
    monkeypatch.setattr(settings, "model_mode", "trained")
    monkeypatch.setattr(settings, "model_checkpoint", final["checkpoint"])
    service = ModelService()
    result = service.predict(tmp_path / "rgb0.png", tmp_path / "thermal0.png",
                             dict(ambient_temperature=30, humidity=50))
    assert result["evidence"]["validated"] is False
    assert service.status()["mode"] == "trained"
    assert service.status()["validated"] is False


def test_checkpoint_with_different_class_order_is_rejected(tmp_path, monkeypatch):
    path = tmp_path / "wrong-order.pt"
    torch.save({"classes": list(reversed(RISK_CLASSES))}, path)
    monkeypatch.setattr(settings, "model_checkpoint", str(path))
    with pytest.raises(ValueError, match="class ordering"):
        ModelService()._load_trained_model()
