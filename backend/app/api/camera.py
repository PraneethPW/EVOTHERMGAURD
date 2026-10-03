"""Opt-in paired dataset replay endpoints; no real camera is represented."""
import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.services.paired_camera import (
    DATASET_ID, PAIR_PROTOCOL, SOURCE_KIND, dataset_info, dataset_pairs,
    image_bytes, select_pair,
)
from pathlib import Path

router = APIRouter(prefix="/camera", tags=["Dataset camera simulation"])
NO_CACHE = {"Cache-Control": "no-store"}


def camera_url(request: Request, route: str, **parameters) -> str:
    url = request.url_for(route, **parameters)
    # TLS-terminating proxies may present HTTP to the application. Use the
    # configured public origin rather than generating insecure image links.
    if settings.camera_public_base_url:
        return settings.camera_public_base_url.rstrip("/") + url.path
    return str(url)


def require_simulation():
    if not settings.camera_simulation_enabled:
        raise HTTPException(404, "Dataset camera simulation is disabled")


@router.get("/datasets", dependencies=[Depends(require_simulation)])
async def camera_datasets(request: Request, response: Response):
    """Discover configured per-asset feeds without advancing any capture cursor."""
    def catalog():
        root = Path(settings.camera_datasets_path)
        entries = []
        for folder in sorted(root.iterdir()) if root.is_dir() else []:
            if not folder.is_dir() or not DATASET_ID.fullmatch(folder.name):
                continue
            try:
                info = dataset_info(folder.name)
                pairs = dataset_pairs(folder.name)
                entries.append({**info, "ready": True, "pair_count": len(pairs)})
            except (ValueError, OSError):
                entries.append({"dataset_id": folder.name, "ready": False, "pair_count": 0,
                                "error": "Dataset missing, incomplete, or invalid"})
        return entries
    entries = await asyncio.to_thread(catalog)
    for entry in entries:
        entry["pair_url"] = camera_url(request, "dataset_camera_pair", dataset_id=entry["dataset_id"])
    response.headers.update(NO_CACHE)
    return {"source_kind": SOURCE_KIND, "datasets": entries}


async def pair_descriptor(request, response, db, stream, dataset_id=None):
    try:
        pairs = await asyncio.to_thread(dataset_pairs, dataset_id)
        info = await asyncio.to_thread(dataset_info, dataset_id) if dataset_id else {}
        pair = await select_pair(db, pairs, stream)
        rgb, thermal = await asyncio.gather(
            asyncio.to_thread(image_bytes, pair.rgb),
            asyncio.to_thread(image_bytes, pair.thermal),
        )
    except (ValueError, OSError) as exc:
        raise HTTPException(503, f"Camera dataset unavailable: {exc}") from exc
    response.headers.update(NO_CACHE)
    route = "dataset_camera_pair_image" if dataset_id else "camera_pair_image"
    arguments = {"dataset_id": dataset_id} if dataset_id else {}
    return {
        "protocol": PAIR_PROTOCOL, "source_kind": SOURCE_KIND, **info,
        "pair_id": pair.pair_id,
        "selected_at": datetime.now(timezone.utc).isoformat(),
        "images": {
            kind: {
                "url": camera_url(request, route, **arguments, pair_id=pair.pair_id, modality=kind),
                "sha256": hashlib.sha256(payload[0]).hexdigest(),
            }
            for kind, payload in (("rgb", rgb), ("thermal", thermal))
        },
    }


@router.get("/pair", dependencies=[Depends(require_simulation)])
async def camera_pair(
    request: Request, response: Response, db: AsyncSession = Depends(get_db),
    stream: Annotated[str, Header(alias="X-EvoThermGuard-Stream", max_length=128)] = "preview",
):
    return await pair_descriptor(request, response, db, stream)


@router.get("/datasets/{dataset_id}/pair", name="dataset_camera_pair",
            dependencies=[Depends(require_simulation)])
async def dataset_camera_pair(
    dataset_id: str, request: Request, response: Response, db: AsyncSession = Depends(get_db),
    stream: Annotated[str, Header(alias="X-EvoThermGuard-Stream", max_length=128)] = "preview",
):
    return await pair_descriptor(request, response, db, stream, dataset_id)


async def pair_image(pair_id, modality, dataset_id=None):
    try:
        pairs = await asyncio.to_thread(dataset_pairs, dataset_id)
        pair = next((pair for pair in pairs if pair.pair_id == pair_id), None)
        if pair is None:
            raise HTTPException(404, "Dataset pair not found")
        data, content_type = await asyncio.to_thread(image_bytes, getattr(pair, modality))
    except (ValueError, OSError) as exc:
        raise HTTPException(503, f"Camera dataset unavailable: {exc}") from exc
    return Response(data, media_type=content_type, headers={
        **NO_CACHE, "X-EvoThermGuard-Pair-ID": pair.pair_id,
        "X-EvoThermGuard-Modality": modality,
        "X-EvoThermGuard-Source": SOURCE_KIND,
        **({"X-EvoThermGuard-Dataset-ID": dataset_id} if dataset_id else {}),
    })


@router.get("/pairs/{pair_id}/{modality}", name="camera_pair_image",
            dependencies=[Depends(require_simulation)])
async def camera_pair_image(pair_id: str, modality: Literal["rgb", "thermal"]):
    return await pair_image(pair_id, modality)


@router.get("/datasets/{dataset_id}/pairs/{pair_id}/{modality}", name="dataset_camera_pair_image",
            dependencies=[Depends(require_simulation)])
async def dataset_camera_pair_image(dataset_id: str, pair_id: str, modality: Literal["rgb", "thermal"]):
    return await pair_image(pair_id, modality, dataset_id)
