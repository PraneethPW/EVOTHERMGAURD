"""Project acceptance targets, separate from evaluation or engineering approval."""

import math

from app.ml.constants import RISK_CLASSES


def quality_gate(metrics: dict, *, minimum_macro_f1: float = 0.95,
                 minimum_critical_recall: float = 0.98,
                 minimum_samples_per_class: int = 50) -> dict:
    if not (0 < minimum_macro_f1 <= 1 and 0 < minimum_critical_recall <= 1
            and minimum_samples_per_class > 0):
        raise ValueError("Quality targets must be positive probabilities and sample counts")
    reasons = []
    support = metrics.get("class_support", {})
    if any(support.get(label, 0) < minimum_samples_per_class for label in RISK_CLASSES):
        reasons.append("Insufficient held-out examples in one or more risk classes")
    macro_f1 = metrics.get("f1_macro", 0)
    if not math.isfinite(macro_f1) or macro_f1 < minimum_macro_f1:
        reasons.append("Four-class macro F1 is below the project target")
    critical_recall = metrics.get("class_recall", {}).get("CRITICAL")
    if critical_recall is None or not math.isfinite(critical_recall) or critical_recall < minimum_critical_recall:
        reasons.append("Critical recall is unavailable or below the project target")
    return {
        "passed": not reasons,
        "minimum_macro_f1": minimum_macro_f1,
        "minimum_critical_recall": minimum_critical_recall,
        "minimum_samples_per_class": minimum_samples_per_class,
        "reasons": reasons,
        "scope": "Project test-set acceptance targets; not engineering certification or a guarantee on new assets",
    }
