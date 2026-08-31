from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PerfumeProfile(BaseModel):
    id: int | None = None
    brand: str
    name: str
    gender: str = "unisex"
    main_accords: list[str] = Field(default_factory=list)
    top_notes: list[str] = Field(default_factory=list)
    heart_notes: list[str] = Field(default_factory=list)
    base_notes: list[str] = Field(default_factory=list)
    freshness: float = 2.5
    sweetness: float = 2.5
    warmth: float = 2.5
    density: float = 2.5
    darkness: float = 2.5
    cleanliness: float = 2.5
    formality: float = 2.5
    romantic: float = 2.5
    uniqueness: float = 2.5
    projection: float = 3.0
    longevity: float = 3.0
    ideal_temperature: float = 20.0
    comfortable_temperature_min: float = 10.0
    comfortable_temperature_max: float = 28.0
    hard_temperature_min: float = 2.0
    hard_temperature_max: float = 35.0
    humidity_preference: float = 2.5
    indoor_score: float = 3.0
    outdoor_score: float = 3.0
    close_distance_score: float = 3.0
    morning_score: float = 2.5
    day_score: float = 2.5
    evening_score: float = 2.5
    night_score: float = 2.5
    study_score: float = 2.5
    work_score: float = 2.5
    meeting_score: float = 2.5
    walk_score: float = 2.5
    cafe_score: float = 2.5
    date_score: float = 2.5
    restaurant_score: float = 2.5
    party_score: float = 2.5
    club_score: float = 2.5
    birthday_score: float = 2.5
    active_score: float = 2.5
    casual_score: float = 2.5
    effects_profile: dict[str, float] = Field(default_factory=dict)
    season_scores: dict[str, float] = Field(default_factory=dict)
    layer_role: str = "flexible"
    layer_families: list[str] = Field(default_factory=list)
    layer_conflicts: list[str] = Field(default_factory=list)
    sprays: str = "2–3"
    base_sprays_min: int = 2
    base_sprays_max: int = 3
    apply: str = ""
    legacy: dict[str, Any] = Field(default_factory=dict)


EVENT_SCORE_KEYS = {
    "study": "study_score", "work": "work_score", "meeting": "meeting_score", "walk": "walk_score",
    "cafe": "cafe_score", "date": "date_score", "restaurant": "restaurant_score", "party": "party_score",
    "club": "club_score", "birthday": "birthday_score", "active": "active_score", "casual": "casual_score",
}


def _clamp5(value: float) -> float:
    return round(max(0.0, min(5.0, value)), 2)


def _flatten(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, dict):
        out: list[str] = []
        for v in value.values():
            out.extend(_flatten(v))
        return out
    if isinstance(value, (list, tuple, set)):
        return [str(v).lower() for v in value]
    return [str(value).lower()]


LEGACY_EVENT_MAP = {
    "study": "study", "office": "work", "work": "work", "meeting": "meeting", "important_meeting": "meeting",
    "day_meeting": "meeting", "important_event": "meeting", "walk": "walk", "day_walk": "walk", "night_walk": "walk",
    "evening_walk": "walk", "cold_walk": "walk", "calm_walk": "walk", "cafe": "cafe", "coffee_shop": "cafe",
    "date": "date", "casual_date": "date", "winter_date": "date", "romantic_evening": "date",
    "restaurant": "restaurant", "restaurant_day": "restaurant", "restaurant_evening": "restaurant",
    "party": "party", "light_party": "party", "club": "club", "birthday": "birthday",
    "active_day": "active", "gym_after_shower": "active", "sport_casual": "active", "casual": "casual",
    "ordinary_day": "casual", "city": "casual", "friends": "casual", "friends_evening": "casual",
    "day": "casual", "evening": "casual", "night": "casual", "trip": "casual", "flight": "casual",
}


def _score_from_tags(tags: set[str], positives: set[str], base: float = 2.0) -> float:
    return _clamp5(base + 0.7 * len(tags & positives))


def _spray_range(text: str) -> tuple[int, int]:
    import re
    nums = [int(x) for x in re.findall(r"\d+", text or "")]
    if not nums:
        return 2, 3
    if len(nums) == 1:
        return nums[0], nums[0]
    return min(nums[0], nums[1]), max(nums[0], nums[1])


