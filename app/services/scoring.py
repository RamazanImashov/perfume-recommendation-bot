from __future__ import annotations

import math
import statistics
from typing import Iterable

from app.models.perfume import EVENT_SCORE_KEYS, PerfumeProfile, build_perfume_profile
from app.models.recommendation import RecommendationResult, ScoreBreakdown
from app.models.situation import Situation
from app.services.personalization import personal_adjustment
from app.services.scoring_config import (
    CONFIDENCE_THRESHOLDS,
    HARD_PENALTIES,
    OUTDOOR_EXPOSURE_CLIMATE_FACTOR,
    SCORE_WEIGHTS,
    TEMPERATURE_CURVE,
)
from app.services.spray_advisor import recommend_sprays


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _temperature_score(profile: PerfumeProfile, temp: float) -> float:
    ideal, cmin, cmax, hmin, hmax = (
        profile.ideal_temperature,
        profile.comfortable_temperature_min,
        profile.comfortable_temperature_max,
        profile.hard_temperature_min,
        profile.hard_temperature_max,
    )
    if temp < hmin or temp > hmax:
        return TEMPERATURE_CURVE["outside_score"]
    if cmin <= temp <= cmax:
        span = max(1.0, ideal - cmin if temp <= ideal else cmax - ideal)
        ratio = min(1.0, abs(temp - ideal) / span)
        return 100.0 - (100.0 - TEMPERATURE_CURVE["comfort_edge_score"]) * ratio ** 1.35
    if temp < cmin:
        ratio = (cmin - temp) / max(1.0, cmin - hmin)
    else:
        ratio = (temp - cmax) / max(1.0, hmax - cmax)
    return TEMPERATURE_CURVE["comfort_edge_score"] - (TEMPERATURE_CURVE["comfort_edge_score"] - TEMPERATURE_CURVE["hard_edge_score"]) * min(1.0, ratio)


def climate_score(profile: PerfumeProfile, situation: Situation) -> tuple[float, list[str]]:
    temp = situation.feels_like if situation.feels_like is not None else situation.temperature
    score = _temperature_score(profile, temp)
    evidence: list[str] = []
    humidity = situation.humidity
    if humidity is not None:
        humidity_fit = 100.0 - abs(profile.humidity_preference - humidity / 20.0) * 14.0
        score = score * 0.82 + clamp(humidity_fit) * 0.18
    if situation.temperature >= 27 and (humidity or 0) >= 70:
        score -= max(0.0, profile.density - 2.7) * 7.0 + max(0.0, profile.sweetness - 3.0) * 4.0
        if profile.freshness >= 3.8:
            score += 5.0
        evidence.append("влажная жара усиливает плотность и сладость")
    elif situation.temperature >= 27 and humidity is not None and humidity <= 45:
        score += (profile.freshness - profile.density) * 2.5
        evidence.append("сухая жара лучше переносит свежие профили")
    elif situation.temperature <= 8 and (humidity or 0) >= 75:
        score += (profile.warmth - 2.5) * 3.0
        evidence.append("сырой холод поддерживает тёплые профили")
    elif situation.temperature <= 8 and humidity is not None and humidity <= 50:
        score += (profile.warmth + profile.density - 5.0) * 2.0
        evidence.append("сухой холод раскрывает тёплые и плотные ароматы")
    if situation.rain + situation.precipitation > 0:
        score += (profile.formality + profile.warmth - profile.freshness) * 1.2
        evidence.append("дождь делает древесно-тёплые профили уместнее")
    if (situation.wind_speed or 0) >= 20 and situation.outdoor_exposure == "high":
        score += (profile.projection - 3.0) * 4.0
        evidence.append("на ветру важна проекция")
    if situation.temperature >= 27 and (situation.cloud_cover or 0) < 35 and situation.is_day:
        score += (profile.freshness - profile.warmth) * 2.5
        evidence.append("солнечная жара требует более лёгкого профиля")
    exposure_factor = OUTDOOR_EXPOSURE_CLIMATE_FACTOR.get(situation.outdoor_exposure, 0.72)
    score = 50.0 + (score - 50.0) * exposure_factor
    if not evidence:
        evidence.append(f"температурный профиль близок к {profile.ideal_temperature:g}°C")
    return clamp(score), evidence


