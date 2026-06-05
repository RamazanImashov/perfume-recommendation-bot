from __future__ import annotations

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
    "Авто": "auto",
    "Утро": "morning",
    "День": "day",
    "Вечер": "evening",
    "Ночь": "night",
}

SEASON_MAP = {
    "Авто": "auto",
    "Весна": "spring",
    "Лето": "summer",
    "Осень": "autumn",
    "Зима": "winter",
}

STRONG_NOTES_FOR_HOT = {"tobacco", "coffee", "leather", "dense", "vanilla", "gourmand", "oud"}


def _safe_list(perfume: dict, key: str) -> list[str]:
    value = perfume.get(key, [])
    if value is None:
        return []
    if isinstance(value, dict):
        result: list[str] = []
        for item in value.values():
            if isinstance(item, list):
                result.extend(str(x) for x in item)
            else:
                result.append(str(item))
        return result
    if isinstance(value, list):
        return [str(x) for x in value]
    return [str(value)]


def _profile_tags(perfume: dict) -> set[str]:
    tags: set[str] = set()
    for key in ("type", "effects", "weather_tags", "occasions", "outfits"):
        tags.update(_safe_list(perfume, key))
    tags.update(_safe_list(perfume, "notes"))
    return tags


def _weather_reason(weather: dict, perfume: dict) -> tuple[int, str]:
    temp = float(weather.get("temperature") or 0)
    min_t = float(perfume.get("weather_min", -50))
    max_t = float(perfume.get("weather_max", 60))

    if min_t <= temp <= max_t:
        return 4, f"{temp:g}°C подходит"

    if temp > max_t:
        return -3, "жарковато для него"

    return -2, "холодновато для него"


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

    occasions = _safe_list(perfume, "occasions")
    outfits = _safe_list(perfume, "outfits")
    effects = _safe_list(perfume, "effects")
    weather_tag_list = _safe_list(perfume, "weather_tags")
    perfume_times = _safe_list(perfume, "time_of_day")
    perfume_seasons = _safe_list(perfume, "seasons")
    avoid_list = _safe_list(perfume, "avoid")
    strength = str(perfume.get("strength", "medium"))
    tags = _profile_tags(perfume)

    weather_score, weather_reason = _weather_reason(weather, perfume)
    score += weather_score
    reasons.append(weather_reason)

    if event in occasions:
        score += 5
        reasons.append("сценарий совпадает")
    else:
        if event == "birthday" and ("club" in occasions or "party" in occasions):
            score += 2
            reasons.append("подходит для вечеринки/дня рождения")
        if event == "ordinary_day" and ("study" in occasions or "day" in occasions or "casual" in occasions):
            score += 2
            reasons.append("норм для обычного дня")

    matching_outfit = outfit_tags.intersection(set(outfits))
    if matching_outfit:
        score += min(5, len(matching_outfit) * 2)
        reasons.append("совпал с образом")
    else:
        score -= 1

    if effect != "any" and effect in effects:
        score += 4
        reasons.append("дает нужный эффект")

    if time_of_day != "auto":
        if time_of_day in perfume_times:
            score += 3
            reasons.append("подходит по времени")
        else:
            score -= 1

    if season != "auto":
        if season in perfume_seasons:
            score += 3
            reasons.append("подходит по сезону")
        else:
            score -= 1

    if "rainy" in w_tags and ("rain" in occasions or "rainy" in weather_tag_list):
        score += 3
        reasons.append("хорошо на дождь/пасмурность")

    if "cloudy" in w_tags and "cloudy" in weather_tag_list:
        score += 1

    if circumstance == "small_room" and strength == "strong":
        score -= 4
        warnings.append("в маленьком помещении лучше аккуратно")

    if circumstance == "indoor" and strength == "strong":
        score -= 1
        warnings.append("в помещении снизь на 1 пшик")

    if circumstance == "club" and ("club" in occasions or "party" in occasions):
        score += 4
        reasons.append("хватит заметности для шума")

    if circumstance == "close_distance":
        if strength in {"soft", "medium"} or "close_distance" in occasions:
            score += 3
            reasons.append("норм на близкую дистанцию")
        else:
            score -= 2
            warnings.append("может быть резким близко")

    if "hot" in w_tags and tags.intersection(STRONG_NOTES_FOR_HOT):
        score -= 5
        warnings.append("в жару тяжелые ноты рискованны")

    for avoid in avoid_list:
        if avoid in {event, circumstance, time_of_day, season} or avoid in w_tags or avoid in outfit_tags:
            score -= 3
            warnings.append(f"ограничение: {avoid}")

    return {
        "score": score,
        "perfume": perfume,
        "reasons": _unique(reasons)[:3],
        "warnings": _unique(warnings)[:2],
        "outfit_tags": sorted(outfit_tags),
        "weather_tags": sorted(w_tags),
    }


def _unique(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


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
        score_perfume(
            perfume=perfume,
            weather=weather,
            event=event,
            outfit_text=outfit_text,
            circumstance=circumstance,
            effect=effect,
            time_of_day=time_of_day,
            season=season,
        )
        for perfume in PERFUMES
    ]
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:limit]


def adjust_sprays(base_sprays: str, circumstance: str, weather: dict) -> str:
    temp = float(weather.get("temperature") or 0)

    if circumstance in {"indoor", "small_room", "close_distance"}:
        return f"{base_sprays}; лучше минус 1 пшик"

    if temp >= 28:
        return f"{base_sprays}; держись нижней границы"

    return base_sprays


def find_perfume(query: str) -> dict | None:
    q = query.lower().strip()
    if not q:
        return None

    for perfume in PERFUMES:
        full_name = f"{perfume.get('name', '')} {perfume.get('brand', '')}".lower()
        if q == perfume.get("name", "").lower() or q == full_name:
            return perfume

    for perfume in PERFUMES:
        full_name = f"{perfume.get('name', '')} {perfume.get('brand', '')}".lower()
        if q in full_name:
            return perfume

    return None
