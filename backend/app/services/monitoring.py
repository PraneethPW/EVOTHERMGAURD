import asyncio
from datetime import datetime, timedelta
from uuid import uuid4

import httpx
from sqlalchemy import select, update

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.entities import CaptureMode, ImageType, Inspection, InspectionEnvironment, InspectionImage, MonitoringSource
from app.services.analysis import analysis_service
from app.services.storage import save_image_bytes
from app.services.weather import current_weather

CAPTURE_INTERVAL_MINUTES = 10

async def fetch_camera(url: str) -> tuple[bytes,str]:
    async with httpx.AsyncClient(timeout=12,follow_redirects=True) as client:
        response=await client.get(url,headers={"Accept":"image/jpeg,image/png"})
        response.raise_for_status()
    data=response.content
    if len(data)>settings.max_upload_bytes: raise ValueError("Camera image exceeds the upload limit")
    return data,response.headers.get("content-type","application/octet-stream")

async def capture_source(source_id: str) -> str:
    async with SessionLocal() as db:
        source=await db.scalar(select(MonitoringSource).where(MonitoringSource.id==source_id))
        if not source: raise ValueError("Monitoring source not found")
        inspection=Inspection(id=str(uuid4()),user_id=source.user_id,equipment_id=source.equipment_id,monitoring_source_id=source.id,capture_mode=CaptureMode.AUTOMATIC,status="ACQUIRING")
        db.add(inspection); await db.commit()
        try:
            weather,(rgb,thermal)=await asyncio.gather(current_weather(source.latitude,source.longitude),asyncio.gather(fetch_camera(source.rgb_camera_url),fetch_camera(source.thermal_camera_url)))
            env=InspectionEnvironment(inspection_id=inspection.id,station_name=source.station_name,latitude=source.latitude,longitude=source.longitude,notes="Automatically associated with paired camera capture.",**weather)
            records=[]
            for kind,payload,url in ((ImageType.RGB,rgb,source.rgb_camera_url),(ImageType.THERMAL,thermal,source.thermal_camera_url)):
                path,width,height,meta=save_image_bytes(inspection.id,kind.value,payload[0],payload[1],url)
                records.append(InspectionImage(inspection_id=inspection.id,image_type=kind,file_path=str(path),width=width,height=height,metadata_json=meta))
            inspection.status="CAPTURED"; inspection.equipment=source.equipment; db.add_all([env,*records]); await db.commit()
            await analysis_service.run(db,inspection)
            source.last_capture_at=datetime.utcnow(); source.next_capture_at=source.last_capture_at+timedelta(minutes=CAPTURE_INTERVAL_MINUTES); source.last_error=None; await db.commit()
            return inspection.id
        except Exception as exc:
            inspection.status="CAPTURE_FAILED"; source.last_error=str(exc)[:1000]; await db.commit()
            raise

async def claim_due_sources() -> list[str]:
    now=datetime.utcnow(); claimed=[]
    async with SessionLocal() as db:
        ids=(await db.scalars(select(MonitoringSource.id).where(MonitoringSource.monitoring_enabled.is_(True),MonitoringSource.next_capture_at<=now))).all()
        for source_id in ids:
            result=await db.execute(update(MonitoringSource).where(MonitoringSource.id==source_id,MonitoringSource.monitoring_enabled.is_(True),MonitoringSource.next_capture_at<=now).values(next_capture_at=now+timedelta(minutes=CAPTURE_INTERVAL_MINUTES)))
            if result.rowcount: claimed.append(source_id)
        await db.commit()
    return claimed

async def scheduler(stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            for source_id in await claim_due_sources():
                try: await capture_source(source_id)
                except Exception: pass
        except Exception: pass
        try: await asyncio.wait_for(stop.wait(),timeout=max(5,settings.monitoring_poll_seconds))
        except asyncio.TimeoutError: pass
