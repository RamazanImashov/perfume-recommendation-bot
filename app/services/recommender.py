
from __future__ import annotations

from collections.abc import Iterable
from app.data.perfumes import PERFUMES
from app.services.outfit_parser import parse_outfit
from app.services.weather import weather_tags


EVENT_MAP = {
    "Учеба": "study",
    "Обычный день": "ordinary_day",
    "Прогулка": "walk",
    "Кафе": "cafe",
    "Свидание": "date",
    "Ресторан": "restaurant",
    "Клуб": "club",
    "День рождения": "birthday",
    "Важная встреча": "important_meeting",
    "Спорт / активный день": "active_day",
}

CIRCUMSTANCE_MAP = {
    "Улица": "outdoor",
    "Помещение": "indoor",
    "Маленькое помещение": "small_room",
    "Клуб / шумное место": "club",
    "Близкая дистанция": "close_distance",
}

EFFECT_MAP = {
    "Чисто": "clean",
    "Дорого": "expensive",
    "Сексуально": "sexy",
    "Заметно": "noticeable",
    "Спокойно": "calm",
    "Необычно": "unusual",
    "Не важно": "any",
}

TIME_MAP = {
    "Утро": "morning",
    "День": "day",
    "Вечер": "evening",
    "Ночь": "night",
    "Авто по погоде": "auto",
}

SEASON_MAP = {
    "Весна": "spring",
    "Лето": "summer",
    "Осень": "autumn",
    "Зима": "winter",
    "Авто по погоде": "auto",
}

STRONG_NOTES_FOR_HOT = {"tobacco", "coffee", "leather", "dense", "vanilla", "gourmand", "praline", "cinnamon"}


def _as_set(value) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {value}
    if isinstance(value, dict):
        result: set[str] = set()
        for item in value.values():
            result.update(_as_set(item))
        return result
    if isinstance(value, Iterable):
        result: set[str] = set()
        for item in value:
            result.update(_as_set(item))
        return result
    return {str(value)}


def infer_season_from_temperature(weather: dict) -> str:
    temp = float(weather.get("temperature") or 0)
    if temp >= 24:
        return "summer"
    if temp >= 12:
        return "spring"
    if temp >= 3:
        return "autumn"
    return "winter"


def infer_time_from_weather(weather: dict) -> str:
    return "day" if weather.get("is_day", True) else "night"


def _weather_reason(weather: dict, perfume: dict) -> tuple[int, str]:
    temp = float(weather.get("temperature") or 0)
    min_t = float(perfume.get("weather_min", -50))
    max_t = float(perfume.get("weather_max", 50))

    if min_t <= temp <= max_t:
        return 4, f"температура {temp:g}°C попадает в диапазон {min_t:g}–{max_t:g}°C"

    if temp > max_t:
        return -3, f"сейчас теплее идеального диапазона {min_t:g}–{max_t:g}°C"

    return -2, f"сейчас холоднее идеального диапазона {min_t:g}–{max_t:g}°C"


