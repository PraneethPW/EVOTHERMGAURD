"""Research metrics calculated only from held-out labelled observations."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.preprocessing import label_binarize

from app.ml.constants import RISK_CLASSES


def localization_metrics(predicted_masks, target_masks, threshold: float = 0.5) -> dict:
    if len(predicted_masks) != len(target_masks) or not 0 <= threshold <= 1:
        raise ValueError("Localization masks must have matching counts and a threshold in [0, 1]")
    ious, dice_scores = [], []
    for predicted, target in zip(predicted_masks, target_masks):
        if np.asarray(predicted).shape != np.asarray(target).shape:
            raise ValueError("Localization masks must have matching shapes")
        if not np.isfinite(predicted).all() or not np.isfinite(target).all():
            raise ValueError("Localization masks must contain finite values")
        predicted = np.asarray(predicted) >= threshold
        target = np.asarray(target) > 0
        intersection = np.logical_and(predicted, target).sum()
        union = np.logical_or(predicted, target).sum()
        ious.append(float(intersection / union) if union else 1.0)
        denominator = predicted.sum() + target.sum()
        dice_scores.append(float(2 * intersection / denominator) if denominator else 1.0)
    return {
        "samples": len(ious),
        "mean_iou": round(float(np.mean(ious)), 6) if ious else None,
        "mean_dice": round(float(np.mean(dice_scores)), 6) if dice_scores else None,
    }


def evaluate(
    y_true,
    y_pred,
    probabilities=None,
    predicted_masks=None,
    target_masks=None,
) -> dict:
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    labels = list(range(len(RISK_CLASSES)))
    if y_true.ndim != 1 or y_pred.shape != y_true.shape or not y_true.size:
        raise ValueError("Labels and predictions must be nonempty vectors of matching length")
    if not np.isin(y_true, labels).all() or not np.isin(y_pred, labels).all():
        raise ValueError("Labels and predictions must use the four risk-class indices")
    if probabilities is not None:
        probabilities = np.asarray(probabilities, dtype=float)
        if (probabilities.shape != (len(y_true), len(labels))
            or not np.isfinite(probabilities).all()
            or (probabilities < 0).any() or (probabilities > 1).any()
            or not np.allclose(probabilities.sum(axis=1), 1, atol=1e-5)):
            raise ValueError("Probabilities must be finite normalized N-by-4 values")
    support = {name: int((y_true == index).sum()) for index, name in enumerate(RISK_CLASSES)}
    per_class_recall = recall_score(y_true, y_pred, labels=labels, average=None, zero_division=0)
    result = {
        "sample_count": int(len(y_true)),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 6),
        "precision_macro": round(
            float(precision_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)), 6
        ),
        "recall_macro": round(
            float(recall_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)), 6
        ),
        "f1_macro": round(
            float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)), 6
        ),
        "confusion_matrix": confusion_matrix(
            y_true, y_pred, labels=list(range(len(RISK_CLASSES)))
        ).tolist(),
        "class_names": list(RISK_CLASSES),
        "class_support": support,
        "class_recall": {name: round(float(value), 6) if support[name] else None for name, value in zip(RISK_CLASSES, per_class_recall)},
        "all_classes_present": all(support.values()),
        "critical_missed": int(((y_true == 3) & (y_pred != 3)).sum()),
        "roc_auc_ovr_macro": None,
    }
    if probabilities is not None and len(np.unique(y_true)) > 1:
        try:
            targets = label_binarize(y_true, classes=list(range(len(RISK_CLASSES))))
            result["roc_auc_ovr_macro"] = round(
                float(
                    roc_auc_score(
                        targets,
                        np.asarray(probabilities),
                        average="macro",
                        multi_class="ovr",
                    )
                ),
                6,
            )
        except ValueError:
            # A held-out split may not contain every class; report unavailable rather than
            # manufacturing a number.
            pass
    if (predicted_masks is None) != (target_masks is None):
        raise ValueError("Supply both predicted and target localization masks")
    if predicted_masks is not None and target_masks is not None:
        result["localization"] = localization_metrics(predicted_masks, target_masks)
    else:
        result["localization"] = {
            "samples": 0,
            "mean_iou": None,
            "mean_dice": None,
            "reason": "No localization masks were supplied.",
        }
    return result
