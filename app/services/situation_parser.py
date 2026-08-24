from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from app.models.situation import Situation
from app.services.outfit_parser import parse_outfit_profile

EVENT_ALIASES = {
    "study": "study", "учеб": "study", "универ": "study", "колледж": "study", "работ": "work", "офис": "work",
    "meeting": "meeting", "встреч": "meeting", "important_meeting": "meeting", "important_event": "meeting", "day_meeting": "meeting",
    "walk": "walk", "прогул": "walk", "day_walk": "walk", "evening_walk": "walk", "night_walk": "walk", "cold_walk": "walk",
    "cafe": "cafe", "кафе": "cafe", "кофейн": "cafe", "coffee_shop": "cafe", "date": "date", "свидан": "date",
    "casual_date": "date", "winter_date": "date", "restaurant": "restaurant", "ресторан": "restaurant", "restaurant_day": "restaurant",
    "restaurant_evening": "restaurant", "party": "party", "вечерин": "party", "light_party": "party", "club": "club", "клуб": "club",
    "birthday": "birthday", "день рожден": "birthday", "active": "active", "active_day": "active", "спорт": "active",
    "gym_after_shower": "active", "ordinary_day": "casual", "обычн": "casual", "casual": "casual", "city": "casual",
}

EFFECT_ALIASES = {
    "чист": "clean", "clean": "clean", "дорог": "expensive", "expensive": "expensive", "сексу": "sexy", "sexy": "sexy",
    "замет": "noticeable", "шлейф": "noticeable", "noticeable": "noticeable", "спокой": "calm", "calm": "calm",
    "необыч": "unusual", "unique": "unusual",
}

CIRCUMSTANCE_ALIASES = {
    "маленьк.*помещ": "small_room", "тесн": "small_room", "close distance": "close_distance", "близк.*дистан": "close_distance",
    "помещ": "indoor", "indoor": "indoor", "ресторан": "indoor", "кафе": "indoor", "клуб": "club", "улиц": "outdoor", "outdoor": "outdoor",
}

LEGACY_EVENT_NORMALIZATION = {
    "important_meeting": ("meeting", ["important"], "high", 4.5),
    "important_event": ("meeting", ["important"], "high", 4.0),
    "day_meeting": ("meeting", ["day"], "medium", 3.5),
    "restaurant_day": ("restaurant", ["day"], "medium", 3.2),
    "restaurant_evening": ("restaurant", ["evening"], "medium", 3.5),
    "day_walk": ("walk", ["day"], "low", 1.5),
    "evening_walk": ("walk", ["evening"], "low", 1.5),
    "night_walk": ("walk", ["night"], "low", 1.5),
    "cold_walk": ("walk", ["cold"], "low", 1.5),
    "casual_date": ("date", ["casual"], "medium", 2.5),
    "winter_date": ("date", ["winter"], "medium", 2.5),
    "active_day": ("active", ["day"], "low", 1.0),
    "ordinary_day": ("casual", [], "low", 1.5),
}


def normalize_event(event: str) -> tuple[str, list[str], str, float]:
    raw = (event or "casual").strip().lower()
    if raw in LEGACY_EVENT_NORMALIZATION:
        return LEGACY_EVENT_NORMALIZATION[raw]
    for token, normalized in EVENT_ALIASES.items():
        if token in raw:
            default_formality = {"meeting": 3.8, "restaurant": 3.3, "date": 2.7, "study": 1.8, "work": 3.0, "club": 1.8, "party": 1.8}.get(normalized, 2.0)
            importance = "high" if "важ" in raw or "important" in raw else "medium"
            return normalized, [], importance, default_formality
    return "casual", [], "low", 1.8


def infer_outdoor_exposure(event: str, circumstance: str) -> str:
    if circumstance in {"small_room", "indoor", "close_distance"}:
        return "low"
    if circumstance == "outdoor" or event in {"walk", "active"}:
        return "high"
    if event in {"restaurant", "cafe", "meeting", "study", "work"}:
        return "low"
    return "medium"


def infer_time_of_day(dt: datetime) -> str:
    hour = dt.hour
    if 5 <= hour < 11:
        return "morning"
    if 11 <= hour < 17:
        return "day"
    if 17 <= hour < 22:
        return "evening"
    return "night"


