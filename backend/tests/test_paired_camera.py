import asyncio
import hashlib
from datetime import datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.camera import router
from app.core.config import settings
from app.db.session import get_db
from app.models.entities import (
    Alert, Base, Equipment, ImageType, Inspection, InspectionEnvironment,
    InspectionImage, MonitoringSource, Prediction, User,
)
from app.services import monitoring
from app.services.paired_camera import dataset_pairs, image_bytes, select_pair, SOURCE_KIND


@pytest_asyncio.fixture
async def simulation(tmp_path, monkeypatch):
    dataset = tmp_path / "dataset"
    for index in (1, 2, 3):
        folder = dataset / f"Pair {index:03}"
        folder.mkdir(parents=True)
        Image.new("RGB", (32, 24), (index * 60, 30, 10)).save(folder / f"RGB_{index:03}.jpg")
        Image.new("L", (32, 24), index * 70).save(folder / f"Thermal_{index:03}.jpg")
    monkeypatch.setattr(settings, "camera_simulation_enabled", True)
    monkeypatch.setattr(settings, "camera_dataset_path", str(dataset))
    monkeypatch.setattr(settings, "storage_path", str(tmp_path / "evidence"))
    monkeypatch.setattr(settings, "smtp_host", "")
    db_url = "sqlite+aiosqlite:///" + (tmp_path / "simulation.db").as_posix()
    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(router)

    async def database():
        async with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = database
    requests = []

    @app.middleware("http")
    async def record_request(request, call_next):
        requests.append(request.url.path)
        return await call_next(request)

    transport = httpx.ASGITransport(app=app)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(monitoring, "httpx", SimpleNamespace(
        AsyncClient=lambda **kwargs: original_client(transport=transport, **kwargs)
    ))
    monkeypatch.setattr(monitoring, "SessionLocal", sessions)
    async with original_client(transport=transport, base_url="http://camera.test") as client:
        yield SimpleNamespace(dataset=dataset, sessions=sessions, client=client,
                              requests=requests, db_url=db_url)
    await engine.dispose()


@pytest.mark.asyncio
async def test_endpoint_pins_pair_and_cursor_survives_reconnection(simulation):
    client = simulation.client
    first = (await client.get("/camera/pair")).json()
    assert first["pair_id"] == "001"
    assert first["source_kind"] == SOURCE_KIND
    for _ in range(2):
        for modality in ("rgb", "thermal"):
            result = await client.get(first["images"][modality]["url"])
            assert result.status_code == 200
            assert result.headers["cache-control"] == "no-store"
            assert result.headers["x-evothermguard-pair-id"] == "001"
            assert hashlib.sha256(result.content).hexdigest() == first["images"][modality]["sha256"]
    assert (await client.get("/camera/pair")).json()["pair_id"] == "002"
    # A new engine/session pool sees the persisted cursor rather than restarting.
    restarted = create_async_engine(simulation.db_url)
    async with async_sessionmaker(restarted)() as db:
        assert (await select_pair(db, dataset_pairs(), "preview")).pair_id == "003"
    await restarted.dispose()
    assert (await client.get("/camera/pair")).json()["pair_id"] == "001"
    assert (await client.get("/camera/pair", headers={"X-EvoThermGuard-Stream": "another-source"})).json()["pair_id"] == "001"
    assert (await client.get("/camera/pairs/missing/rgb")).status_code == 404


@pytest.mark.asyncio
async def test_concurrent_pair_requests_share_atomic_cursor(simulation):
    responses = await asyncio.gather(*[
        simulation.client.get("/camera/pair", headers={"X-EvoThermGuard-Stream": "concurrent"})
        for _ in range(9)
    ])
    assert all(response.status_code == 200 for response in responses)
    ids = [response.json()["pair_id"] for response in responses]
    assert {pair_id: ids.count(pair_id) for pair_id in set(ids)} == {"001": 3, "002": 3, "003": 3}


