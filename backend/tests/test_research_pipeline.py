import numpy as np
import pytest

from app.ml.processing import localization_overlay
from app.services.notifications import policy_for
from ml_training.evaluate import evaluate, localization_metrics


def test_notification_policy_matches_risk_tiers():
    assert policy_for("NORMAL") == {
        "dashboard": False,
        "email": False,
        "prominent": False,
    }
    assert policy_for("WARNING")["dashboard"] is True
    assert policy_for("WARNING")["email"] is False
    assert policy_for("HIGH_RISK")["email"] is True
    assert policy_for("CRITICAL")["prominent"] is True


def test_evaluation_reports_real_classification_and_localization_metrics():
    labels = [0, 1, 2, 3]
    probabilities = np.eye(4)
    metrics = evaluate(labels, labels, probabilities)
    assert metrics["accuracy"] == 1.0
    assert metrics["precision_macro"] == 1.0
    assert metrics["recall_macro"] == 1.0
    assert metrics["f1_macro"] == 1.0
    assert metrics["roc_auc_ovr_macro"] == 1.0
    assert metrics["confusion_matrix"] == np.eye(4, dtype=int).tolist()

    mask = np.zeros((24, 24), dtype=np.uint8)
    mask[5:12, 7:16] = 1
    localization = localization_metrics([mask], [mask])
    assert localization["mean_iou"] == 1.0
    assert localization["mean_dice"] == 1.0


def test_localization_overlay_returns_operator_region():
    rgb = np.zeros((128, 128, 3), dtype=np.uint8)
    heatmap = np.zeros((32, 32), dtype=np.float32)
    heatmap[10:18, 12:20] = 1
    overlay, region = localization_overlay(rgb, heatmap, learned=True)
    assert overlay.shape == rgb.shape
    assert region["localization_method"] == "true_gradcam"
    assert region["instruction"] == "Inspect this highlighted area."
    assert region["bounding_box"]["width"] > 0


def test_dual_branch_network_and_true_gradcam():
    torch = pytest.importorskip("torch")
    from app.ml.model import GradCAM, MultimodalAnomalyNet

    model = MultimodalAnomalyNet(modality="fusion_env")
    model.eval()
    rgb = torch.randn(1, 3, 64, 64)
    thermal = torch.randn(1, 1, 64, 64)
    environment = torch.randn(1, 22)
    logits = model(rgb, thermal, environment)
    assert logits.shape == (1, 4)
    gradcam = GradCAM(model, branch="thermal")
    try:
        result = gradcam(rgb, thermal, environment)
    finally:
        gradcam.close()
    assert result.heatmap.shape == (64, 64)
    assert 0 <= result.target_class < 4
    assert float(result.heatmap.min()) >= 0
    assert float(result.heatmap.max()) <= 1

