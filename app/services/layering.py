from __future__ import annotations

from itertools import combinations

from app.data.perfumes import PERFUMES
from app.models.perfume import PerfumeProfile, build_perfume_profile
from app.models.recommendation import LayeringResult
from app.models.situation import Situation
from app.services.recommender import find_perfume, recommend_situation
from app.services.scoring import clamp, hard_constraints, score_perfume as score_profile
from app.services.scoring_config import CURATED_LAYERING_BONUS, LAYERING_WEIGHTS
from app.services.situation_parser import build_situation
from app.services.spray_advisor import recommend_layering_sprays

PRESET_LAYERING_PAIRS = [
    {"first": "Oud Wood", "second": "Imagination", "label": "дорого + чисто", "best_for": "ресторан, встреча, дождь, smart casual", "directional": True},
    {"first": "Oud Wood", "second": "Lost Cherry", "label": "дорого + романтично", "best_for": "свидание, бар, близкая дистанция", "directional": True},
    {"first": "The Most Wanted Parfum", "second": "Hawas for Him", "label": "вечер + свежий акватический верх", "best_for": "теплый вечер, день рождения, прогулка", "directional": True},
    {"first": "Ombré Leather (2018)", "second": "Pacific Chill", "label": "кожа + легкая свежесть", "best_for": "прохладный вечер, темный образ", "directional": True},
    {"first": "Tobacco Vanille", "second": "Oud Wood", "label": "зимняя дорогая база", "best_for": "холод, пальто, ресторан, праздник", "directional": True, "max_temperature": 22},
    {"first": "Khamrah Qahwa", "second": "Imagination", "label": "кофе + чистый чай", "best_for": "кофейня, холодный день, спокойный образ", "directional": True, "max_temperature": 20},
    {"first": "Lost Cherry", "second": "Aventus", "label": "вишня + уверенная свежесть", "best_for": "свидание днем/вечером, smart casual", "directional": False},
    {"first": "9PM Night Out", "second": "9AM Dive", "label": "сладкий + водная свежесть", "best_for": "вечеринка, теплый вечер", "directional": True},
    {"first": "Turathi Blue", "second": "Imagination", "label": "цитрус + чайная чистота", "best_for": "день, учеба, кафе, светлый образ", "directional": False},
    {"first": "Liquid Brun", "second": "Pacific Chill", "label": "сладкая база + свежий верх", "best_for": "прохладный вечер", "directional": True, "max_temperature": 24},
    {"first": "Fucking Fabulous", "second": "Molecule 02", "label": "пряная кожа + минеральная прозрачность", "best_for": "прохладный вечер, ресторан, близкая дистанция", "directional": True, "max_temperature": 22},
    {"first": "Fucking Fabulous", "second": "Lost Cherry", "label": "кожа и миндаль + вишня", "best_for": "свидание, бар, холодный вечер", "directional": True, "max_temperature": 20},
    {"first": "Fucking Fabulous", "second": "Pacific Chill", "label": "кожа + цитрусовая свежесть", "best_for": "прохладный день, smart casual, встреча", "directional": True, "max_temperature": 23},
    {"first": "Oud Wood", "second": "Molecule 02", "label": "сухая древесина + минеральный шлейф", "best_for": "встреча, ресторан, минималистичный образ", "directional": True, "max_temperature": 25},
    {"first": "Ombré Leather (2018)", "second": "Molecule 02", "label": "темная кожа + чистый амбровый верх", "best_for": "прогулка, бар, прохладный вечер", "directional": True, "max_temperature": 22},
    {"first": "Tobacco Vanille", "second": "Molecule 02", "label": "табачная ваниль + сухая прозрачность", "best_for": "холод, ресторан, праздничный вечер", "directional": True, "max_temperature": 18},
    {"first": "Lost Cherry", "second": "Molecule 02", "label": "вишня + чистая минеральная база", "best_for": "свидание, кафе, близкая дистанция", "directional": True, "max_temperature": 24},
]

