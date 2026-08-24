from __future__ import annotations

SCORE_WEIGHTS = {
    "event": 0.25,
    "climate": 0.20,
    "effect": 0.15,
    "environment": 0.15,
    "outfit": 0.10,
    "time": 0.05,
    "season": 0.05,
    "personal": 0.05,
}

OUTDOOR_EXPOSURE_CLIMATE_FACTOR = {"low": 0.45, "medium": 0.72, "high": 1.0}

HARD_PENALTIES = {
    "humid_extreme_heat_dense": 34.0,
    "extreme_heat_dense": 28.0,
    "small_room_projection": 24.0,
    "close_distance_projection": 18.0,
    "active_gourmand": 30.0,
    "hard_temperature": 28.0,
}

CURATED_LAYERING_BONUS = 7.0
DIVERSITY_MAX_DROP_SAFE = 12.0
DIVERSITY_MAX_DROP_EXPRESSIVE = 15.0
CONFIDENCE_THRESHOLDS = {"high": 76.0, "medium": 55.0}

TEMPERATURE_CURVE = {
    "comfort_edge_score": 74.0,
    "hard_edge_score": 24.0,
    "outside_score": 4.0,
}

RECENT_WEAR_PENALTIES = {
    "diversity": {0: 12.0, 1: 8.0, 2: 4.5, 3: 2.0},
    "favorites": {0: 4.0, 1: 2.0, 2: 1.0, 3: 0.5},
}

FEEDBACK_WEIGHTS = {
    "excellent": 1.4,
    "normal": 0.25,
    "dislike": -1.5,
    "too_strong": -1.1,
    "too_weak": -0.7,
    "compliment": 0.65,
    "liked_myself": 0.55,
    "fatigued": -0.75,
    "repeat": 0.8,
}
PERSONAL_DECAY_DAYS = 45.0
PERSONAL_MAX_ADJUSTMENT = 18.0
AI_MAX_ADJUSTMENT = 3.0
AI_RERANK_MAX_GAP = 7.0

LAYERING_WEIGHTS = {
    "accords": 0.16,
    "notes": 0.08,
    "bridging": 0.08,
    "contrast": 0.08,
    "freshness_balance": 0.08,
    "sweetness_balance": 0.08,
    "density_balance": 0.10,
    "warmth_balance": 0.07,
    "projection_balance": 0.08,
    "scenario": 0.08,
    "climate": 0.07,
    "close_distance": 0.04,
}