def infer_season(dt: datetime, latitude: float | None) -> str:
    month = dt.month
    north = True if latitude is None else latitude >= 0
    if month in (3, 4, 5): season = "spring"
    elif month in (6, 7, 8): season = "summer"
    elif month in (9, 10, 11): season = "autumn"
    else: season = "winter"
    if north:
        return season
    return {"spring": "autumn", "summer": "winter", "autumn": "spring", "winter": "summer"}[season]


def build_situation(
    *, event: str, outfit_text: str, circumstance: str, effect: str, weather: dict,
    place: str = "", target_datetime: datetime | None = None, latitude: float | None = None,
    longitude: float | None = None, timezone: str | None = None, manual_time: str = "auto",
    manual_season: str = "auto", outdoor_exposure: str | None = None,
) -> Situation:
    normalized_event, modifiers, importance, formality = normalize_event(event)
    target = target_datetime or datetime.now(ZoneInfo(timezone)) if timezone else (target_datetime or datetime.now().astimezone())
    if target.tzinfo is None:
        target = target.replace(tzinfo=ZoneInfo(timezone) if timezone else datetime.now().astimezone().tzinfo)
    time_of_day = manual_time if manual_time != "auto" else infer_time_of_day(target)
    season = manual_season if manual_season != "auto" else infer_season(target, latitude)
    exposure = outdoor_exposure or infer_outdoor_exposure(normalized_event, circumstance)
    return Situation(
        event=normalized_event,
        event_modifiers=modifiers,
        importance=importance,
        formality=formality,
        circumstance=circumstance,
        outdoor_exposure=exposure,
        desired_effect=effect,
        time_of_day=time_of_day,
        season=season,
        temperature=float(weather.get("temperature") if weather.get("temperature") is not None else 20.0),
        feels_like=float(weather["feels_like"]) if weather.get("feels_like") is not None else None,
        humidity=float(weather["humidity"]) if weather.get("humidity") is not None else None,
        rain=float(weather.get("rain") or 0.0),
        precipitation=float(weather.get("precipitation") or 0.0),
        cloud_cover=float(weather["cloud_cover"]) if weather.get("cloud_cover") is not None else None,
        wind_speed=float(weather["wind_speed"]) if weather.get("wind_speed") is not None else None,
        is_day=bool(weather.get("is_day", time_of_day in {"morning", "day"})),
        outfit=parse_outfit_profile(outfit_text),
        target_datetime=target,
        location=place,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone,
        weather_source=str(weather.get("source", "current")),
    )


def parse_free_text(text: str, *, default_datetime: datetime | None = None, latitude: float | None = None, timezone: str | None = None) -> dict:
    normalized = (text or "").lower()
    event = "casual"
    for token, value in EVENT_ALIASES.items():
        if token in normalized:
            event = value
            break
    effect = "any"
    for token, value in EFFECT_ALIASES.items():
        if token in normalized:
            effect = value
            break
    circumstance = "outdoor"
    for pattern, value in CIRCUMSTANCE_ALIASES.items():
        if re.search(pattern, normalized):
            circumstance = value
            break
    temp_match = re.search(r"(?<!\d)([-+]?\d{1,2})(?:\s*°|\s*град|\s*c\b)", normalized)
    humidity_match = re.search(r"влажност\w*\s*(\d{1,3})\s*%", normalized)
    target = default_datetime or (datetime.now(ZoneInfo(timezone)) if timezone else datetime.now().astimezone())
    if "утром" in normalized: target = target.replace(hour=8, minute=0, second=0, microsecond=0)
    elif "днем" in normalized or "днём" in normalized: target = target.replace(hour=14, minute=0, second=0, microsecond=0)
    elif "вечером" in normalized: target = target.replace(hour=19, minute=0, second=0, microsecond=0)
    elif "ночью" in normalized: target = target.replace(hour=23, minute=0, second=0, microsecond=0)
    return {
        "event": event,
        "circumstance": circumstance,
        "effect": effect,
        "temperature": float(temp_match.group(1)) if temp_match else None,
        "humidity": float(humidity_match.group(1)) if humidity_match else None,
        "target_datetime": target,
        "outfit_text": text,
        "time_of_day": infer_time_of_day(target),
        "season": infer_season(target, latitude),
    }