@pytest.mark.asyncio
async def test_simultaneous_inspections_keep_corresponding_modalities(simulation):
    source = MonitoringSource(id="simultaneous", rgb_camera_url="http://camera.test/camera/pair", thermal_camera_url="http://camera.test/camera/pair")
    captures = await asyncio.gather(*[monitoring.acquire_images(source) for _ in range(3)])
    assert {meta["pair_id"] for _, _, meta in captures} == {"001", "002", "003"}
    for rgb, thermal, meta in captures:
        folder = simulation.dataset / f"Pair {meta['pair_id']}"
        assert rgb[0] == (folder / f"RGB_{meta['pair_id']}.jpg").read_bytes()
        assert thermal[0] == (folder / f"Thermal_{meta['pair_id']}.jpg").read_bytes()
    assert simulation.requests.count("/camera/pair") == 3


@pytest.mark.asyncio
async def test_capture_uses_one_pair_then_runs_pipeline_and_scheduling(simulation, monkeypatch):
    weather_requests = []

    async def weather(lat, lon):
        weather_requests.append((lat, lon))
        return dict(ambient_temperature=35.0, humidity=60.0, weather="Clear",
                    season="Summer", time_of_day="Afternoon", sun_exposure="Daylight",
                    weather_source="Open-Meteo", weather_observed_at=datetime.utcnow())
    monkeypatch.setattr(monitoring, "current_weather", weather)
    async with simulation.sessions() as db:
        db.add(User(id="user", name="Operator", email="operator@example.test", password_hash="unused"))
        db.add(Equipment(id="asset", user_id="user", equipment_name="Transformer T-01", equipment_type="Transformer"))
        db.add(MonitoringSource(id="source", user_id="user", equipment_id="asset",
                               station_name="Demo station", latitude=12.12, longitude=79.45,
                               rgb_camera_url="http://camera.test/camera/pair",
                               thermal_camera_url="http://camera.test/camera/pair"))
        await db.commit()
    for expected_id in ("001", "002"):
        inspection_id = await monitoring.capture_source("source")
        async with simulation.sessions() as db:
            inspection = await db.get(Inspection, inspection_id)
            assert inspection.status == "COMPLETED"
            images = (await db.scalars(select(InspectionImage).where(InspectionImage.inspection_id == inspection_id))).all()
            assert {im.image_type for im in images} == set(ImageType)
            originals = [im for im in images if im.image_type in (ImageType.RGB, ImageType.THERMAL)]
            assert {im.metadata_json["pair_id"] for im in originals} == {expected_id}
            assert {im.metadata_json["source"] for im in originals} == {SOURCE_KIND}
            assert len({im.metadata_json["inspection_captured_at"] for im in originals}) == 1
            env = await db.scalar(select(InspectionEnvironment).where(InspectionEnvironment.inspection_id == inspection_id))
            assert "simulation" in env.notes
            assert (env.latitude, env.longitude) == (12.12, 79.45)
            prediction = await db.scalar(select(Prediction).where(Prediction.inspection_id == inspection_id))
            assert prediction.explanation_metadata["capture_source"]["pair_id"] == expected_id
            alerts = (await db.scalars(select(Alert).where(Alert.inspection_id == inspection_id))).all()
            assert bool(alerts) == prediction.explanation_metadata["notification_policy"]["dashboard"]
            source = await db.get(MonitoringSource, "source")
            assert source.last_capture_at == inspection.created_at
            assert source.next_capture_at - source.last_capture_at == timedelta(minutes=10)
    assert simulation.requests.count("/camera/pair") == 2
    assert weather_requests == [(12.12, 79.45)] * 2
    assert await monitoring.claim_due_sources() == []
    async with simulation.sessions() as db:
        source = await db.get(MonitoringSource, "source")
        source.next_capture_at = datetime.utcnow() - timedelta(seconds=1)
        await db.commit()
    assert await monitoring.claim_due_sources() == ["source"]
    assert await monitoring.claim_due_sources() == []
    await monitoring.capture_source("source")
    assert simulation.requests.count("/camera/pair") == 3


