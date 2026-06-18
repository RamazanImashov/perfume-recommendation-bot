from __future__ import annotations

from itertools import combinations

from app.data.perfumes import PERFUMES
from app.services.recommender import find_perfume, score_perfume


HEAVY_TAGS = {"tobacco", "coffee", "leather", "dense", "oud", "gourmand", "vanilla", "amber", "warm", "sweet"}
FRESH_TAGS = {"fresh", "citrus", "aquatic", "clean", "tea", "light", "blue", "fruity"}
ROMANTIC_TAGS = {"cherry", "almond", "romantic", "soft", "sweet", "warm"}
WOODY_TAGS = {"woody", "oud", "smoky", "amber", "patchouli", "vetiver"}

PRESET_LAYERING_PAIRS = [
    {
        "first": "Oud Wood",
        "second": "Imagination",
        "label": "дорого + чисто",
        "best_for": "ресторан, встреча, дождь, smart casual",
    },
    {
        "first": "Oud Wood",
        "second": "Lost Cherry",
        "label": "дорого + романтично",
        "best_for": "свидание, бар, близкая дистанция",
    },
    {
        "first": "The Most Wanted Parfum",
        "second": "Hawas Ice",
        "label": "вечер + свежий верх",
        "best_for": "теплый вечер, день рождения, прогулка",
    },
    {
        "first": "Ombré Leather (2018)",
        "second": "Pacific Chill",
        "label": "кожа + легкая свежесть",
        "best_for": "прохладный вечер, темный образ, но без перегруза",
    },
    {
        "first": "Tobacco Vanille",
        "second": "Oud Wood",
        "label": "зимняя дорогая база",
        "best_for": "холод, пальто, ресторан, праздник",
    },
    {
        "first": "Khamrah Qahwa",
        "second": "Imagination",
        "label": "кофе + чистый чай",
        "best_for": "кофейня, холодный день, спокойный образ",
    },
    {
        "first": "Lost Cherry",
        "second": "Aventus",
        "label": "вишня + уверенная свежесть",
        "best_for": "свидание днем/вечером, smart casual",
    },
    {
        "first": "9PM Night Out",
        "second": "9AM Dive",
        "label": "клубный сладкий + водная свежесть",
        "best_for": "вечеринка, теплый вечер, молодая подача",
    },
    {
        "first": "Turathi Blue",
        "second": "Imagination",
        "label": "цитрус + чайная чистота",
        "best_for": "день, учеба, кафе, светлый образ",
    },
    {
        "first": "Liquid Brun",
        "second": "Pacific Chill",
        "label": "сладкая база + летняя свежесть",
        "best_for": "прохладный летний вечер, но не жара и не маленькая комната",
    },
]


def _tags(perfume: dict) -> set[str]:
    result: set[str] = set()

    for key in ("type", "effects", "occasions", "outfits", "weather_tags"):
        value = perfume.get(key, [])
        if isinstance(value, list):
            result.update(str(x) for x in value)
        elif value:
            result.add(str(value))

    notes = perfume.get("notes", [])
    if isinstance(notes, dict):
        for value in notes.values():
            if isinstance(value, list):
                result.update(str(x) for x in value)
    elif isinstance(notes, list):
        result.update(str(x) for x in notes)

    return result


def _strength(perfume: dict) -> str:
    return str(perfume.get("strength", "medium"))


def _choose_base_and_top(a: dict, b: dict) -> tuple[dict, dict]:
    a_tags = _tags(a)
    b_tags = _tags(b)

    def weight(p: dict, tags: set[str]) -> int:
        score = 0
        score += 5 if _strength(p) == "strong" else 2 if _strength(p) == "medium" else 0
        score += len(tags.intersection(HEAVY_TAGS)) * 2
        score += len(tags.intersection(WOODY_TAGS))
        score -= len(tags.intersection(FRESH_TAGS))
        return score

    if weight(a, a_tags) >= weight(b, b_tags):
        return a, b
    return b, a


