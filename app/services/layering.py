from __future__ import annotations

import re
from collections.abc import Iterable
from app.data.perfumes import PERFUMES


HEAVY_TAGS = {"tobacco", "coffee", "leather", "dense", "gourmand", "vanilla", "praline", "cinnamon", "sweet", "amber"}
FRESH_TAGS = {"fresh", "citrus", "aquatic", "tea", "clean", "mint", "aromatic", "blue", "green"}
DARK_TAGS = {"dark", "leather", "oud", "tobacco", "coffee", "woody", "amber"}
ROMANTIC_TAGS = {"romantic", "sexy", "sweet", "warm", "cherry", "vanilla"}


def _as_set(value) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {value}
    if isinstance(value, dict):
        result = set()
        for item in value.values():
            result.update(_as_set(item))
        return result
    if isinstance(value, Iterable):
        result = set()
        for item in value:
            result.update(_as_set(item))
        return result
    return {str(value)}


def _profile(perfume: dict) -> set[str]:
    keys = ["type", "effects", "weather_tags", "occasions", "outfits", "notes", "layer_tags"]
    result: set[str] = set()
    for key in keys:
        result.update(_as_set(perfume.get(key)))
    return result


def _normalize(text: str) -> str:
    return re.sub(r"[^a-zа-яё0-9]+", " ", text.lower()).strip()


def find_perfume(query: str) -> dict | None:
    q = _normalize(query)
    if not q:
        return None

    best = None
    best_score = 0

    for perfume in PERFUMES:
        name = _normalize(perfume.get("name", ""))
        brand = _normalize(perfume.get("brand", ""))
        full = f"{name} {brand}"

        score = 0
        if q == name or q == full:
            score = 100
        elif q in full:
            score = 80
        else:
            q_words = set(q.split())
            full_words = set(full.split())
            score = len(q_words & full_words) * 20

        if score > best_score:
            best_score = score
            best = perfume

    return best if best_score >= 20 else None


def analyze_layering(first_query: str, second_query: str) -> dict:
    first = find_perfume(first_query)
    second = find_perfume(second_query)

    if not first or not second:
        return {
            "ok": False,
            "message": "Не нашел один из ароматов. Напиши названия ближе к базе, например: Oud Wood + Lost Cherry.",
        }

    if first.get("id") == second.get("id"):
        return {"ok": False, "message": "Это один и тот же аромат. Для наслаивания выбери два разных."}

    p1 = _profile(first)
    p2 = _profile(second)

    score = 50
    reasons: list[str] = []
    warnings: list[str] = []

    if p1 & FRESH_TAGS and p2 & HEAVY_TAGS:
        score += 15
        reasons.append("свежий аромат может облегчить тяжелый/сладкий")
    if p2 & FRESH_TAGS and p1 & HEAVY_TAGS:
        score += 15
        reasons.append("свежий аромат может облегчить тяжелый/сладкий")
    if p1 & ROMANTIC_TAGS and p2 & DARK_TAGS:
        score += 10
        reasons.append("романтичная сладость хорошо ложится на темную древесную/амбровую базу")
    if p2 & ROMANTIC_TAGS and p1 & DARK_TAGS:
        score += 10
        reasons.append("романтичная сладость хорошо ложится на темную древесную/амбровую базу")
    if p1 & FRESH_TAGS and p2 & FRESH_TAGS:
        score += 5
        reasons.append("оба свежие — безопасное дневное сочетание")
    if p1 & HEAVY_TAGS and p2 & HEAVY_TAGS:
        score -= 20
        warnings.append("оба аромата плотные — легко получить тяжелую смесь")
    if first.get("strength") == "strong" and second.get("strength") == "strong":
        score -= 15
        warnings.append("оба сильные — используй очень мало")

    # Specific strong recommendations from this collection.
    pair_ids = {first.get("id"), second.get("id")}
    special: dict[frozenset[int], tuple[int, str, str]] = {
        frozenset({9, 21}): (92, "Oud Wood + Lost Cherry", "дорогое романтичное сочетание для свидания и бара"),
        frozenset({12, 23}): (86, "Imagination + The Most Wanted", "чистое начало + теплый вечерний шлейф"),
        frozenset({11, 12}): (88, "Pacific Chill + Imagination", "максимально чистая свежесть для жары"),
        frozenset({4, 9}): (84, "Aventus + Oud Wood", "уверенный smart casual, чище и дороже"),
        frozenset({23, 29}): (62, "The Most Wanted + Liquid Brun", "очень сладко и плотно; только холод и 1+1 пшик"),
        frozenset({2, 29}): (55, "Tobacco Vanille + Liquid Brun", "слишком плотная ванильная сладость; лучше не для помещения"),
        frozenset({26, 28}): (82, "Turathi Blue + Maahir Legacy", "свежий цитрус + зеленая мята, хороший дневной микс"),
        frozenset({27, 28}): (85, "Art Of Universe + Maahir Legacy", "летняя яркая свежесть, мята и цитрус"),
    }
    if frozenset(pair_ids) in special:
        score, title, extra = special[frozenset(pair_ids)]
        reasons.insert(0, extra)

    score = max(0, min(100, score))

    if score >= 80:
        verdict = "Хорошее сочетание"
    elif score >= 65:
        verdict = "Можно носить, но аккуратно"
    elif score >= 50:
        verdict = "Слабое сочетание"
    else:
        verdict = "Лучше не смешивать"

    # Safer application rule: strong/heavy first under clothes, fresh/soft later on open skin/clothes.
    first_profile = _profile(first)
    second_profile = _profile(second)
    if first_profile & HEAVY_TAGS and second_profile & FRESH_TAGS:
        order = f"Сначала {first['name']} — 1 пшик на грудь под одежду. Потом {second['name']} — 1–2 пшика на шею/одежду."
    elif second_profile & HEAVY_TAGS and first_profile & FRESH_TAGS:
        order = f"Сначала {second['name']} — 1 пшик на грудь под одежду. Потом {first['name']} — 1–2 пшика на шею/одежду."
    else:
        order = f"Начни с 1 пшика {first['name']} на грудь и 1 пшика {second['name']} на шею. Не делай больше 2–3 пшиков суммарно."

    if not reasons:
        reasons.append("нет явного конфликта по профилю, но сочетание лучше тестировать малыми дозами")

    return {
        "ok": True,
        "score": score,
        "verdict": verdict,
        "first": first,
        "second": second,
        "order": order,
        "reasons": reasons[:4],
        "warnings": warnings[:4],
    }