FAMILY_COMPATIBILITY: dict[tuple[str, str], float] = {
    ("fresh", "woody"): 88, ("fresh", "amber"): 80, ("fresh", "gourmand"): 68, ("fresh", "leather"): 72,
    ("aquatic", "woody"): 82, ("aquatic", "amber"): 75, ("woody", "gourmand"): 84, ("woody", "fruity"): 82,
    ("woody", "leather"): 84, ("amber", "gourmand"): 82, ("amber", "fruity"): 80, ("fruity", "gourmand"): 79,
    ("spicy", "woody"): 84, ("spicy", "gourmand"): 85, ("tobacco", "woody"): 90, ("floral", "woody"): 78,
    ("musk", "woody"): 86, ("musk", "amber"): 88, ("musk", "leather"): 82, ("musk", "fruity"): 84,
    ("musk", "gourmand"): 80, ("musk", "fresh"): 88, ("musk", "floral"): 86, ("musk", "spicy"): 82,
    ("mineral", "woody"): 88, ("mineral", "amber"): 90, ("mineral", "leather"): 84, ("mineral", "fruity"): 82,
    ("mineral", "gourmand"): 78, ("mineral", "fresh"): 90, ("mineral", "aquatic"): 88, ("mineral", "tobacco"): 82,
    ("aromatic", "woody"): 86, ("aromatic", "leather"): 84, ("aromatic", "amber"): 82,
    ("aromatic", "fresh"): 88, ("aromatic", "spicy"): 84, ("aromatic", "floral"): 80,
}


def _pair_key(a: str, b: str) -> tuple[str, str]:
    return tuple(sorted((a, b)))


def _compatibility_by_families(a: PerfumeProfile, b: PerfumeProfile) -> float:
    if not a.layer_families or not b.layer_families:
        return 62.0
    scores = []
    for fa in a.layer_families:
        for fb in b.layer_families:
            if fa == fb:
                scores.append(72.0)
            else:
                scores.append(FAMILY_COMPATIBILITY.get((fa, fb), FAMILY_COMPATIBILITY.get((fb, fa), 64.0)))
    if not scores:
        return 62.0
    # A single matching family must not hide several weak family clashes.
    # Keep the strongest bridge, but require the rest of the structures to agree too.
    return 0.65 * max(scores) + 0.35 * (sum(scores) / len(scores))


def _note_set(profile: PerfumeProfile, section: str) -> set[str]:
    return set(getattr(profile, section))


def _note_compatibility(base: PerfumeProfile, top: PerfumeProfile) -> tuple[float, float]:
    all_a = set(base.top_notes + base.heart_notes + base.base_notes)
    all_b = set(top.top_notes + top.heart_notes + top.base_notes)
    if not all_a or not all_b:
        return 60.0, 55.0
    overlap = len(all_a & all_b)
    note_score = clamp(58 + overlap * 10)
    bridges = len(_note_set(base, "heart_notes") & (_note_set(top, "top_notes") | _note_set(top, "heart_notes")))
    bridges += len(_note_set(base, "base_notes") & _note_set(top, "heart_notes"))
    return note_score, clamp(52 + bridges * 14)


def _choose_base_top(a: PerfumeProfile, b: PerfumeProfile) -> tuple[PerfumeProfile, PerfumeProfile]:
    if a.layer_role == "base" and b.layer_role != "base": return a, b
    if b.layer_role == "base" and a.layer_role != "base": return b, a
    if a.layer_role == "top" and b.layer_role != "top": return b, a
    if b.layer_role == "top" and a.layer_role != "top": return a, b
    weight_a = a.density * 1.5 + a.warmth + a.projection * 0.5 - a.freshness * 0.5
    weight_b = b.density * 1.5 + b.warmth + b.projection * 0.5 - b.freshness * 0.5
    return (a, b) if weight_a >= weight_b else (b, a)


def _balance_score(a: float, b: float, ideal_diff: float = 1.2) -> float:
    diff = abs(a - b)
    return clamp(100 - abs(diff - ideal_diff) * 22)


def _curated_any(a: PerfumeProfile, b: PerfumeProfile) -> dict | None:
    for item in PRESET_LAYERING_PAIRS:
        if {item["first"], item["second"]} == {a.name, b.name}:
            return item
    return None


