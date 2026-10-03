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
    PAIR_PROTOCOL, SOURCE_KIND, dataset_pairs, image_bytes, select_pair,
)

router = APIRouter(prefix="/camera", tags=["Dataset camera simulation"])
NO_CACHE = {"Cache-Control": "no-store"}


def require_simulation():
    if not settings.camera_simulation_enabled:
        raise HTTPException(404, "Dataset camera simulation is disabled")


@router.get("/pair", dependencies=[Depends(require_simulation)])
async def camera_pair(
    request: Request, response: Response, db: AsyncSession = Depends(get_db),
    stream: Annotated[str, Header(alias="X-EvoThermGuard-Stream", max_length=128)] = "preview",
):
    try:
        pairs = await asyncio.to_thread(dataset_pairs)
        pair = await select_pair(db, pairs, stream)
        rgb, thermal = await asyncio.gather(
            asyncio.to_thread(image_bytes, pair.rgb),
            asyncio.to_thread(image_bytes, pair.thermal),
        )
    except (ValueError, OSError) as exc:
        raise HTTPException(503, f"Camera dataset unavailable: {exc}") from exc
    response.headers.update(NO_CACHE)
    return {
        "protocol": PAIR_PROTOCOL,
        "source_kind": SOURCE_KIND,
        "pair_id": pair.pair_id,
        "selected_at": datetime.now(timezone.utc).isoformat(),
        "images": {
            kind: {
                "url": str(request.url_for("camera_pair_image", pair_id=pair.pair_id, modality=kind)),
                "sha256": hashlib.sha256(payload[0]).hexdigest(),
            }
            for kind, payload in (("rgb", rgb), ("thermal", thermal))
        },
    }


@router.get("/pairs/{pair_id}/{modality}", name="camera_pair_image",
            dependencies=[Depends(require_simulation)])
async def camera_pair_image(pair_id: str, modality: Literal["rgb", "thermal"]):
    try:
        pairs = await asyncio.to_thread(dataset_pairs)
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
    })