def event_score(profile: PerfumeProfile, situation: Situation) -> tuple[float, list[str]]:
    key = EVENT_SCORE_KEYS.get(situation.event, "casual_score")
    base = getattr(profile, key, 2.5) * 20.0
    event_label = {"study":"учёбы","work":"работы","meeting":"встречи","walk":"прогулки","cafe":"кафе","date":"свидания","restaurant":"ресторана","party":"вечеринки","club":"клуба","birthday":"дня рождения","active":"активного дня","casual":"обычного дня"}.get(situation.event, situation.event)
    evidence = [f"характер аромата подходит для {event_label}"] if base >= 72 else []
    if situation.importance == "high":
        formality_fit = 100 - abs(profile.formality - max(3.8, situation.formality)) * 18
        base = base * 0.75 + clamp(formality_fit) * 0.25
        if formality_fit >= 75:
            evidence.append("достаточно собранный для важного события")
    if situation.event == "active":
        base -= max(0, profile.density - 3.0) * 10 + max(0, profile.sweetness - 3.2) * 6
    return clamp(base), evidence


def effect_score(profile: PerfumeProfile, situation: Situation) -> tuple[float, list[str]]:
    if situation.desired_effect == "any":
        return 70.0, []
    value = profile.effects_profile.get(situation.desired_effect, 2.5) * 20.0
    effect_label = {"clean":"чистый","expensive":"дорогой","sexy":"сексуальный","noticeable":"заметный","calm":"спокойный","unusual":"необычный"}.get(situation.desired_effect, situation.desired_effect)
    return clamp(value), [f"даёт нужный {effect_label} характер"] if value >= 72 else []


def environment_score(profile: PerfumeProfile, situation: Situation) -> tuple[float, list[str]]:
    if situation.circumstance == "close_distance":
        score = profile.close_distance_score * 20.0
        reason = "комфортен на близкой дистанции"
    elif situation.circumstance in {"indoor", "small_room"}:
        score = profile.indoor_score * 20.0
        reason = "контролируемая проекция подходит помещению"
    elif situation.outdoor_exposure == "high":
        score = profile.outdoor_score * 20.0
        reason = "проекция подходит для улицы"
    else:
        score = (profile.indoor_score + profile.outdoor_score) * 10.0
        reason = "балансирует помещение и улицу"
    return clamp(score), [reason] if score >= 72 else []


def outfit_score(profile: PerfumeProfile, situation: Situation) -> tuple[float, list[str]]:
    outfit = situation.outfit
    legacy = profile.legacy
    legacy_outfits = {str(x).lower() for x in legacy.get("outfits", [])}
    style_hits = len(set(outfit.style) & legacy_outfits)
    if "smart_casual" in outfit.style and profile.formality >= 3.1: style_hits += 1
    if "formal" in outfit.style and profile.formality >= 4.0: style_hits += 1
    if "sport" in outfit.style and profile.freshness >= 3.5 and profile.density <= 3.2: style_hits += 1
    style = clamp(55 + style_hits * 18 - (12 if "sport" in outfit.style and profile.density >= 4 else 0))
    formal = clamp(100 - abs(profile.formality - outfit.formality) * 20)
    if outfit.palette == "dark": palette = clamp(55 + profile.darkness * 9)
    elif outfit.palette == "light": palette = clamp(55 + profile.cleanliness * 8 + profile.freshness * 3)
    elif outfit.palette == "monochrome": palette = clamp(60 + profile.formality * 6)
    else: palette = 68.0
    material = 65.0
    if "leather" in outfit.materials:
        material = 90.0 if "leather" in profile.main_accords or profile.darkness >= 3.6 else 58.0
    elif "wool" in outfit.materials or "knit" in outfit.materials:
        material = clamp(58 + profile.warmth * 8)
    elif "linen" in outfit.materials:
        material = clamp(58 + profile.freshness * 8 - profile.density * 3)
    garment_hits = len(set(outfit.garments) & legacy_outfits)
    garment = clamp(58 + garment_hits * 15)
    total = style * 0.35 + formal * 0.30 + palette * 0.15 + material * 0.10 + garment * 0.10
    evidence = []
    if style >= 78: evidence.append("стилистически совпадает с образом")
    if formal >= 80: evidence.append("формальность аромата соответствует одежде")
    if material >= 82 and "leather" in outfit.materials: evidence.append("кожаный материал поддержан характером аромата")
    elif palette >= 82: evidence.append(f"хорошо сочетается с {outfit.palette} палитрой")
    return clamp(total), evidence


