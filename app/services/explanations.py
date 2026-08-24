from __future__ import annotations

from app.models.recommendation import RecommendationResult
from app.models.situation import Situation


def explanation_lines(result: RecommendationResult, situation: Situation, max_items: int = 3) -> list[str]:
    buckets = result.breakdown.evidence
    ordered = ["event", "climate", "outfit", "environment", "effect", "time", "season", "personal"]
    lines: list[str] = []
    for key in ordered:
        for item in buckets.get(key, []):
            if item and item not in lines:
                lines.append(item)
            if len(lines) >= max_items:
                return lines
    return lines


def risk_line(result: RecommendationResult) -> str:
    if result.hard_warnings:
        return result.hard_warnings[0]
    if result.breakdown.recent_wear_penalty > 0:
        return "недавно уже носился — выбран режим разнообразия"
    if result.breakdown.climate_score < 55:
        return "погода не идеальна, лучше уменьшить нагрузку"
    if result.breakdown.environment_score < 55:
        return "окружение требует аккуратной дозировки"
    return "существенных рисков нет"


def comparison_reason(a: RecommendationResult, b: RecommendationResult) -> list[str]:
    labels = {
        "event_score": "событие",
        "climate_score": "погода",
        "effect_score": "эффект",
        "environment_score": "окружение",
        "outfit_score": "образ",
        "time_score": "время",
        "season_score": "сезон",
        "personal_score": "личный опыт",
    }
    diffs = []
    for field, label in labels.items():
        av = getattr(a.breakdown, field)
        bv = getattr(b.breakdown, field)
        diffs.append((abs(av - bv), label, av - bv))
    diffs.sort(reverse=True)
    out = []
    for _, label, delta in diffs[:3]:
        if abs(delta) < 4:
            continue
        winner = a.name if delta > 0 else b.name
        out.append(f"{winner} сильнее по фактору «{label}» на {abs(delta):.0f} баллов")
    if not out:
        out.append("разница небольшая: решающими стали суммарные веса факторов")
    return out
