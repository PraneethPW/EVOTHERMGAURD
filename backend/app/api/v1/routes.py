from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from uuid import uuid4
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.api.deps import current_user
from app.core.security import hash_password,verify_password,create_token
from app.models.entities import User,Equipment,Inspection,InspectionEnvironment,InspectionImage,Prediction,Alert,MaintenanceFeedback,ImageType,AIAnalysis
from app.schemas.schemas import RegisterIn,LoginIn,UserOut,TokenOut,EquipmentIn,EquipmentOut,InspectionIn,FeedbackIn
from app.services.storage import save_upload
from app.services.analysis import analysis_service
from app.ml.inference import model_service
from app.integrations.openrouter import explain, fallback_explanation
import asyncio

router=APIRouter()

STARTER_EQUIPMENT=(
 {"equipment_name":"Transformer T-01","equipment_type":"Distribution Transformer","asset_code":"DEMO-TR-01","location_label":"North Substation","manufacturer":"ABB","notes":"Starter asset for thermal inspection practice."},
 {"equipment_name":"Feeder Motor M-204","equipment_type":"Motor","asset_code":"DEMO-M-204","location_label":"Pump Hall A","manufacturer":"Siemens","notes":"Starter asset for multispectral inspection practice."},
 {"equipment_name":"Main Switchgear SG-12","equipment_type":"Electrical Switchgear","asset_code":"DEMO-SG-12","location_label":"Control Room","manufacturer":"Schneider Electric","notes":"Starter asset for thermal inspection practice."},
 {"equipment_name":"Cooling Pump P-07","equipment_type":"Industrial Pump","asset_code":"DEMO-P-07","location_label":"Process Bay 2","manufacturer":"Grundfos","notes":"Starter asset for multispectral inspection practice."},
 {"equipment_name":"Generator G-03","equipment_type":"Generator","asset_code":"DEMO-G-03","location_label":"Power Station","manufacturer":"Cummins","notes":"Starter asset for thermal inspection practice."},
)

async def ensure_starter_equipment(user:User,db:AsyncSession):
 existing=await db.scalar(select(Equipment.id).where(Equipment.user_id==user.id).limit(1))
 if existing: return
 db.add_all([Equipment(user_id=user.id,**asset) for asset in STARTER_EQUIPMENT])
 await db.commit()

@router.get('/health')
async def health(): return {"api":"ok","model":model_service.status(),"openrouter_configured":bool(__import__('app.core.config',fromlist=['settings']).settings.openrouter_api_key)}
@router.post('/auth/register',response_model=TokenOut)
async def register(body:RegisterIn,db:AsyncSession=Depends(get_db)):
 if await db.scalar(select(User).where(User.email==body.email.lower())): raise HTTPException(409,"Email is already registered")
 user=User(name=body.name,email=body.email.lower(),password_hash=hash_password(body.password)); db.add(user); await db.commit(); await db.refresh(user); return TokenOut(access_token=create_token(user.id),user=user)
@router.post('/auth/login',response_model=TokenOut)
async def login(body:LoginIn,db:AsyncSession=Depends(get_db)):
 user=await db.scalar(select(User).where(User.email==body.email.lower()))
 if not user or not verify_password(body.password,user.password_hash): raise HTTPException(401,"Invalid email or password")
 return TokenOut(access_token=create_token(user.id),user=user)
