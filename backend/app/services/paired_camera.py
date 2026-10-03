"""A sequential replay source; filenames declare pairs, not real live capture."""
import hashlib
import io
import json
import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.entities import CameraSimulationCursor

PAIR_PROTOCOL = "evothermguard-pair-v1"
SOURCE_KIND = "dataset_backed_camera_simulation"
IMAGE_NAME = re.compile(r"^(RGB|Thermal)_([A-Za-z0-9_-]+)\.(jpg|jpeg|png)$", re.I)
DATASET_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def dataset_root(dataset_id: str | None = None) -> Path:
    if dataset_id is None:
        return Path(settings.camera_dataset_path).resolve()
    if len(dataset_id) > 64 or not DATASET_ID.fullmatch(dataset_id):
        raise ValueError("Invalid camera dataset ID")
    parent = Path(settings.camera_datasets_path).resolve()
    root = (parent / dataset_id).resolve()
    if not root.is_relative_to(parent):
        raise ValueError("Camera dataset resolves outside the datasets directory")
    return root


def dataset_info(dataset_id: str) -> dict:
    """Only explicit provenance may identify data as synthetic or field captured."""
    manifest = dataset_root(dataset_id) / "dataset.json"
    if not manifest.is_file():
        return {"dataset_id": dataset_id, "data_origin": "unspecified"}
    with manifest.open(encoding="utf-8") as file:
        info = json.load(file)
    if not isinstance(info, dict) or info.get("dataset_id") != dataset_id:
        raise ValueError("Camera dataset manifest ID does not match its directory")
    return {"dataset_id": dataset_id, "data_origin": info.get("data_origin", "unspecified"),
            "asset_name": info.get("asset_name", dataset_id),
            "description": info.get("description", "")}


@dataclass(frozen=True)
class DatasetPair:
    pair_id: str
    rgb: Path
    thermal: Path


def dataset_pairs(dataset_id: str | None = None) -> list[DatasetPair]:
    """Pair only identical IDs in the same directory; reject ambiguous catalogs."""
    root = dataset_root(dataset_id)
    if not root.is_dir():
        raise ValueError("Camera dataset directory does not exist")
    groups: dict[str, dict[str, Path]] = {}
    for path in sorted(root.rglob("*")):
        match = IMAGE_NAME.fullmatch(path.name)
        if not match or not path.is_file():
            continue
        modality, pair_id, _ = match.groups()
        if len(pair_id) > 128:
            raise ValueError("Camera pair IDs must be at most 128 characters")
        resolved = path.resolve()
        if not resolved.is_relative_to(root):
            raise ValueError("Camera dataset image resolves outside the dataset directory")
        pair = groups.setdefault(pair_id, {})
        key = modality.lower()
        if key in pair:
            raise ValueError(f"Duplicate {modality} image for pair {pair_id}")
        pair[key] = resolved
    if not groups:
        raise ValueError("No camera pairs found; use RGB_<id>.jpg and Thermal_<id>.jpg (or PNG)")
    pairs = []
    for pair_id, images in groups.items():
        if set(images) != {"rgb", "thermal"}:
            raise ValueError(f"Incomplete camera pair {pair_id}: RGB and thermal images are required")
        if images["rgb"].parent != images["thermal"].parent:
            raise ValueError(f"Camera pair {pair_id} images must be in the same directory")
        if images["rgb"] == images["thermal"]:
            raise ValueError(f"Camera pair {pair_id} must contain two distinct files")
        pairs.append(DatasetPair(pair_id, images["rgb"], images["thermal"]))
    return sorted(pairs, key=lambda pair: (0, int(pair.pair_id), pair.pair_id)
                  if pair.pair_id.isdecimal() else (1, pair.pair_id, pair.pair_id))


def image_bytes(path: Path) -> tuple[bytes, str]:
    """Read bounded, verified JPEG/PNG bytes without trusting the extension."""
    with path.open("rb") as file:
        data = file.read(settings.max_upload_bytes + 1)
    if not data or len(data) > settings.max_upload_bytes:
        raise ValueError("Dataset image is empty or exceeds the upload limit")
    with Image.open(io.BytesIO(data)) as image:
        content_type = {"JPEG": "image/jpeg", "PNG": "image/png"}.get(image.format)
        if not content_type:
            raise ValueError("Dataset images must be JPEG or PNG")
        image.verify()
    return data, content_type


async def select_pair(db: AsyncSession, pairs: list[DatasetPair], stream: str) -> DatasetPair:
    """One atomic increment serializes selection across workers and restarts."""
    catalog = "\n".join(f"{p.pair_id}:{p.rgb}:{p.thermal}" for p in pairs)
    scope = hashlib.sha256(f"{catalog}\n{stream}".encode()).hexdigest()
    dialect = db.get_bind().dialect.name
    insert = {"postgresql": pg_insert, "sqlite": sqlite_insert}.get(dialect)
    if insert is None:
        raise ValueError("Camera simulation cursors require PostgreSQL or SQLite")
    await db.execute(insert(CameraSimulationCursor).values(scope=scope, position=0)
                     .on_conflict_do_nothing(index_elements=["scope"]))
    position = await db.scalar(
        update(CameraSimulationCursor)
        .where(CameraSimulationCursor.scope == scope)
        .values(position=CameraSimulationCursor.position + 1)
        .returning(CameraSimulationCursor.position)
    )
    await db.commit()
    return pairs[(position - 1) % len(pairs)]