def time_score(profile: PerfumeProfile, situation: Situation) -> tuple[float, list[str]]:
    value = getattr(profile, f"{situation.time_of_day}_score", 2.5) * 20.0
    label = {"morning":"утром","day":"днём","evening":"вечером","night":"ночью"}.get(situation.time_of_day, situation.time_of_day)
    return clamp(value), [f"лучше раскрывается {label}"] if value >= 80 else []


def season_score(profile: PerfumeProfile, situation: Situation) -> tuple[float, list[str]]:
    value = profile.season_scores.get(situation.season, 2.5) * 20.0
    label = {"spring":"весна","summer":"лето","autumn":"осень","winter":"зима"}.get(situation.season, situation.season)
    return clamp(value), [f"сезон «{label}» подходит профилю"] if value >= 80 else []


def hard_constraints(profile: PerfumeProfile, situation: Situation) -> tuple[float, list[str]]:
    penalty = 0.0
    warnings: list[str] = []
    temp = situation.feels_like if situation.feels_like is not None else situation.temperature
    if temp < profile.hard_temperature_min or temp > profile.hard_temperature_max:
        penalty += HARD_PENALTIES["hard_temperature"]
        warnings.append("температура за жёстким комфортным пределом")
    if situation.temperature >= 31 and (situation.humidity or 0) >= 72 and profile.density >= 3.8 and profile.sweetness >= 3.2:
        penalty += HARD_PENALTIES["humid_extreme_heat_dense"]
        warnings.append("плотный сладкий профиль в сильной влажной жаре")
    elif situation.temperature >= 32 and profile.density >= 4.0:
        penalty += HARD_PENALTIES["extreme_heat_dense"]
        warnings.append("слишком плотный профиль для экстремальной жары")
    if situation.circumstance == "small_room" and profile.projection >= 4.1:
        penalty += HARD_PENALTIES["small_room_projection"]
        warnings.append("сильная проекция в маленьком помещении")
    if situation.circumstance == "close_distance" and profile.projection >= 4.4:
        penalty += HARD_PENALTIES["close_distance_projection"]
        warnings.append("слишком громкий для близкой дистанции")
    if situation.event == "active" and profile.density >= 4.0 and profile.sweetness >= 3.4:
        penalty += HARD_PENALTIES["active_gourmand"]
        warnings.append("тяжёлый сладкий профиль плохо сочетается с активностью")
    return penalty, warnings


def _profile_completeness(profile: PerfumeProfile) -> float:
    values = [profile.main_accords, profile.effects_profile, profile.layer_families, profile.ideal_temperature, profile.projection, profile.longevity]
    base = sum(bool(v) for v in values) / len(values)
    notes = bool(profile.top_notes or profile.heart_notes or profile.base_notes)
    return min(1.0, base * 0.85 + (0.15 if notes else 0.0))