@pytest.mark.asyncio
async def test_corrupt_or_changed_image_fails_without_resampling(simulation, monkeypatch):
    source = MonitoringSource(id="changed", rgb_camera_url="http://camera.test/camera/pair", thermal_camera_url="http://camera.test/camera/pair")
    original = monitoring.camera_response

    async def change_after_selection(url, accept, limit, headers=None):
        result = await original(url, accept, limit, headers)
        if accept == "application/json":
            Image.new("L", (32, 24), 255).save(simulation.dataset / "Pair 001/Thermal_001.jpg")
        return result
    monkeypatch.setattr(monitoring, "camera_response", change_after_selection)
    with pytest.raises(ValueError, match="checksum"):
        await monitoring.acquire_images(source)
    assert simulation.requests.count("/camera/pair") == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_descriptor", ["malformed", "wrong_pair", "wrong_modality"])
async def test_descriptor_identity_errors_are_rejected(simulation, monkeypatch, bad_descriptor):
    source = MonitoringSource(id="invalid", rgb_camera_url="http://camera.test/camera/pair", thermal_camera_url="http://camera.test/camera/pair")
    original = monitoring.camera_response

    async def corrupt_descriptor(url, accept, limit, headers=None):
        data, response = await original(url, accept, limit, headers)
        if accept == "application/json":
            import json
            if bad_descriptor == "malformed":
                data = b'{"pair_id":"001"}'
            else:
                descriptor = json.loads(data)
                descriptor["images"]["thermal"]["url"] = (
                    "http://camera.test/camera/pairs/002/thermal" if bad_descriptor == "wrong_pair"
                    else "http://camera.test/camera/pairs/001/rgb"
                )
                data = json.dumps(descriptor).encode()
        return data, response
    monkeypatch.setattr(monitoring, "camera_response", corrupt_descriptor)
    with pytest.raises(ValueError):
        await monitoring.acquire_images(source)
    assert simulation.requests.count("/camera/pair") == 1


@pytest.mark.asyncio
async def test_acquisition_failure_records_failed_inspection_and_skips_analysis(simulation, monkeypatch):
    async def weather(lat, lon):
        return dict(ambient_temperature=25, humidity=60, weather="Clear", season="Summer",
                    time_of_day="Morning", sun_exposure="Daylight")
    monkeypatch.setattr(monitoring, "current_weather", weather)
    async with simulation.sessions() as db:
        db.add(User(id="failed-user", name="Operator", email="failed@example.test", password_hash="unused"))
        db.add(Equipment(id="failed-asset", user_id="failed-user", equipment_name="Transformer", equipment_type="Transformer"))
        db.add(MonitoringSource(id="failed-source", user_id="failed-user", equipment_id="failed-asset",
                               station_name="Demo station", latitude=12, longitude=79,
                               rgb_camera_url="http://camera.test/camera/pair", thermal_camera_url="http://camera.test/camera/pair"))
        await db.commit()
    (simulation.dataset / "Pair 001/Thermal_001.jpg").unlink()
    with pytest.raises(httpx.HTTPStatusError):
        await monitoring.capture_source("failed-source")
    async with simulation.sessions() as db:
        inspection = await db.scalar(select(Inspection))
        assert inspection.status == "CAPTURE_FAILED"
        assert await db.scalar(select(Prediction)) is None
        assert await db.scalar(select(InspectionImage)) is None
        assert (await db.get(MonitoringSource, "failed-source")).last_error


@pytest.mark.asyncio
async def test_disabled_and_incomplete_dataset_fail_clearly(simulation, monkeypatch):
    monkeypatch.setattr(settings, "camera_simulation_enabled", False)
    assert (await simulation.client.get("/camera/pair")).status_code == 404
    monkeypatch.setattr(settings, "camera_simulation_enabled", True)
    (simulation.dataset / "Pair 001/Thermal_001.jpg").unlink()
    response = await simulation.client.get("/camera/pair")
    assert response.status_code == 503
    assert "Incomplete camera pair 001" in response.json()["detail"]


@pytest.mark.asyncio
async def test_duplicate_pair_or_cross_directory_modalities_rejected(simulation):
    folder = simulation.dataset / "duplicate"
    folder.mkdir()
    Image.new("RGB", (16, 16)).save(folder / "RGB_001.png")
    with pytest.raises(ValueError, match="Duplicate"):
        dataset_pairs()
    (folder / "RGB_001.png").unlink()
    (simulation.dataset / "Pair 001/Thermal_001.jpg").rename(folder / "Thermal_001.jpg")
    with pytest.raises(ValueError, match="same directory"):
        dataset_pairs()


