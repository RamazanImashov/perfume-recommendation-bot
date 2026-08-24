from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.models.outfit import OutfitProfile

Event = Literal["study", "work", "meeting", "walk", "cafe", "date", "restaurant", "party", "club", "birthday", "active", "casual"]
TimeOfDay = Literal["morning", "day", "evening", "night"]
Season = Literal["spring", "summer", "autumn", "winter"]
Exposure = Literal["low", "medium", "high"]


class Situation(BaseModel):
    event: Event = "casual"
    event_modifiers: list[str] = Field(default_factory=list)
    importance: Literal["low", "medium", "high"] = "medium"
    formality: float = 2.0
    circumstance: str = "outdoor"
    outdoor_exposure: Exposure = "medium"
    desired_effect: str = "any"
    time_of_day: TimeOfDay = "day"
    season: Season = "summer"
    temperature: float = 20.0
    feels_like: float | None = None
    humidity: float | None = None
    rain: float = 0.0
    precipitation: float = 0.0
    cloud_cover: float | None = None
    wind_speed: float | None = None
    is_day: bool = True
    outfit: OutfitProfile = Field(default_factory=OutfitProfile)
    target_datetime: datetime | None = None
    location: str = ""
    latitude: float | None = None
    longitude: float | None = None
    timezone: str | None = None
    weather_source: str = "current"

    @field_validator("formality")
    @classmethod
    def clamp_formality(cls, value: float) -> float:
        return max(0.0, min(5.0, float(value)))