def _situation_completeness(situation: Situation) -> float:
    checks = [situation.event, situation.circumstance, situation.outfit.raw_text, situation.time_of_day, situation.season, situation.temperature is not None, situation.humidity is not None]
    return sum(bool(x) for x in checks) / len(checks)


def confidence_for(result: RecommendationResult, profile: PerfumeProfile, situation: Situation, margin: float = 0.0, history_count: int = 0) -> float:
    subs = [result.breakdown.event_score, result.breakdown.climate_score, result.breakdown.effect_score, result.breakdown.environment_score, result.breakdown.outfit_score, result.breakdown.time_score, result.breakdown.season_score]
    agreement = clamp(100 - statistics.pstdev(subs) * 1.4) / 100
    conf = 28 + _profile_completeness(profile) * 22 + _situation_completeness(situation) * 18 + agreement * 17 + min(1, history_count / 8) * 5 + min(10, max(0, margin))
    return clamp(conf)


def confidence_label(value: float) -> str:
    if value >= CONFIDENCE_THRESHOLDS["high"]: return "Высокая"
    if value >= CONFIDENCE_THRESHOLDS["medium"]: return "Средняя"
    return "Низкая"


def score_perfume(profile_or_dict, situation: Situation, personal_snapshot: dict | None = None) -> RecommendationResult:
    profile = profile_or_dict if isinstance(profile_or_dict, PerfumeProfile) else build_perfume_profile(profile_or_dict)
    e, e_ev = event_score(profile, situation)
    c, c_ev = climate_score(profile, situation)
    ef, ef_ev = effect_score(profile, situation)
    env, env_ev = environment_score(profile, situation)
    out, out_ev = outfit_score(profile, situation)
    t, t_ev = time_score(profile, situation)
    s, s_ev = season_score(profile, situation)
    personal, recent_penalty, p_ev = personal_adjustment(profile.name, situation, personal_snapshot)
    hard_penalty, warnings = hard_constraints(profile, situation)
    weighted = (
        e * SCORE_WEIGHTS["event"] + c * SCORE_WEIGHTS["climate"] + ef * SCORE_WEIGHTS["effect"] + env * SCORE_WEIGHTS["environment"] +
        out * SCORE_WEIGHTS["outfit"] + t * SCORE_WEIGHTS["time"] + s * SCORE_WEIGHTS["season"] + personal * SCORE_WEIGHTS["personal"]
    )
    final = clamp(weighted - hard_penalty - recent_penalty)
    evidence = {"event": e_ev, "climate": c_ev, "effect": ef_ev, "environment": env_ev, "outfit": out_ev, "time": t_ev, "season": s_ev, "personal": p_ev}
    advice = recommend_sprays(profile, situation)
    breakdown = ScoreBreakdown(
        event_score=e, climate_score=c, effect_score=ef, environment_score=env, outfit_score=out, time_score=t, season_score=s,
        personal_score=personal, weighted_score=weighted, hard_penalty=hard_penalty, recent_wear_penalty=recent_penalty,
        evidence=evidence, penalties=warnings,
    )
    result = RecommendationResult(
        perfume_id=profile.id, name=profile.name, brand=profile.brand, score=round(final, 1), confidence=0,
        confidence_label="Низкая", breakdown=breakdown, hard_warnings=warnings, spray_count=advice.count,
        spray_locations=advice.locations, spray_explanation=advice.explanation, deterministic_score=round(final, 1),
    )
    return result


def finalize_confidence(results: list[RecommendationResult], profiles: dict[str, PerfumeProfile], situation: Situation, history_count: int = 0) -> None:
    for idx, result in enumerate(results):
        next_score = results[idx + 1].score if idx + 1 < len(results) else max(0, result.score - 5)
        margin = max(0, result.score - next_score)
        conf = confidence_for(result, profiles[result.name], situation, margin, history_count)
        result.confidence = round(conf, 1)
        result.confidence_label = confidence_label(conf)