@pytest.mark.asyncio
async def test_corrupt_image_and_size_limit_rejected(simulation, monkeypatch):
    path = simulation.dataset / "Pair 001/RGB_001.jpg"
    monkeypatch.setattr(settings, "max_upload_bytes", 5)
    with pytest.raises(ValueError, match="size|limit"):
        image_bytes(path)
    monkeypatch.setattr(settings, "max_upload_bytes", 1024)
    path.write_bytes(b"not a JPEG")
    assert (await simulation.client.get("/camera/pair")).status_code == 503


@pytest.mark.asyncio
async def test_separate_real_camera_endpoints_remain_supported(simulation, monkeypatch):
    requests = []

    async def fetch(url):
        requests.append(url)
        return url.encode(), "image/jpeg"
    monkeypatch.setattr(monitoring, "fetch_camera", fetch)
    source = MonitoringSource(id="real", rgb_camera_url="https://real.example/rgb.jpg", thermal_camera_url="https://real.example/thermal.jpg")
    rgb, thermal, metadata = await monitoring.acquire_images(source)
    assert rgb[0] == source.rgb_camera_url.encode()
    assert thermal[0] == source.thermal_camera_url.encode()
    assert metadata == {}
    assert len(requests) == 2


def test_paired_source_detection_and_mismatched_fields():
    assert monitoring.is_paired_source("https://CAMERA.test:443/camera/pair/", "https://camera.test/camera/pair")
    assert not monitoring.is_paired_source("https://camera.test/rgb.jpg", "https://camera.test/thermal.jpg")
    with pytest.raises(ValueError, match="same"):
        monitoring.is_paired_source("https://camera.test/camera/pair", "https://camera.test/thermal.jpg")


def test_cursor_migration_upgrade_downgrade_upgrade(tmp_path, monkeypatch):
    import sqlite3
    from alembic import command
    from alembic.config import Config

    database = tmp_path / "migration.db"
    monkeypatch.setattr(settings, "database_url", "sqlite:///" + database.as_posix())
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT COUNT(*) FROM camera_simulation_cursors").fetchone()[0] == 0
    command.downgrade(config, "94e907c533d0")
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT name FROM sqlite_master WHERE name='camera_simulation_cursors'").fetchone() is None
        assert db.execute("SELECT name FROM sqlite_master WHERE name='monitoring_sources'").fetchone()
    command.upgrade(config, "head")
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "b421dc54ea90"

@pytest.mark.asyncio
async def test_named_datasets_catalog_cursors_and_pipeline(simulation, monkeypatch):
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "dataset/cameras"
    monkeypatch.setattr(settings, "camera_datasets_path", str(root))
    catalog = (await simulation.client.get("/camera/datasets")).json()["datasets"]
    assert len(catalog) == 5
    assert all(e["ready"] and e["pair_count"] == 4 and e["data_origin"] == "synthetic" for e in catalog)
    await simulation.client.get("/camera/datasets")
    for entry in catalog:
        url = entry["pair_url"]
        assert monitoring.is_paired_source(url, url)
        for expected in ("001", "002", "003", "004", "001"):
            pair = (await simulation.client.get(url)).json()
            assert (pair["dataset_id"], pair["pair_id"]) == (entry["dataset_id"], expected)
            for kind in ("rgb", "thermal"):
                result = await simulation.client.get(pair["images"][kind]["url"])
                assert result.headers["x-evothermguard-dataset-id"] == entry["dataset_id"]
                assert hashlib.sha256(result.content).hexdigest() == pair["images"][kind]["sha256"]
    async def weather(lat, lon):
        return dict(ambient_temperature=28, humidity=55, weather="Clear", season="Summer", time_of_day="Morning", sun_exposure="Daylight")
    monkeypatch.setattr(monitoring, "current_weather", weather)
    async with simulation.sessions() as db:
        db.add(User(id="named-user", name="Demo", email="named@example.test", password_hash="unused"))
        for entry in catalog:
            key = entry["dataset_id"]
            db.add(Equipment(id=key, user_id="named-user", equipment_name=entry["asset_name"], equipment_type="Demo"))
            db.add(MonitoringSource(id="source-"+key, user_id="named-user", equipment_id=key, station_name="Demo", latitude=12, longitude=79, rgb_camera_url=entry["pair_url"], thermal_camera_url=entry["pair_url"]))
        await db.commit()
    for entry in catalog:
        key = entry["dataset_id"]
        inspection_id = await monitoring.capture_source("source-"+key)
        async with simulation.sessions() as db:
            inspection = await db.get(Inspection, inspection_id)
            assert inspection.status == "COMPLETED" and inspection.equipment_id == key
            prediction = await db.scalar(select(Prediction).where(Prediction.inspection_id == inspection_id))
            capture = prediction.explanation_metadata["capture_source"]
            assert (capture["dataset_id"], capture["pair_id"], capture["data_origin"]) == (key, "001", "synthetic")
            source = await db.get(MonitoringSource, "source-"+key)
            assert source.next_capture_at-source.last_capture_at == timedelta(minutes=10)
        manifest = json.loads((root/key/"dataset.json").read_text())
        for pair, record in zip(dataset_pairs(key), manifest["pairs"]):
            for kind in ("rgb", "thermal"):
                assert hashlib.sha256(getattr(pair, kind).read_bytes()).hexdigest() == record["images"][kind]["sha256"]


