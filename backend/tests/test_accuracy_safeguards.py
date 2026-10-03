import csv
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.core.config import settings
from app.ml.inference import ModelService, _dataset_status
from app.ml.manifest import ManifestValidationError, validate_rows
from app.ml.quality import quality_gate
from app.ml.processing import inspection_localization, localization_overlay
from ml_training.evaluate import evaluate, localization_metrics


def observations(root):
    rows = []
    for i, split in enumerate(("train", "validation", "test")):
        Image.new("RGB", (16, 16), (i * 50, 40, 10)).save(root / f"rgb{i}.png")
        Image.new("L", (16, 16), 100 + i * 50).save(root / f"thermal{i}.png")
        rows.append(dict(sample_id=str(i), capture_group=f"session{i}",
                         rgb_path=f"rgb{i}.png", thermal_path=f"thermal{i}.png",
                         ambient_temperature=30, humidity=50, weather="clear",
                         season="summer", time_of_day="morning", sun_exposure="none",
                         label="NORMAL", split=split))
    return rows


def test_renamed_reencoded_image_leaks_are_rejected(tmp_path):
    rows = observations(tmp_path)
    Image.open(tmp_path / "rgb0.png").save(tmp_path / "renamed.bmp")
    rows[2]["rgb_path"] = "renamed.bmp"
    with pytest.raises(ManifestValidationError, match="content occurs across splits"):
        validate_rows(rows, tmp_path)


def test_adjacent_frames_in_same_recording_cannot_cross_splits(tmp_path):
    rows = observations(tmp_path)
    rows[1]["capture_group"] = rows[0]["capture_group"]
    with pytest.raises(ManifestValidationError, match="group .* across splits"):
        validate_rows(rows, tmp_path)


@pytest.mark.parametrize("value", [float("inf"), float("nan"), "unknown"])
def test_environment_must_be_finite(tmp_path, value):
    rows = observations(tmp_path)
    rows[0]["ambient_temperature"] = value
    with pytest.raises(ManifestValidationError, match="finite"):
        validate_rows(rows, tmp_path)


def test_runtime_readiness_uses_full_evidence_validation(tmp_path):
    rows = observations(tmp_path)
    rows[1]["thermal_path"] = "missing.jpg"
    manifest = tmp_path / "manifest.csv"
    with manifest.open("w", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    assert _dataset_status(str(manifest))["ready"] is False


def test_normal_only_accuracy_cannot_pass_four_class_gate():
    metrics = evaluate([0] * 100, [0] * 100, [[1, 0, 0, 0]] * 100)
    assert metrics["accuracy"] == 1
    assert metrics["f1_macro"] == 0.25
    assert metrics["all_classes_present"] is False
    assert metrics["class_recall"]["CRITICAL"] is None
    assert quality_gate(metrics)["passed"] is False


def test_high_overall_accuracy_does_not_hide_critical_misses():
    labels = [0] * 950 + [1] * 50 + [2] * 50 + [3] * 50
    predictions = [0] * 950 + [1] * 50 + [2] * 50 + [0] * 50
    metrics = evaluate(labels, predictions)
    assert metrics["accuracy"] > 0.95
    assert metrics["critical_missed"] == 50
    assert metrics["class_recall"]["CRITICAL"] == 0
    assert quality_gate(metrics)["passed"] is False


def test_perfect_tiny_test_does_not_establish_quality():
    assert quality_gate(evaluate([0, 1, 2, 3], [0, 1, 2, 3]))["passed"] is False
    labels = list(range(4)) * 50
    assert quality_gate(evaluate(labels, labels))["passed"] is True


@pytest.mark.parametrize("probabilities", [np.zeros((4, 3)), np.ones((4, 4)), np.full((4, 4), np.nan)])
def test_invalid_probabilities_are_not_reported_as_metrics(probabilities):
    with pytest.raises(ValueError, match="Probabilities"):
        evaluate([0, 1, 2, 3], [0, 1, 2, 3], probabilities)


def test_mismatched_localization_evidence_cannot_be_silently_truncated():
    with pytest.raises(ValueError, match="matching counts"):
        localization_metrics([np.zeros((4, 4))], [])
    with pytest.raises(ValueError, match="matching shapes"):
        localization_metrics([np.zeros((4, 4))], [np.zeros((1, 4))])


def test_trained_failure_does_not_substitute_demo_risk(monkeypatch):
    monkeypatch.setattr(settings, "model_mode", "trained")
    service = ModelService()
    def failed(*args):
        raise RuntimeError("Invalid checkpoint")
    def forbidden(*args):
        pytest.fail("Trained-mode failure invoked the heuristic")
    monkeypatch.setattr(service, "_predict_trained", failed)
    monkeypatch.setattr(service, "_predict_baseline", forbidden)
    with pytest.raises(ValueError, match="no baseline result"):
        service.predict(Path("rgb.jpg"), Path("thermal.jpg"), {})
    assert "Invalid checkpoint" in service.status()["checkpoint"]["load_error"]
    assert service.status()["mode"] == "unavailable"


def test_checkpoint_existence_alone_does_not_mark_model_active(tmp_path, monkeypatch):
    checkpoint = tmp_path / "broken.pt"
    checkpoint.write_bytes(b"not a model")
    monkeypatch.setattr(settings, "model_mode", "trained")
    monkeypatch.setattr(settings, "model_checkpoint", str(checkpoint))
    state = ModelService().status()
    assert state["mode"] == "unavailable"
    assert state["validated"] is False
    assert state["gradcam"]["available"] is False


def test_successful_retry_clears_transient_inference_error(monkeypatch):
    monkeypatch.setattr(settings, "model_mode", "trained")
    service = ModelService()
    service._load_error = "Earlier invalid input"
    monkeypatch.setattr(service, "_predict_trained", lambda *args: {"risk_level": "NORMAL"})
    assert service.predict(Path("rgb.jpg"), Path("thermal.jpg"), {})["risk_level"] == "NORMAL"
    assert service._load_error is None


def test_heuristic_confidence_is_explicitly_not_accuracy(tmp_path):
    Image.new("L", (64, 64), 190).save(tmp_path / "thermal.png")
    result = ModelService()._predict_baseline(tmp_path / "thermal.png", dict(ambient_temperature=30, humidity=50))
    assert result["evidence"]["validated"] is False
    assert "not a probability" in result["evidence"]["confidence_type"]
    assert "not calibrated temperatures" in result["evidence"]["thermal_measurement"]


@pytest.mark.parametrize("frame", ["RGB", "THERMAL"])
def test_heatmap_stays_on_the_modality_that_generated_it(frame):
    rgb = np.full((128, 128, 3), (0, 0, 180), dtype=np.uint8)
    thermal = np.full((128, 128, 3), (100, 20, 0), dtype=np.uint8)
    heatmap = np.zeros((32, 32), dtype=float)
    heatmap[10:20, 10:20] = 1
    canvas = rgb if frame == "RGB" else thermal
    expected, _ = localization_overlay(canvas, heatmap, learned=True)
    overlay, region = inspection_localization(rgb, thermal, heatmap, frame)
    assert np.array_equal(overlay, expected)
    assert region["coordinate_frame"] == frame
