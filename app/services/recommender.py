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

STRONG_NOTES_FOR_HOT = {"tobacco", "coffee", "leather", "dense", "vanilla", "gourmand"}


def _weather_reason(weather: dict, perfume: dict) -> tuple[int, str]:
    temp = float(weather.get("temperature") or 0)
    min_t = perfume["weather_min"]
    max_t = perfume["weather_max"]

    if min_t <= temp <= max_t:
        return 4, f"температура {temp:g}°C попадает в его диапазон {min_t}–{max_t}°C"

    if temp > max_t:
        return -3, f"сейчас теплее его идеального диапазона {min_t}–{max_t}°C"

    return -2, f"сейчас холоднее его идеального диапазона {min_t}–{max_t}°C"


def score_perfume(
    perfume: dict,
    weather: dict,
    event: str,
    outfit_text: str,
    circumstance: str,
    effect: str,
) -> dict:
    score = 0
    reasons: list[str] = []
    warnings: list[str] = []

    w_tags = weather_tags(weather)
    outfit_tags = parse_outfit(outfit_text)

    weather_score, weather_reason = _weather_reason(weather, perfume)
    score += weather_score
    reasons.append(weather_reason if weather_score > 0 else f"минус: {weather_reason}")

    if event in perfume["occasions"]:
        score += 5
        reasons.append("событие совпадает с назначением аромата")
    else:
        # Soft event links.
        if event == "birthday" and "club" in perfume["occasions"]:
            score += 2
            reasons.append("для дня рождения подходит вечерний/клубный характер")
        if event == "ordinary_day" and ("study" in perfume["occasions"] or "day" in perfume["occasions"]):
            score += 2
            reasons.append("подходит для обычного дневного выхода")

    matching_outfit = outfit_tags.intersection(set(perfume["outfits"]))
    if matching_outfit:
        score += min(5, len(matching_outfit) * 2)
        reasons.append("образ совпал по тегам: " + ", ".join(sorted(matching_outfit)))
    else:
        score -= 1
        warnings.append("образ не сильно совпал с этим ароматом")

    if effect != "any" and effect in perfume["effects"]:
        score += 4
        reasons.append("нужный эффект совпадает")

    if "rainy" in w_tags and ("rain" in perfume["occasions"] or "rainy" in perfume["weather_tags"]):
        score += 3
        reasons.append("дождь/пасмурность усиливает этот профиль")

    if "cloudy" in w_tags and "cloudy" in perfume["weather_tags"]:
        score += 1
        reasons.append("пасмурная погода подходит")

    if "night" in w_tags and "night" in perfume.get("time_of_day", []):
        score += 2
        reasons.append("по времени суток больше вечерний/ночной вариант")

    if "day" in w_tags and "day" in perfume.get("time_of_day", []):
        score += 2
        reasons.append("по времени суток подходит для дня")

    if circumstance == "small_room" and perfume["strength"] == "strong":
        score -= 4
        warnings.append("сильный аромат может душить в маленьком помещении")

    if circumstance == "indoor" and perfume["strength"] == "strong":
        score -= 1
        warnings.append("в помещении лучше снизить количество пшиков")

    if circumstance == "club" and "club" in perfume["occasions"]:
        score += 4
        reasons.append("для шумного места хватает заметности")

    if circumstance == "close_distance":
        if perfume["strength"] in {"soft", "medium"} or "close_distance" in perfume["occasions"]:
            score += 3
            reasons.append("не слишком агрессивен для близкой дистанции")
        else:
            score -= 2
            warnings.append("для близкой дистанции может быть резким")

    notes = perfume.get("type", [])
    
    if "hot" in w_tags and set(notes).intersection(STRONG_NOTES_FOR_HOT):
        score -= 5
        warnings.append("в жару тяжелые сладкие/кожаные/кофейные ноты лучше избегать")

    for avoid in perfume.get("avoid", []):
        if avoid in {event, circumstance} or avoid in w_tags or avoid in outfit_tags:
            score -= 3
            warnings.append(f"есть ограничение: {avoid}")

    return {
        "score": score,
        "perfume": perfume,
        "reasons": reasons[:4],
        "warnings": warnings[:3],
        "outfit_tags": sorted(outfit_tags),
        "weather_tags": sorted(w_tags),
    }


def recommend(
    weather: dict,
    event: str,
    outfit_text: str,
    circumstance: str,
    effect: str,
    limit: int = 3,
) -> list[dict]:
    scored = [
        score_perfume(perfume, weather, event, outfit_text, circumstance, effect)
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
