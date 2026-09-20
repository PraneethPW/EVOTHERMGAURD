from datetime import datetime
from io import BytesIO

import pytest
from PIL import Image
from pydantic import ValidationError

from app.schemas.schemas import MonitoringSourceIn
from app.services.storage import save_image_bytes
from app.services.weather import season_for, time_of_day_for


def test_monitoring_source_requires_coordinates_and_http_camera_urls():
    source = MonitoringSourceIn(
        equipment_id="asset-1",
        station_name="KARE Substation",
        latitude=12.12,
        longitude=79.45,
        rgb_camera_url="https://gateway.example/rgb.jpg",
        thermal_camera_url="https://gateway.example/thermal.png",
    )
    assert source.monitoring_enabled is True
    with pytest.raises(ValidationError):
        MonitoringSourceIn(
            equipment_id="asset-1",
            station_name="KARE Substation",
            latitude=120,
            longitude=79.45,
            rgb_camera_url="file:///tmp/rgb.jpg",
            thermal_camera_url="https://gateway.example/thermal.png",
        )


def test_weather_context_derives_season_and_time_of_day():
    observed = datetime(2026, 7, 10, 14, 0)
    assert season_for(12.0, observed) == "Summer"
    assert season_for(-33.0, observed) == "Winter"
    assert time_of_day_for(observed) == "Afternoon"


def test_automatic_camera_bytes_are_validated_and_saved(tmp_path, monkeypatch):
    image = Image.new("RGB", (32, 24), (200, 40, 20))
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    monkeypatch.setattr("app.services.storage.settings.storage_path", str(tmp_path))
    path, width, height, metadata = save_image_bytes(
        "inspection-1", "RGB", buffer.getvalue(), "image/jpeg", "https://camera/rgb.jpg"
    )
    assert path.exists()
    assert (width, height) == (32, 24)
    assert metadata["source"] == "automatic_camera"
