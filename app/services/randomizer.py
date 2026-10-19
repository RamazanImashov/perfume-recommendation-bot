from __future__ import annotations

import random
from dataclasses import dataclass
from statistics import fmean
from typing import Any, Sequence

from app.models.perfume import EVENT_SCORE_KEYS, build_perfume_profile


@dataclass(frozen=True)
class RandomCandidate:
    perfume: dict[str, Any]
    versatility_score: float
    weight: float


def _clamp5(value: float) -> float:
    return max(0.0, min(5.0, float(value)))


def random_weight(perfume: dict[str, Any]) -> RandomCandidate:
    """Calculate a context-free weight while keeping every perfume selectable."""
    profile = build_perfume_profile(perfume)
    event_score = fmean(getattr(profile, field) for field in EVENT_SCORE_KEYS.values())
    time_score = fmean((profile.morning_score, profile.day_score, profile.evening_score, profile.night_score))
    season_score = fmean(profile.season_scores.get(season, 2.5) for season in ("spring", "summer", "autumn", "winter"))
    environment_score = fmean((profile.indoor_score, profile.outdoor_score, profile.close_distance_score))
    temperature_score = _clamp5((profile.comfortable_temperature_max - profile.comfortable_temperature_min) / 8.0)
    projection_balance = _clamp5(5.0 - abs(profile.projection - 3.2) * 0.9)
    performance_score = fmean((profile.longevity, projection_balance))

    universal = (
        event_score * 0.30
        + time_score * 0.15
        + season_score * 0.15
        + environment_score * 0.15
        + temperature_score * 0.15
        + performance_score * 0.10
    )
    versatility_score = round(_clamp5(universal) * 20.0, 1)
    weight = round(1.0 + 9.0 * (versatility_score / 100.0) ** 2, 4)
    return RandomCandidate(perfume=perfume, versatility_score=versatility_score, weight=weight)


def random_candidate(
    perfumes: Sequence[dict[str, Any]],
    *,
    exclude_id: int | None = None,
    rng: random.Random | None = None,
) -> RandomCandidate:
    if not perfumes:
        raise ValueError("Perfume catalogue is empty")
    candidates = [perfume for perfume in perfumes if perfume.get("id") != exclude_id]
    if not candidates:
        candidates = list(perfumes)
    weighted = [random_weight(perfume) for perfume in candidates]
    generator = rng or random.SystemRandom()
    return generator.choices(weighted, weights=[item.weight for item in weighted], k=1)[0]
