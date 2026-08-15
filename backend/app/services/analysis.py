from pathlib import Path
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.models.entities import Inspection, InspectionImage, InspectionEnvironment, Prediction, Alert, ImageType, RiskLevel
from app.ml.processing import preprocess,register,fuse,gradcam_overlay
from app.ml.inference import model_service

class InspectionAnalysisService:
 def __init__(self): self.statuses={}
 def stage(self,inspection_id,name,state="running"):
    current=self.statuses.setdefault(inspection_id,{"current":name,"stages":{}}); current["current"]=name; current["stages"][name]=state
 def status(self,inspection_id): return self.statuses.get(inspection_id,{"current":"pending","stages":{}})
 async def run(self,db:AsyncSession,inspection:Inspection):
    self.stage(inspection.id,"input_acquired")
    images=(await db.scalars(select(InspectionImage).where(InspectionImage.inspection_id==inspection.id))).all(); by_type={i.image_type.value:i for i in images}
    if "RGB" not in by_type or "THERMAL" not in by_type: raise HTTPException(422,"RGB and thermal evidence are required before analysis")
    inspection.status="PROCESSING"
    await db.commit()
    env=await db.scalar(select(InspectionEnvironment).where(InspectionEnvironment.inspection_id==inspection.id)); root=Path(by_type["RGB"].file_path).parent.parent
    self.stage(inspection.id,"input_acquired","complete"); self.stage(inspection.id,"preprocessing")
    rgb=preprocess(Path(by_type["RGB"].file_path),root/"rgb"/"processed.jpg"); thermal=preprocess(Path(by_type["THERMAL"].file_path),root/"thermal"/"processed.jpg",True)
    self.stage(inspection.id,"preprocessing","complete"); self.stage(inspection.id,"registration")
    aligned,registration_status,registration_confidence=register(rgb,thermal); (root/"fused").mkdir(exist_ok=True); (root/"gradcam").mkdir(exist_ok=True)
    cv2=__import__('cv2'); registered_path=root/"fused"/"registered_thermal.jpg"; cv2.imwrite(str(registered_path),aligned)
    self.stage(inspection.id,"registration","complete"); self.stage(inspection.id,"fusion")
    fused_path=root/"fused"/"fused.jpg"; cam_path=root/"gradcam"/"model_attributed_region.jpg"; cv2.imwrite(str(fused_path),fuse(rgb,aligned))
    self.stage(inspection.id,"fusion","complete"); self.stage(inspection.id,"inference")
    for typ,path in [(ImageType.FUSED,fused_path),(ImageType.GRADCAM,cam_path)]: db.add(InspectionImage(inspection_id=inspection.id,image_type=typ,file_path=str(path),width=512,height=512,metadata_json={"generated":True}))
    values={"ambient_temperature":env.ambient_temperature,"humidity":env.humidity,"weather":env.weather,"season":env.season,"time_of_day":env.time_of_day}
    result=model_service.predict(Path(by_type["RGB"].file_path),Path(by_type["THERMAL"].file_path),values); result["evidence"].update({"registration_status":registration_status,"registration_confidence":round(registration_confidence,3),"gradcam_label":"Model-attributed region"})
    self.stage(inspection.id,"inference","complete"); self.stage(inspection.id,"gradcam")
    cv2.imwrite(str(cam_path),gradcam_overlay(rgb,aligned))
    self.stage(inspection.id,"gradcam","complete"); self.stage(inspection.id,"risk_interpretation")
    prediction=Prediction(inspection_id=inspection.id,risk_level=RiskLevel(result["risk_level"]),confidence=result["confidence"],probabilities=result["class_probabilities"],explanation_metadata=result["evidence"],model_version=result["model_version"]); db.add(prediction)
    inspection.status="COMPLETED"; inspection.completed_at=datetime.utcnow(); inspection.model_version=result["model_version"]
    if result["risk_level"] in ("HIGH_RISK","CRITICAL"): db.add(Alert(inspection_id=inspection.id,severity=RiskLevel(result["risk_level"]),message=f"{result['risk_level'].replace('_',' ').title()} assessment requires operator review."))
    await db.commit(); self.stage(inspection.id,"risk_interpretation","complete"); self.statuses[inspection.id]["current"]="complete"; return result
analysis_service=InspectionAnalysisService()
