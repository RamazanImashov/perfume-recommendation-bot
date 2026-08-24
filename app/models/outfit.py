from __future__ import annotations

from pydantic import BaseModel, Field


class OutfitProfile(BaseModel):
    top_type: str | None = None
    top_color: str | None = None
    bottom_type: str | None = None
    bottom_color: str | None = None
    shoes_type: str | None = None
    shoes_color: str | None = None
    outerwear: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    colors: list[str] = Field(default_factory=list)
    palette: str = "neutral"
    style: list[str] = Field(default_factory=lambda: ["casual"])
    formality: float = 2.0
    fit: str | None = None
    weather_weight: str = "medium"
    garments: list[str] = Field(default_factory=list)
    legacy_tags: list[str] = Field(default_factory=list)
    raw_text: str = ""
