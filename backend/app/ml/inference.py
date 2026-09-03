"""Runtime model selection with an honest heuristic fallback."""

from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

import cv2
import numpy as np

from app.core.config import settings


RISK_CLASSES = ["NORMAL", "WARNING", "HIGH_RISK", "CRITICAL"]
CATEGORIES = {
    "weather": ("clear", "cloudy", "rain", "windy", "unknown"),
    "season": ("summer", "monsoon", "winter", "spring", "unknown"),
    "time_of_day": ("morning", "afternoon", "evening", "night", "unknown"),
    "sun_exposure": ("none", "low", "partial", "direct", "unknown"),
}


def _normalise(value: object) -> str:
    return str(value or "unknown").strip().lower().replace(" ", "_")


def _environment_vector(environment: dict) -> np.ndarray:
    values = [
        float(np.clip((float(environment["ambient_temperature"]) - 20.0) / 60.0, -1, 1)),
        float(np.clip(float(environment["humidity"]) / 100.0, 0, 1)),
    ]
    for field, options in CATEGORIES.items():
        selected = _normalise(environment.get(field))
        if selected not in options:
            selected = "unknown"
        values.extend(float(selected == option) for option in options)
    return np.asarray(values, dtype=np.float32)


def _dataset_status(path_value: str) -> dict:
    path = Path(path_value)
    if not path.is_file():
        return {
            "ready": False,
            "labelled": False,
            "sample_count": 0,
            "reason": "No labelled RGB/thermal manifest is configured.",
        }
    try:
        with path.open(newline="", encoding="utf-8") as source:
            rows = list(csv.DictReader(source))
        required = {"rgb_path", "thermal_path", "label", "split"}
        if not rows or not required.issubset(rows[0]):
            raise ValueError("The manifest is empty or incomplete")
        return {
            "ready": True,
            "labelled": True,
            "sample_count": len(rows),
            "context_is_associated_metadata": True,
        }
    except (OSError, ValueError, csv.Error) as exc:
        return {
            "ready": False,
            "labelled": False,
            "sample_count": 0,
            "reason": str(exc),
        }


