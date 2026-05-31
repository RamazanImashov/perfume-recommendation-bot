import aiohttp


async def get_coordinates(city: str) -> dict | None:
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {
        "name": city,
        "count": 1,
        "language": "en",
        "format": "json",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, timeout=15) as response:
            response.raise_for_status()
            data = await response.json()

    results = data.get("results") or []
    if not results:
        return None

    item = results[0]
    return {
        "latitude": item["latitude"],
        "longitude": item["longitude"],
        "name": item.get("name", city),
        "country": item.get("country", ""),
        "timezone": item.get("timezone", "auto"),
    }


async def get_weather(latitude: float, longitude: float) -> dict:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,relative_humidity_2m,precipitation,rain,weather_code,cloud_cover,wind_speed_10m,is_day",
        "timezone": "auto",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, timeout=15) as response:
            response.raise_for_status()
            data = await response.json()

    current = data["current"]
    return {
        "temperature": current.get("temperature_2m"),
        "humidity": current.get("relative_humidity_2m"),
        "precipitation": current.get("precipitation", 0),
        "rain": current.get("rain", 0),
        "weather_code": current.get("weather_code"),
        "cloud_cover": current.get("cloud_cover"),
        "wind_speed": current.get("wind_speed_10m"),
        "is_day": bool(current.get("is_day", 1)),
    }


def weather_tags(weather: dict) -> set[str]:
    temp = float(weather.get("temperature") or 0)
    rain = float(weather.get("rain") or 0) + float(weather.get("precipitation") or 0)
    cloud_cover = int(weather.get("cloud_cover") or 0)
    wind_speed = float(weather.get("wind_speed") or 0)
    humidity = float(weather.get("humidity") or 0)

    tags: set[str] = set()

    if temp >= 28:
        tags.add("hot")
    elif temp >= 18:
        tags.add("warm")
    elif temp >= 8:
        tags.add("cool")
    else:
        tags.add("cold")

    if rain > 0:
        tags.add("rainy")

    if cloud_cover >= 70:
        tags.add("cloudy")

    if wind_speed >= 20:
        tags.add("windy")

    if humidity >= 75:
        tags.add("humid")

    tags.add("day" if weather.get("is_day", True) else "night")

    return tags
