from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ScoreBreakdown(BaseModel):
    event_score: float
    climate_score: float
    effect_score: float
    environment_score: float
    outfit_score: float
    time_score: float
    season_score: float
    personal_score: float
    weighted_score: float
    hard_penalty: float = 0.0
    recent_wear_penalty: float = 0.0
    ai_adjustment: float = 0.0
    evidence: dict[str, list[str]] = Field(default_factory=dict)
    penalties: list[str] = Field(default_factory=list)


class RecommendationResult(BaseModel):
    perfume_id: int | None = None
    name: str
    brand: str
    score: float
    confidence: float
    confidence_label: str
    role: str = "candidate"
    breakdown: ScoreBreakdown
    hard_warnings: list[str] = Field(default_factory=list)
    spray_count: int = 2
    spray_locations: list[str] = Field(default_factory=list)
    spray_explanation: str = ""
    deterministic_score: float | None = None
    ai_adjustment: float = 0.0


class LayeringResult(BaseModel):
    base_name: str
    top_name: str
    score: float
    confidence: float
    confidence_label: str
    application_order: list[str]
    spray_plan: str
    subscores: dict[str, float] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    curated: bool = False
    curated_label: str = ""
    curated_best_for: str = ""


class FeedbackRecord(BaseModel):
    perfume: str | None = None
    layering: list[str] = Field(default_factory=list)
    timestamp: datetime
    event: str
    temperature: float | None = None
    humidity: float | None = None
    circumstance: str
    outfit_profile: dict = Field(default_factory=dict)
    effect: str
    sprays: str = ""
    rating: str
    feedback_tags: list[str] = Field(default_factory=list)
    recommendation_score: float = 0.0
    application_order: list[str] = Field(default_factory=list)
