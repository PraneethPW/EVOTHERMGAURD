import asyncio
import hashlib
from datetime import datetime, timedelta
from typing import Literal
from urllib.parse import urljoin, urlsplit
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field, HttpUrl, ValidationError
from sqlalchemy import select, update

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.entities import CaptureMode, ImageType, Inspection, InspectionEnvironment, InspectionImage, MonitoringSource
from app.services.analysis import analysis_service
from app.services.storage import save_image_bytes
from app.services.weather import current_weather
from app.services.paired_camera import PAIR_PROTOCOL, SOURCE_KIND

CAPTURE_INTERVAL_MINUTES = 10

def camera_url_identity(url: str) -> tuple:
    parsed = urlsplit(url)
    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    return (parsed.scheme.lower(), (parsed.hostname or "").lower(), port,
            parsed.path.rstrip("/"), parsed.query)


def is_paired_source(rgb_url: str, thermal_url: str) -> bool:
    def paired_path(url):
        return urlsplit(url).path.rstrip("/").endswith("/camera/pair")
    if not (paired_path(rgb_url) or paired_path(thermal_url)):
        return False
    if camera_url_identity(rgb_url) != camera_url_identity(thermal_url):
        raise ValueError("A paired camera source must use the same /camera/pair URL in both fields")
    return True


async def camera_response(url: str, accept: str, limit: int, headers: dict | None = None):
    chunks = []
    total = 0
    async with httpx.AsyncClient(timeout=12,follow_redirects=True) as client:
        async with client.stream("GET", url, headers={"Accept": accept, **(headers or {})}) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > limit:
                    raise ValueError("Camera response exceeds the size limit")
                chunks.append(chunk)
    return b"".join(chunks), response


async def fetch_camera(url: str) -> tuple[bytes, str]:
    data, response = await camera_response(url, "image/jpeg,image/png", settings.max_upload_bytes)
    return data, response.headers.get("content-type", "application/octet-stream")


class PairImage(BaseModel):
    url: HttpUrl
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class PairImages(BaseModel):
    rgb: PairImage
    thermal: PairImage


class PairEnvelope(BaseModel):
    protocol: Literal["evothermguard-pair-v1"]
    source_kind: Literal["dataset_backed_camera_simulation"]
    pair_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$", max_length=128)
    selected_at: datetime
    images: PairImages


async def acquire_images(source: MonitoringSource):
    """Fetch selection once, then both images for that selection; never resample."""
    if not is_paired_source(source.rgb_camera_url, source.thermal_camera_url):
        rgb, thermal = await asyncio.gather(
            fetch_camera(source.rgb_camera_url), fetch_camera(source.thermal_camera_url)
        )
        return rgb, thermal, {}
    data, response = await camera_response(
        source.rgb_camera_url, "application/json", 64 * 1024,
        {"X-EvoThermGuard-Stream": source.id},
    )
    if response.headers.get("content-type", "").split(";", 1)[0].lower() != "application/json":
        raise ValueError("Paired camera endpoint must return a JSON pair descriptor")
    try:
        pair = PairEnvelope.model_validate_json(data)
    except ValidationError as exc:
        raise ValueError("Invalid paired camera descriptor") from exc

    async def fetch_selected(modality: str):
        descriptor = getattr(pair.images, modality)
        url = str(descriptor.url)
        selection_url = urlsplit(str(response.url))._replace(query="", fragment="").geturl()
        expected_path = urlsplit(urljoin(selection_url.rstrip("/") + "/", f"../pairs/{pair.pair_id}/{modality}")).path
        if (camera_url_identity(url)[:3] != camera_url_identity(str(response.url))[:3]
                or urlsplit(url).path != expected_path or urlsplit(url).query):
            raise ValueError("Pair image URL does not identify the selected pair and modality")
        payload, image_response = await camera_response(url, "image/jpeg,image/png", settings.max_upload_bytes)
        if (image_response.headers.get("X-EvoThermGuard-Pair-ID") != pair.pair_id
                or image_response.headers.get("X-EvoThermGuard-Modality") != modality
                or hashlib.sha256(payload).hexdigest() != descriptor.sha256):
            raise ValueError("Selected pair image identity or checksum does not match")
        return payload, image_response.headers.get("content-type", "application/octet-stream")

    rgb, thermal = await asyncio.gather(fetch_selected("rgb"), fetch_selected("thermal"))
    return rgb, thermal, {
        "source": SOURCE_KIND, "protocol": PAIR_PROTOCOL, "pair_id": pair.pair_id,
        "pair_selected_at": pair.selected_at.isoformat(),
        "rgb_sha256": pair.images.rgb.sha256, "thermal_sha256": pair.images.thermal.sha256,
    }

async def capture_source(source_id: str) -> str:
    async with SessionLocal() as db:
        source=await db.scalar(select(MonitoringSource).where(MonitoringSource.id==source_id))
        if not source: raise ValueError("Monitoring source not found")
        captured_at = datetime.utcnow()
        inspection=Inspection(id=str(uuid4()),user_id=source.user_id,equipment_id=source.equipment_id,monitoring_source_id=source.id,capture_mode=CaptureMode.AUTOMATIC,status="ACQUIRING",created_at=captured_at)
        db.add(inspection); await db.commit()
        try:
            weather,(rgb,thermal,pair_meta)=await asyncio.gather(current_weather(source.latitude,source.longitude),acquire_images(source))
            notes = (f"Dataset-backed camera-feed simulation; pair {pair_meta['pair_id']}. "
                     "Current station weather associated with simulation inspection time; not historical dataset weather."
                     if pair_meta else "Automatically associated with paired camera capture.")
            env=InspectionEnvironment(inspection_id=inspection.id,station_name=source.station_name,latitude=source.latitude,longitude=source.longitude,notes=notes,**weather)
            records=[]
            for kind,payload,url in ((ImageType.RGB,rgb,source.rgb_camera_url),(ImageType.THERMAL,thermal,source.thermal_camera_url)):
                path,width,height,meta=save_image_bytes(inspection.id,kind.value,payload[0],payload[1],url)
                meta.update(pair_meta)
                meta["inspection_captured_at"] = captured_at.isoformat() + "Z"
                records.append(InspectionImage(inspection_id=inspection.id,image_type=kind,file_path=str(path),width=width,height=height,metadata_json=meta))
            inspection.status="CAPTURED"; inspection.equipment=source.equipment; db.add_all([env,*records]); await db.commit()
            await analysis_service.run(db,inspection)
            source.last_capture_at=captured_at; source.next_capture_at=captured_at+timedelta(minutes=CAPTURE_INTERVAL_MINUTES); source.last_error=None; await db.commit()
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