def score_perfume(
    perfume: dict,
    weather: dict,
    event: str,
    outfit_text: str,
    circumstance: str,
    effect: str,
    time_of_day: str = "auto",
    season: str = "auto",
) -> dict:
    score = 0
    reasons: list[str] = []
    warnings: list[str] = []

    w_tags = weather_tags(weather)
    outfit_tags = parse_outfit(outfit_text)

    if time_of_day == "auto":
        time_of_day = infer_time_from_weather(weather)
    if season == "auto":
        season = infer_season_from_temperature(weather)

    occasions = _as_set(perfume.get("occasions"))
    outfits = _as_set(perfume.get("outfits"))
    effects = _as_set(perfume.get("effects"))
    weather_tag_list = _as_set(perfume.get("weather_tags"))
    time_tags = _as_set(perfume.get("time_of_day") or perfume.get("time_tags"))
    seasons = _as_set(perfume.get("seasons"))
    scent_profile = _as_set(perfume.get("type")) | _as_set(perfume.get("notes"))
    avoid_list = _as_set(perfume.get("avoid"))
    strength = perfume.get("strength", "medium")

    weather_score, weather_reason = _weather_reason(weather, perfume)
    score += weather_score
    reasons.append(weather_reason if weather_score > 0 else f"минус: {weather_reason}")

    if event in occasions:
        score += 5
        reasons.append("событие совпадает с назначением аромата")
    else:
        if event == "birthday" and ({"club", "party", "bar", "evening"} & occasions):
            score += 2
            reasons.append("для дня рождения подходит вечерний/клубный характер")
        if event == "ordinary_day" and ({"study", "day", "walk", "city", "casual"} & occasions):
            score += 2
            reasons.append("подходит для обычного дневного выхода")

    matching_outfit = outfit_tags.intersection(outfits)
    if matching_outfit:
        score += min(5, len(matching_outfit) * 2)
        reasons.append("образ совпал по тегам: " + ", ".join(sorted(matching_outfit)))
    else:
        score -= 1
        warnings.append("образ не сильно совпал с этим ароматом")

    if effect != "any" and effect in effects:
        score += 4
        reasons.append("нужный эффект совпадает")

    if time_of_day in time_tags:
        score += 3
        reasons.append(f"подходит под время суток: {time_of_day}")
    else:
        if time_of_day == "morning" and strength == "strong":
            score -= 2
            warnings.append("для утра может быть слишком плотным")
        if time_of_day in {"evening", "night"} and "morning" in time_tags and strength == "soft":
            score -= 1
            warnings.append("для вечера может быть слишком легким")

    if season in seasons:
        score += 3
        reasons.append(f"сезон совпадает: {season}")
    else:
        if season == "summer" and scent_profile.intersection(STRONG_NOTES_FOR_HOT):
            score -= 4
            warnings.append("летом тяжелые сладкие/ванильные/кожаные ноты лучше осторожно")
        if season == "winter" and strength == "soft":
            score -= 2
            warnings.append("зимой может быть слишком легким")

    if "rainy" in w_tags and ({"rain", "rainy", "rainy_evening"} & occasions or "rainy" in weather_tag_list):
        score += 3
        reasons.append("дождь/пасмурность усиливает этот профиль")

    if "cloudy" in w_tags and "cloudy" in weather_tag_list:
        score += 1
        reasons.append("пасмурная погода подходит")

    if circumstance == "small_room" and strength == "strong":
        score -= 4
        warnings.append("сильный аромат может душить в маленьком помещении")

    if circumstance == "indoor" and strength == "strong":
        score -= 1
        warnings.append("в помещении лучше снизить количество пшиков")

    if circumstance == "club" and "club" in occasions:
        score += 4
        reasons.append("для шумного места хватает заметности")

    if circumstance == "close_distance":
        if strength in {"soft", "medium"} or "close_distance" in occasions:
            score += 3
            reasons.append("не слишком агрессивен для близкой дистанции")
        else:
            score -= 2
            warnings.append("для близкой дистанции может быть резким")

    if "hot" in w_tags and scent_profile.intersection(STRONG_NOTES_FOR_HOT):
        score -= 5
        warnings.append("в жару тяжелые сладкие/кожаные/кофейные ноты лучше избегать")

    for avoid in avoid_list:
        if avoid in {event, circumstance, time_of_day, season} or avoid in w_tags or avoid in outfit_tags:
            score -= 3
            warnings.append(f"есть ограничение: {avoid}")

    return {
        "score": score,
        "perfume": perfume,
        "reasons": reasons[:5],
        "warnings": warnings[:4],
        "outfit_tags": sorted(outfit_tags),
        "weather_tags": sorted(w_tags),
        "time_of_day": time_of_day,
        "season": season,
    }


def recommend(
    weather: dict,
    event: str,
    outfit_text: str,
    circumstance: str,
    effect: str,
    time_of_day: str = "auto",
    season: str = "auto",
    limit: int = 3,
) -> list[dict]:
    scored = [
        score_perfume(perfume, weather, event, outfit_text, circumstance, effect, time_of_day, season)
        for perfume in PERFUMES
    ]
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:limit]


def adjust_sprays(base_sprays: str, circumstance: str, weather: dict) -> str:
    temp = float(weather.get("temperature") or 0)

    if circumstance in {"indoor", "small_room", "close_distance"}:
        return f"{base_sprays}; если помещение/близкая дистанция — снизь на 1 пшик"

    if temp >= 28:
        return f"{base_sprays}; из-за жары лучше не превышать нижнюю границу"

    return base_sprays
