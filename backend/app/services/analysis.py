from datetime import datetime
from pathlib import Path

import cv2
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.inference import model_service
from app.ml.processing import (
    baseline_saliency_overlay,
    fuse,
    localization_overlay,
    preprocess,
    register,
)
from app.models.entities import (
    Alert,
    ImageType,
    Inspection,
    InspectionEnvironment,
    InspectionImage,
    Prediction,
    RiskLevel,
    User,
)
from app.services.notifications import policy_for, queue_risk_email


class InspectionAnalysisService:
    def __init__(self) -> None:
        self.statuses: dict[str, dict] = {}

    def stage(self, inspection_id: str, name: str, state: str = "running") -> None:
        current = self.statuses.setdefault(inspection_id, {"current": name, "stages": {}})
        current["current"] = name
        current["stages"][name] = state

    def status(self, inspection_id: str) -> dict:
        return self.statuses.get(inspection_id, {"current": "pending", "stages": {}})

    async def run(self, db: AsyncSession, inspection: Inspection) -> dict:
        self.stage(inspection.id, "input_acquired")
        images = (
            await db.scalars(
                select(InspectionImage).where(InspectionImage.inspection_id == inspection.id)
            )
        ).all()
        by_type = {image.image_type.value: image for image in images}
        if "RGB" not in by_type or "THERMAL" not in by_type:
            raise HTTPException(
                422, "RGB and thermal evidence are required before analysis"
            )

        inspection.status = "PROCESSING"
        await db.commit()
        environment = await db.scalar(
            select(InspectionEnvironment).where(
                InspectionEnvironment.inspection_id == inspection.id
            )
        )
        if environment is None:
            raise HTTPException(422, "Associated environmental context is required")
        root = Path(by_type["RGB"].file_path).parent.parent

        self.stage(inspection.id, "input_acquired", "complete")
        self.stage(inspection.id, "preprocessing")
        rgb = preprocess(Path(by_type["RGB"].file_path), root / "rgb" / "processed.jpg")
        thermal = preprocess(
            Path(by_type["THERMAL"].file_path),
            root / "thermal" / "processed.jpg",
            True,
        )

        self.stage(inspection.id, "preprocessing", "complete")
        self.stage(inspection.id, "registration")
        aligned, registration_status, registration_confidence = register(rgb, thermal)
        (root / "fused").mkdir(exist_ok=True)
        (root / "gradcam").mkdir(exist_ok=True)
        registered_path = root / "fused" / "registered_thermal.jpg"
        cv2.imwrite(str(registered_path), aligned)

        self.stage(inspection.id, "registration", "complete")
        self.stage(inspection.id, "fusion")
        fused_path = root / "fused" / "fused.jpg"
        cv2.imwrite(str(fused_path), fuse(rgb, aligned))

        self.stage(inspection.id, "fusion", "complete")
        self.stage(inspection.id, "inference")
        values = {
            "ambient_temperature": environment.ambient_temperature,
            "humidity": environment.humidity,
            "weather": environment.weather,
            "season": environment.season,
            "time_of_day": environment.time_of_day,
            "sun_exposure": environment.sun_exposure,
        }
        result = model_service.predict(
            Path(by_type["RGB"].file_path),
            Path(by_type["THERMAL"].file_path),
            values,
        )
        heatmap = result.pop("_gradcam_heatmap", None)

        self.stage(inspection.id, "inference", "complete")
        self.stage(inspection.id, "gradcam")
        if heatmap is not None:
            localized, localization = localization_overlay(rgb, heatmap, learned=True)
            gradcam_label = "True Grad-CAM / inspect highlighted area"
        else:
            localized, localization = baseline_saliency_overlay(rgb, aligned)
            gradcam_label = "Baseline thermal saliency / not CNN Grad-CAM"
        cam_path = root / "gradcam" / "localized_anomaly_region.jpg"
        cv2.imwrite(str(cam_path), localized)
        db.add_all(
            [
                InspectionImage(
                    inspection_id=inspection.id,
                    image_type=ImageType.FUSED,
                    file_path=str(fused_path),
                    width=512,
                    height=512,
                    metadata_json={"generated": True, "method": "registered_rgb_thermal_fusion"},
                ),
                InspectionImage(
                    inspection_id=inspection.id,
                    image_type=ImageType.GRADCAM,
                    file_path=str(cam_path),
                    width=512,
                    height=512,
                    metadata_json={
                        "generated": True,
                        "method": localization["localization_method"],
                        "label": gradcam_label,
                        "region": localization,
                    },
                ),
            ]
        )

        self.stage(inspection.id, "gradcam", "complete")
        self.stage(inspection.id, "risk_interpretation")
        risk = result["risk_level"]
        notification_policy = policy_for(risk)
        result["evidence"].update(
            {
                "registration_status": registration_status,
                "registration_confidence": round(registration_confidence, 3),
                "gradcam_label": gradcam_label,
                "localized_region": localization,
                "notification_policy": notification_policy,
            }
        )
        prediction = Prediction(
            inspection_id=inspection.id,
            risk_level=RiskLevel(risk),
            confidence=result["confidence"],
            probabilities=result["class_probabilities"],
            explanation_metadata=result["evidence"],
            model_version=result["model_version"],
        )
        db.add(prediction)
        inspection.status = "COMPLETED"
        inspection.completed_at = datetime.utcnow()
        inspection.model_version = result["model_version"]
        if notification_policy["dashboard"]:
            prefix = "IMMEDIATE REVIEW" if notification_policy["prominent"] else "OPERATOR REVIEW"
            db.add(
                Alert(
                    inspection_id=inspection.id,
                    severity=RiskLevel(risk),
                    message=(
                        f"{prefix}: {risk.replace('_', ' ').title()} assessment for "
                        f"{inspection.equipment.equipment_name}. Inspect the highlighted region."
                    ),
                )
            )
        await db.commit()

        owner = await db.scalar(select(User).where(User.id == inspection.user_id))
        delivery = queue_risk_email(
            owner.email if owner else "",
            risk,
            inspection.equipment.equipment_name,
            inspection.id,
        )
        prediction.explanation_metadata = {
            **prediction.explanation_metadata,
            "notification_delivery": delivery,
        }
        await db.commit()
        result["evidence"] = prediction.explanation_metadata
        self.stage(inspection.id, "risk_interpretation", "complete")
        self.statuses[inspection.id]["current"] = "complete"
        return result


analysis_service = InspectionAnalysisService()