class ModelService:
    baseline_version = "baseline-heuristic-v1"

    def __init__(self) -> None:
        self._model = None
        self._checkpoint_metadata: dict = {}
        self._load_error: str | None = None

    @property
    def checkpoint_path(self) -> Path:
        return Path(settings.model_checkpoint) if settings.model_checkpoint else Path("__missing__")

    def status(self) -> dict:
        checkpoint_exists = bool(settings.model_checkpoint) and self.checkpoint_path.is_file()
        trained_requested = settings.model_mode.lower() == "trained"
        runtime_available = importlib.util.find_spec("torch") is not None
        trained_active = (
            trained_requested
            and checkpoint_exists
            and runtime_available
            and self._load_error is None
        )
        return {
            "mode": "trained" if trained_active else "baseline",
            "requested_mode": settings.model_mode,
            "validated": bool(self._checkpoint_metadata.get("validated", False)) if trained_active else False,
            "version": self._checkpoint_metadata.get("experiment_id", "multimodal-cnn")
            if trained_active
            else self.baseline_version,
            "architecture": {
                "rgb": "ResNet-18 CNN branch",
                "thermal": "ResNet-18 CNN branch",
                "environment": "Associated-context MLP",
                "fusion": "Feature concatenation + classifier",
            },
            "checkpoint": {
                "configured": bool(settings.model_checkpoint),
                "available": checkpoint_exists,
                "runtime_available": runtime_available,
                "load_error": self._load_error,
            },
            "dataset": _dataset_status(settings.dataset_manifest),
            "gradcam": {
                "available": trained_active,
                "method": "true gradient-weighted class activation mapping"
                if trained_active
                else "baseline thermal saliency visualization",
            },
            "research_state": "validated checkpoint active"
            if trained_active and self._checkpoint_metadata.get("validated")
            else "software baseline; labelled training required",
        }

    def _load_trained_model(self):
        if self._model is not None:
            return self._model
        if not self.checkpoint_path.is_file():
            raise FileNotFoundError("MODEL_CHECKPOINT does not reference a checkpoint")
        try:
            import torch

            from app.ml.model import MultimodalAnomalyNet

            checkpoint = torch.load(self.checkpoint_path, map_location="cpu", weights_only=True)
            model = MultimodalAnomalyNet(
                modality=checkpoint.get("modality", "fusion_env"),
                dropout=float(checkpoint.get("dropout", 0.3)),
            )
            model.load_state_dict(checkpoint["state_dict"])
            model.eval()
            self._model = model
            self._checkpoint_metadata = {
                key: checkpoint.get(key)
                for key in ("validated", "metrics", "experiment_id", "image_size", "modality")
            }
            self._load_error = None
            return model
        except Exception as exc:
            self._load_error = f"{type(exc).__name__}: {exc}"
            raise

    def _predict_trained(self, rgb_path: Path, thermal_path: Path, environment: dict) -> dict:
        import torch
        from PIL import Image
        from torchvision.transforms import functional as TF

        from app.ml.model import GradCAM

        model = self._load_trained_model()
        size = int(self._checkpoint_metadata.get("image_size") or 224)
        rgb_image = TF.resize(Image.open(rgb_path).convert("RGB"), [size, size], antialias=True)
        thermal_image = TF.resize(
            Image.open(thermal_path).convert("L"), [size, size], antialias=True
        )
        rgb = TF.normalize(
            TF.to_tensor(rgb_image), mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)
        ).unsqueeze(0)
        thermal = TF.normalize(
            TF.to_tensor(thermal_image), mean=(0.5,), std=(0.25,)
        ).unsqueeze(0)
        context = torch.from_numpy(_environment_vector(environment)).unsqueeze(0)
        with torch.no_grad():
            probabilities = model(rgb, thermal, context).softmax(dim=1)[0]
        prediction = int(probabilities.argmax().item())
        branch = "rgb" if self._checkpoint_metadata.get("modality") == "rgb" else "thermal"
        gradcam = GradCAM(model, branch=branch)
        try:
            localization = gradcam(rgb, thermal, context, prediction).heatmap
        finally:
            gradcam.close()
        confidence = float(probabilities[prediction].item())
        return {
            "risk_level": RISK_CLASSES[prediction],
            "confidence": round(confidence, 4),
            "class_probabilities": {
                name: round(float(value), 4)
                for name, value in zip(RISK_CLASSES, probabilities.tolist())
            },
            "model_version": self._checkpoint_metadata.get("experiment_id") or "multimodal-cnn",
            "evidence": {
                "output_type": "LEARNED_MULTIMODAL_CLASSIFICATION",
                "architecture": "RGB CNN + thermal CNN + associated environmental context",
                "gradcam_method": "true Grad-CAM from trained CNN activations and gradients",
                "validated": bool(self._checkpoint_metadata.get("validated")),
            },
            "_gradcam_heatmap": localization,
        }

    def _predict_baseline(self, thermal_path: Path, environment: dict) -> dict:
        thermal = cv2.imread(str(thermal_path), cv2.IMREAD_GRAYSCALE)
        if thermal is None:
            raise ValueError("Thermal image could not be decoded")
        p95 = float(np.percentile(thermal, 95)) / 255
        mean = float(thermal.mean()) / 255
        spread = float(thermal.std()) / 255
        hotspot_threshold = max(
            float(np.percentile(thermal, 90)), float(thermal.mean() + thermal.std())
        )
        hotspot_ratio = float(np.mean(thermal >= hotspot_threshold))
        blurred = cv2.GaussianBlur(thermal, (31, 31), 0)
        local_contrast = float(np.percentile(cv2.absdiff(thermal, blurred), 95)) / 255
        ambient = max(0, min(1, (environment["ambient_temperature"] - 20) / 60))
        humidity = max(0, min(1, environment["humidity"] / 100))
        score = min(
            0.98,
            max(
                0.02,
                0.30 * p95
                + 0.18 * mean
                + 0.16 * spread
                + 0.20 * local_contrast
                + 0.08 * min(1, hotspot_ratio * 10)
                + 0.06 * ambient
                + 0.02 * humidity,
            ),
        )
        thresholds = [0.33, 0.50, 0.68]
        index = 0 if score < thresholds[0] else 1 if score < thresholds[1] else 2 if score < thresholds[2] else 3
        centers = np.array([0.20, 0.41, 0.59, 0.79])
        weights = np.exp(-np.abs(centers - score) * 8)
        probabilities = weights / weights.sum()
        return {
            "risk_level": RISK_CLASSES[index],
            "confidence": round(score, 4),
            "class_probabilities": {
                key: round(float(value), 4)
                for key, value in zip(RISK_CLASSES, probabilities)
            },
            "model_version": self.baseline_version,
            "evidence": {
                "output_type": "HEURISTIC_RISK_SCORE",
                "heuristic_score": round(score, 4),
                "thermal_intensity_mean": round(mean, 4),
                "thermal_intensity_p95": round(p95, 4),
                "thermal_texture_spread": round(spread, 4),
                "hotspot_region_proportion": round(hotspot_ratio, 4),
                "local_hotspot_contrast": round(local_contrast, 4),
                "environment_normalization": {
                    "ambient": round(ambient, 4),
                    "humidity": round(humidity, 4),
                },
                "gradcam_method": "unavailable on heuristic baseline",
                "mode_note": "Deterministic comparison baseline; not engineering validated.",
            },
        }

    def predict(self, rgb_path: Path, thermal_path: Path, environment: dict) -> dict:
        if settings.model_mode.lower() == "trained":
            try:
                return self._predict_trained(rgb_path, thermal_path, environment)
            except Exception:
                result = self._predict_baseline(thermal_path, environment)
                result["evidence"]["trained_fallback_reason"] = self._load_error
                return result
        return self._predict_baseline(thermal_path, environment)


model_service = ModelService()