def _curated(base: PerfumeProfile, top: PerfumeProfile) -> dict | None:
    for item in PRESET_LAYERING_PAIRS:
        if item.get("directional"):
            if item["first"] == base.name and item["second"] == top.name:
                return item
        elif {item["first"], item["second"]} == {base.name, top.name}:
            return item
    return None


def analyze_pair_situation(first: dict | PerfumeProfile, second: dict | PerfumeProfile, situation: Situation, personal_snapshot: dict | None = None) -> LayeringResult:
    a = first if isinstance(first, PerfumeProfile) else build_perfume_profile(first)
    b = second if isinstance(second, PerfumeProfile) else build_perfume_profile(second)
    curated_hint = _curated_any(a, b)
    if curated_hint and curated_hint.get("directional"):
        base = a if a.name == curated_hint["first"] else b
        top = b if b.name == curated_hint["second"] else a
    else:
        base, top = _choose_base_top(a, b)
    indiv_a = score_profile(base, situation, personal_snapshot)
    indiv_b = score_profile(top, situation, personal_snapshot)
    accords = _compatibility_by_families(base, top)
    notes, bridging = _note_compatibility(base, top)
    contrast = clamp(78 - abs((base.darkness + base.warmth) - (top.freshness + top.cleanliness)) * 4 + abs(base.freshness - top.freshness) * 3)
    freshness_balance = _balance_score(base.freshness, top.freshness, 1.6)
    sweetness_balance = _balance_score(base.sweetness, top.sweetness, 1.2)
    density_balance = _balance_score(base.density, top.density, 1.5)
    warmth_balance = _balance_score(base.warmth, top.warmth, 1.2)
    projection_balance = clamp(100 - abs(base.projection - top.projection) * 14 - max(0, base.projection + top.projection - 8) * 9)
    scenario = (indiv_a.breakdown.event_score + indiv_b.breakdown.event_score + indiv_a.breakdown.effect_score + indiv_b.breakdown.effect_score) / 4
    climate = (indiv_a.breakdown.climate_score + indiv_b.breakdown.climate_score) / 2
    close = (base.close_distance_score + top.close_distance_score) * 10
    subs = {
        "accords": accords, "notes": notes, "bridging": bridging, "contrast": contrast,
        "freshness_balance": freshness_balance, "sweetness_balance": sweetness_balance,
        "density_balance": density_balance, "warmth_balance": warmth_balance, "projection_balance": projection_balance,
        "scenario": scenario, "climate": climate, "close_distance": close,
    }
    raw = sum(subs[k] * LAYERING_WEIGHTS[k] for k in LAYERING_WEIGHTS)
    warnings: list[str] = []
    hard_penalty = 0.0
    combined_load = base.density + top.density + 0.45 * (base.warmth + top.warmth) + 0.35 * (base.sweetness + top.sweetness)
    if situation.temperature >= 30 and (situation.humidity or 0) >= 70 and combined_load >= 9.5:
        hard_penalty += 32
        warnings.append("слишком плотная пара для влажной жары")
    elif situation.temperature >= 30 and combined_load >= 11.5:
        hard_penalty += 26
        warnings.append("слишком плотная пара для жары")
    if situation.circumstance in {"small_room", "close_distance"} and (base.projection + top.projection) >= 8.0:
        hard_penalty += 22
        warnings.append("слишком высокая общая проекция для близкой дистанции")
    curated = _curated(base, top)
    curated_bonus = 0.0
    if curated:
        max_temp = curated.get("max_temperature")
        if max_temp is None or situation.temperature <= float(max_temp):
            curated_bonus = CURATED_LAYERING_BONUS
    score = clamp(raw + curated_bonus - hard_penalty)
    reasons = []
    if accords >= 80: reasons.append("аккорды хорошо связываются")
    if bridging >= 70: reasons.append("есть связующие ноты между слоями")
    if freshness_balance >= 75 and density_balance >= 70: reasons.append("свежесть и плотность сбалансированы")
    if curated: reasons.append("сочетание включено в отобранные схемы")
    if not reasons: reasons.append("пара приемлемо сбалансирована по сценарию")
    completeness = 0.65 + (0.15 if base.top_notes or base.heart_notes or base.base_notes else 0) + (0.15 if top.top_notes or top.heart_notes or top.base_notes else 0) + (0.05 if curated else 0)
    confidence = clamp(48 + completeness * 35 + max(0, score - 70) * 0.35 - len(warnings) * 7)
    label = "Высокая" if confidence >= 76 else "Средняя" if confidence >= 55 else "Низкая"
    return LayeringResult(
        base_name=base.name, top_name=top.name, score=round(score, 1), confidence=round(confidence, 1), confidence_label=label,
        application_order=[base.name, top.name], spray_plan=recommend_layering_sprays(base, top, situation), subscores={k: round(v, 1) for k, v in subs.items()},
        reasons=reasons[:3], warnings=warnings[:2], curated=bool(curated), curated_label=(curated or {}).get("label", ""), curated_best_for=(curated or {}).get("best_for", ""),
    )


