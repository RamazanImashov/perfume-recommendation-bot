from __future__ import annotations

from dataclasses import dataclass

from app.models.perfume import PerfumeProfile
from app.models.situation import Situation


@dataclass(frozen=True)
class SprayAdvice:
    count: int
    locations: list[str]
    explanation: str


def recommend_sprays(profile: PerfumeProfile, situation: Situation, layering: bool = False) -> SprayAdvice:
    base = round((profile.base_sprays_min + profile.base_sprays_max) / 2)
    count = max(1, base)
    reasons: list[str] = []

    if profile.projection >= 4.0:
        count -= 1
        reasons.append("сильная проекция")
    if profile.density >= 4.0:
        count -= 1
        reasons.append("плотный профиль")
    if situation.temperature >= 28:
        count -= 1
        reasons.append("жара")
    if (situation.humidity or 0) >= 75 and situation.temperature >= 24:
        count -= 1
        reasons.append("высокая влажность")
    if situation.circumstance in {"small_room", "close_distance"}:
        count -= 1
        reasons.append("близкая дистанция/маленькое помещение")
    elif situation.outdoor_exposure == "high" and (situation.wind_speed or 0) >= 18 and profile.projection <= 3.2:
        count += 1
        reasons.append("ветер и улица")
    if layering:
        count = min(count, 2)
        reasons.append("это часть наслаивания")

    count = max(1, min(6, count))
    if situation.circumstance in {"small_room", "close_distance"}:
        locations = ["грудь под одежду"] if count == 1 else ["грудь под одежду", "бок шеи"]
    elif count <= 2:
        locations = ["грудь", "бок шеи"][:count]
    else:
        locations = ["шея слева", "шея справа", "грудь", "затылок", "одежда с расстояния", "запястье"][:count]
    explanation = ", ".join(reasons[:2]) if reasons else "стандартная нагрузка для этого аромата"
    return SprayAdvice(count=count, locations=locations, explanation=explanation)


def recommend_layering_sprays(base: PerfumeProfile, top: PerfumeProfile, situation: Situation) -> str:
    base_advice = recommend_sprays(base, situation, layering=True)
    top_advice = recommend_sprays(top, situation, layering=True)
    total = base_advice.count + top_advice.count
    max_load = 2 if situation.circumstance in {"small_room", "close_distance"} else 3 if situation.temperature >= 27 else 4
    if total > max_load:
        if base.density >= top.density:
            base_count, top_count = 1, max(1, max_load - 1)
        else:
            top_count, base_count = 1, max(1, max_load - 1)
    else:
        base_count, top_count = base_advice.count, top_advice.count
    return f"{base.name}: {base_count} пш.; {top.name}: {top_count} пш."
