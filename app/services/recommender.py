from __future__ import annotations

from datetime import datetime

from app.data.perfumes import PERFUMES
from app.models.perfume import PerfumeProfile, build_perfume_profile
from app.models.recommendation import RecommendationResult
from app.models.situation import Situation
from app.services.scoring import finalize_confidence, score_perfume as score_profile
from app.services.scoring_config import DIVERSITY_MAX_DROP_EXPRESSIVE, DIVERSITY_MAX_DROP_SAFE
from app.services.situation_parser import build_situation

EVENT_MAP = {
    "Учеба": "study", "Работа": "work", "Обычный день": "casual", "Прогулка": "walk", "Кафе": "cafe", "Свидание": "date",
    "Ресторан": "restaurant", "Клуб": "club", "День рождения": "birthday", "Важная встреча": "important_meeting",
    "Спорт / активный день": "active",
}
CIRCUMSTANCE_MAP = {"Улица": "outdoor", "Помещение": "indoor", "Маленькое помещение": "small_room", "Клуб / шумное место": "club", "Близкая дистанция": "close_distance"}
EFFECT_MAP = {"Чисто": "clean", "Дорого": "expensive", "Сексуально": "sexy", "Заметно": "noticeable", "Спокойно": "calm", "Необычно": "unusual", "Не важно": "any"}
TIME_MAP = {"Авто": "auto", "Утро": "morning", "День": "day", "Вечер": "evening", "Ночь": "night"}
SEASON_MAP = {"Авто": "auto", "Весна": "spring", "Лето": "summer", "Осень": "autumn", "Зима": "winter"}


def find_perfume(query: str) -> dict | None:
    q = (query or "").lower().strip()
    if not q:
        return None
    exact = [p for p in PERFUMES if q in {str(p.get("name", "")).lower(), f"{p.get('name','')} {p.get('brand','')}".lower()}]
    if exact:
        return exact[0]
    return next((p for p in PERFUMES if q in f"{p.get('name','')} {p.get('brand','')}".lower()), None)


def _profile_map() -> dict[str, PerfumeProfile]:
    return {p["name"]: build_perfume_profile(p) for p in PERFUMES}


def _character_distance(a: PerfumeProfile, b: PerfumeProfile) -> float:
    attrs = ("freshness", "sweetness", "warmth", "density", "darkness", "cleanliness", "formality", "romantic", "uniqueness")
    return sum(abs(getattr(a, x) - getattr(b, x)) for x in attrs) / len(attrs)


def _diversity_rerank(ranked: list[RecommendationResult], profiles: dict[str, PerfumeProfile], limit: int) -> list[RecommendationResult]:
    if not ranked:
        return []
    top = ranked[0]
    top.role = "Лучший выбор"
    if limit == 1:
        return [top]
    remaining = ranked[1:]
    safe_pool = [r for r in remaining if r.score >= top.score - DIVERSITY_MAX_DROP_SAFE]
    safe = max(safe_pool or remaining, key=lambda r: (r.score - len(r.hard_warnings) * 7 - r.breakdown.environment_score * -0.03), default=None)
    selected = [top]
    if safe:
        safe.role = "Безопасный вариант"
        selected.append(safe)
    if limit >= 3:
        expressive_pool = [r for r in remaining if r not in selected and r.score >= top.score - DIVERSITY_MAX_DROP_EXPRESSIVE]
        if expressive_pool:
            expressive = max(expressive_pool, key=lambda r: (_character_distance(profiles[top.name], profiles[r.name]) * 7 + r.score))
            expressive.role = "Более выразительный вариант"
            selected.append(expressive)
    for r in ranked:
        if len(selected) >= limit:
            break
        if r not in selected:
            r.role = "Альтернатива"
            selected.append(r)
    return selected[:limit]


def recommend_situation(situation: Situation, limit: int = 3, personal_snapshot: dict | None = None, diversity: bool = True) -> list[RecommendationResult]:
    profiles = _profile_map()
    ranked = [score_profile(profile, situation, personal_snapshot) for profile in profiles.values()]
    ranked.sort(key=lambda r: (-r.score, r.brand.lower(), r.name.lower()))
    history_count = int((personal_snapshot or {}).get("history_count", 0))
    finalize_confidence(ranked, profiles, situation, history_count)
    if diversity and limit <= 3:
        return _diversity_rerank(ranked, profiles, limit)
    return ranked[:limit]


def score_perfume(
    perfume: dict,
    weather: dict,
    event: str,
    outfit_text: str,
    circumstance: str,
    effect: str,
    time_of_day: str = "auto",
    season: str = "auto",
    personal_snapshot: dict | None = None,
) -> dict:
    situation = build_situation(
        event=event, outfit_text=outfit_text, circumstance=circumstance, effect=effect, weather=weather,
        manual_time=time_of_day, manual_season=season,
    )
    result = score_profile(build_perfume_profile(perfume), situation, personal_snapshot)
    return {
        "score": result.score,
        "confidence": result.confidence,
        "perfume": perfume,
        "reasons": [x for values in result.breakdown.evidence.values() for x in values][:4],
        "warnings": result.hard_warnings,
        "breakdown": result.breakdown.model_dump(),
        "result": result,
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
    personal_snapshot: dict | None = None,
    target_datetime: datetime | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    timezone: str | None = None,
    place: str = "",
    outdoor_exposure: str | None = None,
) -> list[dict]:
    situation = build_situation(
        event=event, outfit_text=outfit_text, circumstance=circumstance, effect=effect, weather=weather,
        place=place, target_datetime=target_datetime, latitude=latitude, longitude=longitude, timezone=timezone,
        manual_time=time_of_day, manual_season=season, outdoor_exposure=outdoor_exposure,
    )
    results = recommend_situation(situation, limit=limit, personal_snapshot=personal_snapshot, diversity=limit <= 3)
    by_name = {p["name"]: p for p in PERFUMES}
    return [{
        "score": r.score, "confidence": r.confidence, "confidence_label": r.confidence_label, "perfume": by_name[r.name],
        "reasons": [x for values in r.breakdown.evidence.values() for x in values][:4], "warnings": r.hard_warnings,
        "breakdown": r.breakdown.model_dump(), "role": r.role, "result": r, "situation": situation.model_dump(mode="json"),
    } for r in results]


def adjust_sprays(base_sprays: str, circumstance: str, weather: dict) -> str:
    # Backward-compatible helper. New UI should use RecommendationResult spray advice.
    temp = float(weather.get("temperature") or 20)
    if circumstance in {"indoor", "small_room", "close_distance"}:
        return f"{base_sprays}; лучше нижняя граница"
    if temp >= 28:
        return f"{base_sprays}; в жару нижняя граница"
    return base_sprays


def apply_ai_adjustments(results: list[RecommendationResult], adjustments: dict[str, float]) -> list[RecommendationResult]:
    if not adjustments:
        return results
    for result in results:
        if result.hard_warnings:
            continue
        adjustment = max(-3.0, min(3.0, float(adjustments.get(result.name, 0.0))))
        result.ai_adjustment = adjustment
        result.breakdown.ai_adjustment = adjustment
        result.score = max(0.0, min(100.0, round(result.score + adjustment, 1)))
    results.sort(key=lambda r: (-r.score, r.brand.lower(), r.name.lower()))
    return results


def diversify_results(results: list[RecommendationResult], limit: int = 3) -> list[RecommendationResult]:
    return _diversity_rerank(results, _profile_map(), limit)
