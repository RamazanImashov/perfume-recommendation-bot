from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import aiohttp

HTTP_TIMEOUT = aiohttp.ClientTimeout(total=12)


async def get_coordinates(city: str) -> dict | None:
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": city, "count": 1, "language": "en", "format": "json"}
    async with aiohttp.ClientSession(timeout=HTTP_TIMEOUT) as session:
        async with session.get(url, params=params) as response:
            response.raise_for_status()
            data = await response.json()
    results = data.get("results") or []
    if not results:
        return None
    item = results[0]
    return {
        "latitude": item["latitude"], "longitude": item["longitude"], "name": item.get("name", city),
        "country": item.get("country", ""), "timezone": item.get("timezone") or "auto",
    }


def _closest_hour_index(times: list[str], target: datetime) -> int:
    parsed: list[datetime] = []
    for raw in times:
        try:
            parsed.append(datetime.fromisoformat(raw))
        except ValueError:
            parsed.append(target.replace(tzinfo=None))
    target_naive = target.replace(tzinfo=None)
    return min(range(len(parsed)), key=lambda i: abs((parsed[i] - target_naive).total_seconds()))


def _hourly_value(hourly: dict, key: str, idx: int, default=None):
    values = hourly.get(key) or []
    return values[idx] if idx < len(values) else default


async def get_weather(
    latitude: float,
    longitude: float,
    target_datetime: datetime | None = None,
    timezone: str | None = None,
) -> dict:
    """Return current weather or the nearest hourly forecast for target_datetime.

    Falls back to current conditions when hourly data cannot be matched.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    hourly_vars = ",".join([
        "temperature_2m", "apparent_temperature", "relative_humidity_2m", "precipitation", "rain",
        "weather_code", "cloud_cover", "wind_speed_10m", "is_day",
    ])
    current_vars = hourly_vars
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": current_vars,
        "hourly": hourly_vars,
        "timezone": timezone or "auto",
        "forecast_days": 3,
    }
    async with aiohttp.ClientSession(timeout=HTTP_TIMEOUT) as session:
        async with session.get(url, params=params) as response:
            response.raise_for_status()
            data = await response.json()

    api_timezone = data.get("timezone") or timezone or "UTC"
    current = data.get("current") or {}
    if target_datetime is not None:
        try:
            local_target = target_datetime.astimezone(ZoneInfo(api_timezone)) if target_datetime.tzinfo else target_datetime.replace(tzinfo=ZoneInfo(api_timezone))
            hourly = data.get("hourly") or {}
            times = hourly.get("time") or []
            if times:
                idx = _closest_hour_index(times, local_target)
                return {
                    "temperature": _hourly_value(hourly, "temperature_2m", idx),
                    "feels_like": _hourly_value(hourly, "apparent_temperature", idx),
                    "humidity": _hourly_value(hourly, "relative_humidity_2m", idx),
                    "precipitation": _hourly_value(hourly, "precipitation", idx, 0),
                    "rain": _hourly_value(hourly, "rain", idx, 0),
                    "weather_code": _hourly_value(hourly, "weather_code", idx),
                    "cloud_cover": _hourly_value(hourly, "cloud_cover", idx),
                    "wind_speed": _hourly_value(hourly, "wind_speed_10m", idx),
                    "is_day": bool(_hourly_value(hourly, "is_day", idx, 1)),
                    "timezone": api_timezone,
                    "forecast_time": times[idx],
                    "source": "hourly_forecast",
                }
        except Exception:
            pass

    return {
        "temperature": current.get("temperature_2m"),
        "feels_like": current.get("apparent_temperature"),
        "humidity": current.get("relative_humidity_2m"),
        "precipitation": current.get("precipitation", 0),
        "rain": current.get("rain", 0),
        "weather_code": current.get("weather_code"),
        "cloud_cover": current.get("cloud_cover"),
        "wind_speed": current.get("wind_speed_10m"),
        "is_day": bool(current.get("is_day", 1)),
        "timezone": api_timezone,
        "source": "current_fallback" if target_datetime else "current",
    }


def weather_tags(weather: dict) -> set[str]:
    temp = float(weather.get("temperature") or 0)
    rain = float(weather.get("rain") or 0) + float(weather.get("precipitation") or 0)
    cloud_cover = float(weather.get("cloud_cover") or 0)
    wind_speed = float(weather.get("wind_speed") or 0)
    humidity = float(weather.get("humidity") or 0)
    tags: set[str] = set()
    if temp >= 28: tags.add("hot")
    elif temp >= 18: tags.add("warm")
    elif temp >= 8: tags.add("cool")
    else: tags.add("cold")
    if temp >= 27 and humidity >= 70: tags.add("humid_hot")
    elif temp >= 27 and humidity and humidity <= 45: tags.add("dry_hot")
    elif temp <= 8 and humidity >= 75: tags.add("damp_cold")
    elif temp <= 8 and humidity and humidity <= 50: tags.add("dry_cold")
    if rain > 0: tags.add("rainy")
    if cloud_cover >= 70: tags.add("cloudy")
    if wind_speed >= 20: tags.add("windy")
    if humidity >= 75: tags.add("humid")
    if temp >= 27 and cloud_cover < 35 and weather.get("is_day", True): tags.add("sunny_hot")
    tags.add("day" if weather.get("is_day", True) else "night")
    return tags
