from __future__ import annotations

from app.data.perfumes import PERFUMES
from app.models.perfume import EVENT_SCORE_KEYS, build_perfume_profile

VALID_GENDERS = {"men", "women", "unisex"}
VALID_LAYER_ROLES = {"base", "top", "flexible"}
VALID_SEASONS = {"spring", "summer", "autumn", "winter"}


def validate_perfumes(perfumes: list[dict] | None = None, curated_pairs: list[dict] | None = None) -> list[str]:
    perfumes = perfumes or PERFUMES
    errors: list[str] = []
    seen: set[tuple[str, str]] = set()
    names = {p.get("name") for p in perfumes}
    for raw in perfumes:
        key = (str(raw.get("brand", "")).strip().lower(), str(raw.get("name", "")).strip().lower())
        if key in seen: errors.append(f"duplicate perfume: {key}")
        seen.add(key)
        try:
            p = build_perfume_profile(raw)
        except Exception as exc:
            errors.append(f"profile build failed for {raw.get('name')}: {exc}")
            continue
        if p.gender not in VALID_GENDERS: errors.append(f"invalid gender: {p.name}={p.gender}")
        if p.layer_role not in VALID_LAYER_ROLES: errors.append(f"invalid layer_role: {p.name}={p.layer_role}")
        numeric = [p.freshness, p.sweetness, p.warmth, p.density, p.darkness, p.cleanliness, p.formality, p.romantic, p.uniqueness, p.projection, p.longevity, p.indoor_score, p.outdoor_score, p.close_distance_score]
        numeric += [getattr(p, field) for field in EVENT_SCORE_KEYS.values()]
        if any(not 0 <= x <= 5 for x in numeric): errors.append(f"numeric profile out of 0..5: {p.name}")
        if not p.hard_temperature_min < p.ideal_temperature < p.hard_temperature_max: errors.append(f"invalid temperature profile: {p.name}")
        if not p.hard_temperature_min <= p.comfortable_temperature_min <= p.ideal_temperature <= p.comfortable_temperature_max <= p.hard_temperature_max:
            errors.append(f"invalid temperature ordering: {p.name}")
        if set(p.season_scores) - VALID_SEASONS: errors.append(f"invalid season key: {p.name}")
    if curated_pairs:
        for pair in curated_pairs:
            if pair.get("first") not in names: errors.append(f"curated pair missing first: {pair.get('first')}")
            if pair.get("second") not in names: errors.append(f"curated pair missing second: {pair.get('second')}")
    return errors
