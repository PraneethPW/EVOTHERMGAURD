from datetime import datetime

import httpx

from app.core.config import settings

WEATHER_CODES = {
    0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Cloudy",
    45: "Fog", 48: "Rime fog", 51: "Light drizzle", 53: "Drizzle",
    55: "Heavy drizzle", 61: "Light rain", 63: "Rain", 65: "Heavy rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 80: "Rain showers",
    81: "Rain showers", 82: "Heavy showers", 95: "Thunderstorm",
}

def season_for(latitude: float, observed: datetime) -> str:
    month = observed.month
    northern = "Winter" if month in (12,1,2) else "Spring" if month in (3,4,5) else "Summer" if month in (6,7,8) else "Autumn"
    if latitude >= 0: return northern
    return {"Winter":"Summer","Spring":"Autumn","Summer":"Winter","Autumn":"Spring"}[northern]

def time_of_day_for(observed: datetime) -> str:
    hour=observed.hour
    return "Morning" if 5<=hour<12 else "Afternoon" if 12<=hour<17 else "Evening" if 17<=hour<21 else "Night"

async def current_weather(latitude: float, longitude: float) -> dict:
    params={"latitude":latitude,"longitude":longitude,"current":"temperature_2m,relative_humidity_2m,weather_code,is_day","timezone":"auto"}
    async with httpx.AsyncClient(timeout=8,follow_redirects=True) as client:
        response=await client.get(settings.weather_api_url,params=params)
        response.raise_for_status()
    current=response.json().get("current") or {}
    observed=datetime.fromisoformat(current.get("time") or datetime.utcnow().isoformat())
    return {
        "ambient_temperature":float(current["temperature_2m"]),
        "humidity":float(current["relative_humidity_2m"]),
        "weather":WEATHER_CODES.get(int(current.get("weather_code",-1)),"Other"),
        "season":season_for(latitude,observed),
        "time_of_day":time_of_day_for(observed),
        "sun_exposure":"Daylight" if current.get("is_day") else "No daylight",
        "weather_source":"Open-Meteo",
        "weather_observed_at":observed,
    }