@pytest.mark.asyncio
@pytest.mark.parametrize("corruption", ["descriptor_dataset", "image_dataset", "image_path"])
async def test_cross_asset_substitution_is_rejected(simulation, monkeypatch, corruption):
    import json
    from pathlib import Path
    monkeypatch.setattr(settings, "camera_datasets_path", str(Path(__file__).resolve().parents[1]/"dataset/cameras"))
    url = "http://camera.test/camera/datasets/transformer-t-01/pair"
    source = MonitoringSource(id="cross-asset", rgb_camera_url=url, thermal_camera_url=url)
    original = monitoring.camera_response
    async def substitute(url, accept, limit, headers=None):
        data, response = await original(url, accept, limit, headers)
        if accept == "application/json":
            descriptor = json.loads(data)
            if corruption == "descriptor_dataset":
                descriptor["dataset_id"] = "motor-m-204"
            elif corruption == "image_path":
                descriptor["images"]["thermal"]["url"] = descriptor["images"]["thermal"]["url"].replace("transformer-t-01", "motor-m-204")
            data = json.dumps(descriptor).encode()
        elif corruption == "image_dataset":
            response.headers["X-EvoThermGuard-Dataset-ID"] = "motor-m-204"
        return data, response
    monkeypatch.setattr(monitoring, "camera_response", substitute)
    with pytest.raises(ValueError):
        await monitoring.acquire_images(source)
    assert simulation.requests.count("/camera/datasets/transformer-t-01/pair") == 1


def test_named_dataset_paths_and_url_mismatch(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "camera_datasets_path", str(tmp_path))
    for key in ("../outside", "UPPERCASE", "bad/slash", "a"*65):
        with pytest.raises(ValueError, match="Invalid"):
            dataset_pairs(key)
    with pytest.raises(ValueError, match="same"):
        monitoring.is_paired_source("https://camera.test/camera/datasets/transformer-t-01/pair", "https://camera.test/camera/datasets/motor-m-204/pair")

@pytest.mark.asyncio
async def test_proxy_uses_explicit_https_public_origin(simulation, monkeypatch):
    from pathlib import Path
    monkeypatch.setattr(settings, "camera_public_base_url", "https://camera.test")
    monkeypatch.setattr(settings, "camera_datasets_path", str(Path(__file__).resolve().parents[1]/"dataset/cameras"))
    entry = (await simulation.client.get('/camera/datasets')).json()['datasets'][0]
    assert entry['pair_url'].startswith('https://camera.test/')
    pair = (await simulation.client.get(entry['pair_url'])).json()
    assert all(im['url'].startswith('https://camera.test/') for im in pair['images'].values())
    source = MonitoringSource(id='proxy-source', rgb_camera_url=entry['pair_url'], thermal_camera_url=entry['pair_url'])
    rgb, thermal, meta = await monitoring.acquire_images(source)
    assert meta['dataset_id'] == entry['dataset_id'] and meta['pair_id'] == '001'