def analyze_pair(
    first: dict,
    second: dict,
    weather: dict | None = None,
    event: str = "ordinary_day",
    outfit_text: str = "",
    circumstance: str = "outdoor",
    effect: str = "any",
    time_of_day: str = "auto",
    season: str = "auto",
) -> dict:
    weather = weather or {"temperature": 20, "rain": 0, "precipitation": 0, "wind_speed": 0}

    base, top = _choose_base_and_top(first, second)
    base_tags = _tags(base)
    top_tags = _tags(top)
    all_tags = base_tags | top_tags

    base_score = score_perfume(base, weather, event, outfit_text, circumstance, effect, time_of_day, season)["score"]
    top_score = score_perfume(top, weather, event, outfit_text, circumstance, effect, time_of_day, season)["score"]

    score = int((base_score + top_score) / 2)
    reasons: list[str] = []
    warnings: list[str] = []

    if base_tags.intersection(WOODY_TAGS) and top_tags.intersection(FRESH_TAGS):
        score += 9
        reasons.append("древесная база + свежий верх дают дорогой чистый шлейф")

    if base_tags.intersection(ROMANTIC_TAGS) and top_tags.intersection(WOODY_TAGS | FRESH_TAGS):
        score += 6
        reasons.append("сладость становится мягче и чище")

    if base_tags.intersection(HEAVY_TAGS) and top_tags.intersection(FRESH_TAGS):
        score += 5
        reasons.append("свежий верх облегчает плотную базу")

    if event in {"club", "birthday", "party"} and ("sweet" in all_tags or "loud" in all_tags):
        score += 5
        reasons.append("достаточно заметно для вечера/клуба")

    if effect == "expensive" and ("expensive" in all_tags or "woody" in all_tags or "oud" in all_tags):
        score += 4
        reasons.append("пара звучит дороже за счет древесности/чистоты")

    if effect == "clean" and all_tags.intersection({"fresh", "clean", "tea", "citrus"}):
        score += 4
        reasons.append("сохраняет чистый эффект")

    if _strength(base) == "strong" and _strength(top) == "strong":
        score -= 6
        warnings.append("оба аромата сильные: легко переборщить")

    if len(base_tags.intersection(HEAVY_TAGS)) >= 3 and len(top_tags.intersection(HEAVY_TAGS)) >= 3:
        score -= 8
        warnings.append("слишком плотная пара")

    temp = float((weather or {}).get("temperature") or 20)
    if temp >= 28 and all_tags.intersection({"tobacco", "coffee", "leather", "dense", "gourmand"}):
        score -= 8
        warnings.append("в жару эта пара может душить")

    if circumstance in {"small_room", "close_distance"} and (_strength(base) == "strong" or _strength(top) == "strong"):
        score -= 5
        warnings.append("для близкой дистанции лучше меньше пшиков")

    if not reasons:
        reasons.append("пара сбалансирована по ситуации лучше остальных вариантов")

    return {
        "score": score,
        "base": base,
        "top": top,
        "reasons": reasons[:3],
        "warnings": warnings[:2],
        "apply": _apply_rule(base, top, circumstance, temp),
    }


def _apply_rule(base: dict, top: dict, circumstance: str, temp: float) -> str:
    if circumstance in {"small_room", "close_distance"}:
        return f"{base['name']}: 1 пшик на грудь. {top['name']}: 1 пшик на шею."
    if temp >= 28:
        return f"{base['name']}: 1 пшик. {top['name']}: 1–2 пшика."
    return f"{base['name']}: 1–2 пшика как база. {top['name']}: 1–2 пшика сверху."


def recommend_layering(
    weather: dict,
    event: str,
    outfit_text: str,
    circumstance: str,
    effect: str,
    time_of_day: str = "auto",
    season: str = "auto",
    limit: int = 3,
) -> list[dict]:
    results: list[dict] = []

    for first, second in combinations(PERFUMES, 2):
        result = analyze_pair(
            first=first,
            second=second,
            weather=weather,
            event=event,
            outfit_text=outfit_text,
            circumstance=circumstance,
            effect=effect,
            time_of_day=time_of_day,
            season=season,
        )
        results.append(result)

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:limit]


def analyze_pair_by_names(first_name: str, second_name: str) -> dict | None:
    first = find_perfume(first_name)
    second = find_perfume(second_name)

    if not first or not second:
        return None

    return analyze_pair(first, second)


def get_preset_layering_pairs() -> list[dict]:
    results = []
    for item in PRESET_LAYERING_PAIRS:
        first = find_perfume(item["first"])
        second = find_perfume(item["second"])
        if not first or not second:
            continue
        result = analyze_pair(first, second)
        result["label"] = item.get("label", "")
        result["best_for"] = item.get("best_for", "")
        results.append(result)
    return results