def build_perfume_profile(perfume: dict[str, Any]) -> PerfumeProfile:
    tags = set(_flatten(perfume.get("type"))) | set(_flatten(perfume.get("effects"))) | set(_flatten(perfume.get("layer_tags")))
    outfits = set(_flatten(perfume.get("outfits")))
    occasions = _flatten(perfume.get("occasions"))
    accord_tags = sorted(set(_flatten(perfume.get("type"))))

    fresh = _score_from_tags(tags, {"fresh", "citrus", "aquatic", "clean", "tea", "light", "blue", "fruity", "aromatic", "mineral", "ambroxan"}, 1.4)
    sweet = _score_from_tags(tags, {"sweet", "vanilla", "gourmand", "cherry", "coffee", "praline", "rum"}, 1.2)
    warm = _score_from_tags(tags, {"warm", "amber", "spicy", "tobacco", "coffee", "vanilla", "gourmand", "rum"}, 1.4)
    density = _score_from_tags(tags, {"dense", "tobacco", "leather", "oud", "gourmand", "vanilla", "amber", "sweet"}, 1.3)
    darkness = _score_from_tags(tags, {"dark", "leather", "oud", "tobacco", "smoky", "coffee", "amber"}, 1.3)
    clean = _score_from_tags(tags, {"clean", "fresh", "citrus", "aquatic", "tea", "blue", "mineral", "musk", "skin_scent", "ambroxan"}, 1.5)
    formal = _score_from_tags(tags | outfits, {"expensive", "luxury", "woody", "oud", "leather", "formal", "smart_casual", "minimalism", "status"}, 1.5)
    romantic = _score_from_tags(tags, {"romantic", "sexy", "cherry", "sweet", "warm", "soft", "rum"}, 1.2)
    unique = _score_from_tags(tags, {"unusual", "oud", "leather", "tobacco", "cherry", "coffee", "smoky"}, 1.6)

    strength = str(perfume.get("strength", "medium"))
    projection = {"soft": 2.0, "medium": 3.2, "strong": 4.4}.get(strength, 3.0)
    longevity = {"soft": 2.7, "medium": 3.5, "strong": 4.4}.get(strength, 3.4)

    cmin = float(perfume.get("weather_min", 10))
    cmax = float(perfume.get("weather_max", 28))
    ideal = round((cmin + cmax) / 2.0, 1)
    hard_min = cmin - (8 if density >= 3.5 else 6)
    hard_max = cmax + (6 if fresh >= 3.5 else 4)

    notes = perfume.get("notes") or {}
    top_notes: list[str] = []
    heart_notes: list[str] = []
    base_notes: list[str] = []
    if isinstance(notes, dict):
        top_notes = _flatten(notes.get("top"))
        heart_notes = _flatten(notes.get("heart") or notes.get("middle"))
        base_notes = _flatten(notes.get("base"))

    event_scores = {key: 2.2 for key in EVENT_SCORE_KEYS}
    for old in occasions:
        normalized = LEGACY_EVENT_MAP.get(old)
        if normalized:
            event_scores[normalized] = max(event_scores[normalized], 4.5)
    if clean >= 3.5:
        event_scores["study"] = max(event_scores["study"], 3.7)
        event_scores["work"] = max(event_scores["work"], 3.8)
    if formal >= 3.5:
        event_scores["meeting"] = max(event_scores["meeting"], 4.0)
        event_scores["restaurant"] = max(event_scores["restaurant"], 3.8)
    if projection >= 4.0 and sweet >= 3.0:
        event_scores["party"] = max(event_scores["party"], 4.0)
        event_scores["club"] = max(event_scores["club"], 4.0)
    if fresh >= 3.7:
        event_scores["walk"] = max(event_scores["walk"], 4.0)
        event_scores["active"] = max(event_scores["active"], 3.5)

    times = set(_flatten(perfume.get("time_of_day")) or _flatten(perfume.get("time_tags")))
    time_scores = {"morning": 2.2, "day": 2.5, "evening": 2.5, "night": 2.0}
    for t in times:
        if t in time_scores:
            time_scores[t] = 4.5
    seasons = set(_flatten(perfume.get("seasons")))
    season_scores = {s: (4.5 if s in seasons else 2.2) for s in ("spring", "summer", "autumn", "winter")}

    effects = set(_flatten(perfume.get("effects")))
    effects_profile = {
        "clean": max(clean, 4.5 if "clean" in effects else 0),
        "expensive": max(formal, 4.5 if "expensive" in effects or "status" in effects else 0),
        "sexy": max(romantic, 4.5 if "sexy" in effects or "romantic" in effects else 0),
        "noticeable": max(projection, 4.5 if "noticeable" in effects or "loud" in effects else 0),
        "calm": max(5.0 - projection * 0.65, 4.5 if "calm" in effects or "soft" in effects else 0),
        "unusual": max(unique, 4.5 if "unusual" in effects else 0),
    }

    families = set()
    family_map = {
        "fresh": {"fresh", "citrus", "clean", "tea", "blue", "aromatic"}, "aquatic": {"aquatic", "watery_notes"},
        "woody": {"woody", "oud", "vetiver", "patchouli", "driftwood", "smoky"}, "amber": {"amber", "ambergris", "ambroxan"},
        "gourmand": {"gourmand", "coffee", "vanilla", "praline", "sweet"}, "leather": {"leather"},
        "fruity": {"fruity", "cherry", "apple", "plum", "pear"}, "spicy": {"spicy", "cinnamon", "cardamom", "ginger"},
        "tobacco": {"tobacco"}, "floral": {"floral", "orange_blossom"},
        "musk": {"musk", "skin_scent"}, "mineral": {"mineral", "ambroxan"},
        "aromatic": {"aromatic", "lavender", "clary_sage"},
    }
    all_known = tags | set(top_notes) | set(heart_notes) | set(base_notes)
    for family, keys in family_map.items():
        if all_known & keys:
            families.add(family)

    if density >= 3.7 and warm >= 3.0:
        layer_role = "base"
    elif fresh >= 3.8 and density <= 3.0:
        layer_role = "top"
    else:
        layer_role = "flexible"

    smin, smax = _spray_range(str(perfume.get("sprays", "2–3")))
    indoor = _clamp5(4.3 - max(0.0, projection - 3.0) * 0.8 - max(0.0, density - 3.2) * 0.4)
    outdoor = _clamp5(2.5 + projection * 0.35 + fresh * 0.18)
    close = _clamp5(4.4 - max(0.0, projection - 2.5) * 0.9 - max(0.0, density - 3.0) * 0.4)
    humidity_pref = _clamp5(2.5 + (fresh - density) * 0.45)

    return PerfumeProfile(
        id=perfume.get("id"), brand=str(perfume.get("brand", "")), name=str(perfume.get("name", "")), gender=str(perfume.get("gender", "unisex")),
        main_accords=accord_tags, top_notes=top_notes, heart_notes=heart_notes, base_notes=base_notes,
        freshness=fresh, sweetness=sweet, warmth=warm, density=density, darkness=darkness, cleanliness=clean,
        formality=formal, romantic=romantic, uniqueness=unique, projection=projection, longevity=longevity,
        ideal_temperature=ideal, comfortable_temperature_min=cmin, comfortable_temperature_max=cmax,
        hard_temperature_min=hard_min, hard_temperature_max=hard_max, humidity_preference=humidity_pref,
        indoor_score=indoor, outdoor_score=outdoor, close_distance_score=close,
        morning_score=time_scores["morning"], day_score=time_scores["day"], evening_score=time_scores["evening"], night_score=time_scores["night"],
        effects_profile={k: _clamp5(v) for k, v in effects_profile.items()}, season_scores=season_scores,
        layer_role=layer_role, layer_families=sorted(families), layer_conflicts=[], sprays=str(perfume.get("sprays", "2–3")),
        base_sprays_min=smin, base_sprays_max=smax, apply=str(perfume.get("apply", "")), legacy=perfume,
        **{EVENT_SCORE_KEYS[k]: _clamp5(v) for k, v in event_scores.items()},
    )


def enrich_perfume_database(perfumes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for raw in perfumes:
        item = dict(raw)
        profile = build_perfume_profile(item).model_dump(exclude={"legacy"})
        for key, value in profile.items():
            item.setdefault(key, value)
        enriched.append(item)
    return enriched