@router.get('/auth/me',response_model=UserOut)
async def me(user:User=Depends(current_user)): return user
@router.get('/equipment',response_model=list[EquipmentOut])
async def equipment_list(user:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
 await ensure_starter_equipment(user,db)
 return (await db.scalars(select(Equipment).where(Equipment.user_id==user.id).order_by(Equipment.created_at.desc()))).all()
@router.post('/equipment',response_model=EquipmentOut)
async def equipment_create(body:EquipmentIn,user:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
 item=Equipment(user_id=user.id,**body.model_dump()); db.add(item); await db.commit(); await db.refresh(item); return item
@router.get('/equipment/{equipment_id}')
async def equipment_detail(equipment_id:str,user:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
 item=await db.scalar(select(Equipment).where(Equipment.id==equipment_id,Equipment.user_id==user.id))
 if not item: raise HTTPException(404,"Equipment not found")
 runs=(await db.scalars(select(Inspection).where(Inspection.equipment_id==item.id,Inspection.user_id==user.id).order_by(Inspection.created_at.desc()))).all()
 history=[]
 for run in runs:
  pred=await db.scalar(select(Prediction).where(Prediction.inspection_id==run.id))
  history.append({"id":run.id,"created_at":run.created_at,"status":run.status,"risk_level":pred.risk_level.value if pred else None,"confidence":pred.confidence if pred else None})
 return {"id":item.id,"equipment_name":item.equipment_name,"equipment_type":item.equipment_type,"asset_code":item.asset_code,"location_label":item.location_label,"manufacturer":item.manufacturer,"notes":item.notes,"created_at":item.created_at,"inspection_count":len(history),"latest_risk":history[0]["risk_level"] if history else None,"inspections":history}
@router.post('/inspections')
async def inspection_create(body:InspectionIn,user:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
 eq=await db.scalar(select(Equipment).where(Equipment.id==body.equipment_id,Equipment.user_id==user.id))
 if not eq: raise HTTPException(404,"Equipment not found")
 data=body.model_dump(); inspection=Inspection(id=str(uuid4()),user_id=user.id,equipment_id=body.equipment_id); env=InspectionEnvironment(inspection_id=inspection.id,**{k:data[k] for k in data if k!='equipment_id'}); db.add_all([inspection,env]); await db.commit(); return {"id":inspection.id,"status":inspection.status}
@router.post('/inspections/{inspection_id}/images')
async def inspection_images(inspection_id:str,rgb:UploadFile=File(...),thermal:UploadFile=File(...),user:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
 inspection=await db.scalar(select(Inspection).where(Inspection.id==inspection_id,Inspection.user_id==user.id));
 if not inspection: raise HTTPException(404,"Inspection not found")
 result=[]
 for typ,file in [(ImageType.RGB,rgb),(ImageType.THERMAL,thermal)]:
  path,w,h,meta=await save_upload(inspection_id,typ.value,file); record=InspectionImage(inspection_id=inspection_id,image_type=typ,file_path=str(path),width=w,height=h,metadata_json=meta); db.add(record); result.append({"type":typ.value,"path":str(path),"width":w,"height":h})
 await db.commit(); return {"images":result}
@router.post('/inspections/{inspection_id}/analyze')
async def inspection_analyze(inspection_id:str,user:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
 inspection=await db.scalar(select(Inspection).where(Inspection.id==inspection_id,Inspection.user_id==user.id));
 if not inspection: raise HTTPException(404,"Inspection not found")
 if await db.scalar(select(Prediction).where(Prediction.inspection_id==inspection_id)): raise HTTPException(409,"Inspection already analysed; preserve history by creating a new inspection")
 return await analysis_service.run(db,inspection)
@router.get('/inspections/{inspection_id}/processing-status')
async def processing_status(inspection_id:str,user:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
 inspection=await db.scalar(select(Inspection).where(Inspection.id==inspection_id,Inspection.user_id==user.id))
 if not inspection: raise HTTPException(404,"Inspection not found")
 return analysis_service.status(inspection_id)
async def detail(inspection_id,user,db):
 inspection=await db.scalar(select(Inspection).where(Inspection.id==inspection_id,Inspection.user_id==user.id));
 if not inspection: raise HTTPException(404,"Inspection not found")
 env=await db.scalar(select(InspectionEnvironment).where(InspectionEnvironment.inspection_id==inspection_id)); pred=await db.scalar(select(Prediction).where(Prediction.inspection_id==inspection_id)); imgs=(await db.scalars(select(InspectionImage).where(InspectionImage.inspection_id==inspection_id))).all(); feedback=(await db.scalars(select(MaintenanceFeedback).where(MaintenanceFeedback.inspection_id==inspection_id))).all()
 return {"id":inspection.id,"status":inspection.status,"created_at":inspection.created_at,"completed_at":inspection.completed_at,"model_version":inspection.model_version,"equipment":{"id":inspection.equipment.id,"name":inspection.equipment.equipment_name,"type":inspection.equipment.equipment_type,"asset_code":inspection.equipment.asset_code,"location":inspection.equipment.location_label},"environment":env,"prediction":pred,"images":[{"type":i.image_type.value,"url":"/evidence/"+i.file_path.replace('\\','/').split('/storage/')[-1],"width":i.width,"height":i.height,"metadata":i.metadata_json} for i in imgs],"feedback":feedback,"model_status":model_service.status(),"recommended_action":action_for(pred.risk_level.value if pred else None)}
@router.get('/inspections')
async def inspections(risk:str|None=None,equipment_id:str|None=None,search:str|None=None,user:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
 stmt=select(Inspection).where(Inspection.user_id==user.id).order_by(Inspection.created_at.desc())
 if equipment_id: stmt=stmt.where(Inspection.equipment_id==equipment_id)
 items=(await db.scalars(stmt)).all(); result=[]
 for i in items:
  pred=await db.scalar(select(Prediction).where(Prediction.inspection_id==i.id)); env=await db.scalar(select(InspectionEnvironment).where(InspectionEnvironment.inspection_id==i.id)); imgs=(await db.scalars(select(InspectionImage).where(InspectionImage.inspection_id==i.id))).all()
  if risk and (not pred or pred.risk_level.value!=risk): continue
  if search and search.lower() not in i.equipment.equipment_name.lower(): continue
  result.append({"id":i.id,"created_at":i.created_at,"completed_at":i.completed_at,"status":i.status,"equipment_id":i.equipment_id,"equipment_name":i.equipment.equipment_name,"equipment_type":i.equipment.equipment_type,"model_version":i.model_version,"prediction":pred,"environment":{"ambient_temperature":env.ambient_temperature,"humidity":env.humidity,"weather":env.weather,"season":env.season,"time_of_day":env.time_of_day} if env else None,"thumbnail":next(("/evidence/"+x.file_path.replace('\\','/').split('/storage/')[-1] for x in imgs if x.image_type==ImageType.GRADCAM),None)})
 return result
@router.get('/inspections/{inspection_id}')
async def inspection_detail(inspection_id:str,user:User=Depends(current_user),db:AsyncSession=Depends(get_db)): return await detail(inspection_id,user,db)
@router.get('/inspections/{inspection_id}/result')
async def inspection_result(inspection_id:str,user:User=Depends(current_user),db:AsyncSession=Depends(get_db)): return await detail(inspection_id,user,db)
@router.post('/inspections/{inspection_id}/feedback')
async def feedback(inspection_id:str,body:FeedbackIn,user:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
 await detail(inspection_id,user,db); record=MaintenanceFeedback(inspection_id=inspection_id,**body.model_dump()); db.add(record); await db.commit(); return {"id":record.id}
@router.get('/alerts')
async def alerts(user:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
 return (await db.scalars(select(Alert).join(Inspection).where(Inspection.user_id==user.id).order_by(Alert.created_at.desc()))).all()
@router.get('/dashboard')
async def dashboard(user:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
 runs=(await db.scalars(select(Inspection).where(Inspection.user_id==user.id).order_by(Inspection.created_at.desc()))).all(); equipment=(await db.scalars(select(Equipment).where(Equipment.user_id==user.id).order_by(Equipment.created_at.desc()))).all(); alerts=(await db.scalars(select(Alert).join(Inspection).where(Inspection.user_id==user.id).order_by(Alert.created_at.desc()))).all(); distribution={k:0 for k in ["NORMAL","WARNING","HIGH_RISK","CRITICAL"]}; recent=[]; activity=[]; latest_by_equipment={}
 for run in runs:
  pred=await db.scalar(select(Prediction).where(Prediction.inspection_id==run.id)); env=await db.scalar(select(InspectionEnvironment).where(InspectionEnvironment.inspection_id==run.id))
  if pred: distribution[pred.risk_level.value]+=1
  row={"id":run.id,"status":run.status,"equipment":run.equipment.equipment_name,"equipment_id":run.equipment_id,"created_at":run.created_at,"risk_level":pred.risk_level.value if pred else None,"confidence":pred.confidence if pred else None,"model_version":run.model_version,"environment":{"ambient_temperature":env.ambient_temperature,"humidity":env.humidity,"weather":env.weather} if env else None}
  if len(recent)<6: recent.append(row)
  activity.append({"date":run.created_at.isoformat(),"risk_level":row["risk_level"],"confidence":row["confidence"]})
  latest_by_equipment.setdefault(run.equipment_id,row)
 equipment_matrix=[{"id":e.id,"name":e.equipment_name,"type":e.equipment_type,"asset_code":e.asset_code,"location":e.location_label,"latest":latest_by_equipment.get(e.id)} for e in equipment]
 return {"inspection_count":len(runs),"equipment_count":len(equipment),"active_warnings":distribution["WARNING"],"high_risk_events":distribution["HIGH_RISK"]+distribution["CRITICAL"],"open_alerts":sum(1 for a in alerts if a.status=="OPEN"),"risk_distribution":distribution,"recent":recent,"activity":activity,"equipment_matrix":equipment_matrix,"alerts":[{"id":a.id,"inspection_id":a.inspection_id,"severity":a.severity.value,"status":a.status,"message":a.message,"created_at":a.created_at} for a in alerts[:6]],"model":model_service.status()}
@router.get('/risk/overview')
async def risk_overview(user:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
 data=await dashboard(user,db)
 return {"distribution":data["risk_distribution"],"timeline":data["activity"],"equipment":data["equipment_matrix"],"alerts":data["alerts"],"high_risk_events":[x for x in data["recent"] if x["risk_level"] in ("HIGH_RISK","CRITICAL")]}
@router.post('/ai/inspections/{inspection_id}')
async def ai(inspection_id:str,question:str="Explain this inspection result in operator-friendly language.",user:User=Depends(current_user),db:AsyncSession=Depends(get_db)):
 data=await detail(inspection_id,user,db); pred=data["prediction"]
 if not pred: raise HTTPException(422,"This inspection has no completed analysis")
 payload={"risk_level":pred.risk_level.value,"confidence":pred.confidence,"environment":{"ambient_temperature":data['environment'].ambient_temperature,"humidity":data['environment'].humidity,"weather":data['environment'].weather},"model_evidence":pred.explanation_metadata}
 try: response,model=await asyncio.wait_for(explain(payload,question),timeout=4)
 except asyncio.TimeoutError: response,model=fallback_explanation(payload),"fast-deterministic-fallback"
 record=AIAnalysis(inspection_id=inspection_id,prompt_type="operator_question",response=response,model_used=model); db.add(record); await db.commit(); return {"response":response,"model_used":model}
@router.get('/models/status')
async def model_status(user:User=Depends(current_user)): return model_service.status()
@router.get('/experiments')
async def experiments(user:User=Depends(current_user)): return []

def action_for(risk:str|None):
 return {"NORMAL":"Routine record; continue scheduled monitoring.","WARNING":"Review evidence and monitor the asset.","HIGH_RISK":"Engineering inspection recommended.","CRITICAL":"Immediate engineering review recommended."}.get(risk,"Complete analysis to receive an operator review recommendation.")