def recommend_layering_situation(situation: Situation, limit: int = 3, personal_snapshot: dict | None = None) -> list[LayeringResult]:
    profiles = [build_perfume_profile(p) for p in PERFUMES]
    results = [analyze_pair_situation(a, b, situation, personal_snapshot) for a, b in combinations(profiles, 2)]
    results.sort(key=lambda x: (-x.score, x.base_name, x.top_name))
    return results[:limit]


def analyze_pair(first: dict, second: dict, weather: dict | None = None, event: str = "casual", outfit_text: str = "", circumstance: str = "outdoor", effect: str = "any", time_of_day: str = "auto", season: str = "auto") -> dict:
    weather = weather or {"temperature": 20, "humidity": 50, "rain": 0, "precipitation": 0, "cloud_cover": 30, "wind_speed": 5, "is_day": True}
    situation = build_situation(event=event, outfit_text=outfit_text, circumstance=circumstance, effect=effect, weather=weather, manual_time=time_of_day, manual_season=season)
    result = analyze_pair_situation(first, second, situation)
    base = find_perfume(result.base_name) or first
    top = find_perfume(result.top_name) or second
    return {"score": result.score, "confidence": result.confidence, "confidence_label": result.confidence_label, "base": base, "top": top, "reasons": result.reasons, "warnings": result.warnings, "apply": result.spray_plan, "subscores": result.subscores, "result": result}


def recommend_layering(weather: dict, event: str, outfit_text: str, circumstance: str, effect: str, time_of_day: str = "auto", season: str = "auto", limit: int = 3, personal_snapshot: dict | None = None, **kwargs) -> list[dict]:
    situation = build_situation(event=event, outfit_text=outfit_text, circumstance=circumstance, effect=effect, weather=weather, place=kwargs.get("place", ""), target_datetime=kwargs.get("target_datetime"), latitude=kwargs.get("latitude"), longitude=kwargs.get("longitude"), timezone=kwargs.get("timezone"), manual_time=time_of_day, manual_season=season, outdoor_exposure=kwargs.get("outdoor_exposure"))
    results = recommend_layering_situation(situation, limit=limit, personal_snapshot=personal_snapshot)
    out = []
    for result in results:
        out.append({"score": result.score, "confidence": result.confidence, "confidence_label": result.confidence_label, "base": find_perfume(result.base_name), "top": find_perfume(result.top_name), "reasons": result.reasons, "warnings": result.warnings, "apply": result.spray_plan, "subscores": result.subscores, "curated": result.curated, "result": result, "situation": situation.model_dump(mode="json")})
    return out


def analyze_pair_by_names(first_name: str, second_name: str) -> dict | None:
    first, second = find_perfume(first_name), find_perfume(second_name)
    return analyze_pair(first, second) if first and second else None


def get_preset_layering_pairs() -> list[dict]:
    results = []
    neutral = {"temperature": 16, "humidity": 50, "rain": 0, "precipitation": 0, "cloud_cover": 50, "wind_speed": 5, "is_day": False}
    for item in PRESET_LAYERING_PAIRS:
        first, second = find_perfume(item["first"]), find_perfume(item["second"])
        if not first or not second: continue
        result = analyze_pair(first, second, weather=neutral, event="restaurant", circumstance="indoor", effect="expensive", time_of_day="evening")
        result["label"] = item.get("label", "")
        result["best_for"] = item.get("best_for", "")
        results.append(result)
    return results
