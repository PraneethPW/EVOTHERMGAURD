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

from app.ml.model import RISK_CLASSES


def localization_metrics(predicted_masks, target_masks, threshold: float = 0.5) -> dict:
    ious, dice_scores = [], []
    for predicted, target in zip(predicted_masks, target_masks):
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
    result = {
        "sample_count": int(len(y_true)),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 6),
        "precision_macro": round(
            float(precision_score(y_true, y_pred, average="macro", zero_division=0)), 6
        ),
        "recall_macro": round(
            float(recall_score(y_true, y_pred, average="macro", zero_division=0)), 6
        ),
        "f1_macro": round(
            float(f1_score(y_true, y_pred, average="macro", zero_division=0)), 6
        ),
        "confusion_matrix": confusion_matrix(
            y_true, y_pred, labels=list(range(len(RISK_CLASSES)))
        ).tolist(),
        "class_names": list(RISK_CLASSES),
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
