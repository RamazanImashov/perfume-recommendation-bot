from __future__ import annotations

from datetime import datetime, timezone

from app.models.recommendation import FeedbackRecord
from app.storage.base import PersonalStorage


class OwnerHistory:
    def __init__(self, storage: PersonalStorage):
        self.storage = storage

    @property
    def enabled(self) -> bool:
        return self.storage.enabled

    async def get_preferences(self) -> dict:
        return await self.storage.get_json("preferences", {"repeat_mode": "diversity"})

    async def set_preference(self, key: str, value) -> None:
        prefs = await self.get_preferences()
        prefs[key] = value
        await self.storage.set_json("preferences", prefs)

    async def get_history(self) -> list[dict]:
        return await self.storage.get_json("wear_history", [])

    async def append_feedback(self, record: FeedbackRecord) -> None:
        await self.storage.append_json("wear_history", record.model_dump(mode="json"), limit=300)

    async def save_last_situation(self, situation: dict) -> None:
        await self.storage.set_json("last_situation", situation)

    async def get_last_situation(self) -> dict | None:
        return await self.storage.get_json("last_situation", None)

    async def save_last_location(self, location: dict) -> None:
        await self.storage.set_json("last_location", location)

    async def get_last_location(self) -> dict | None:
        return await self.storage.get_json("last_location", None)

    async def save_last_recommendation(self, payload: dict) -> None:
        payload = dict(payload)
        payload["saved_at"] = datetime.now(timezone.utc).isoformat()
        await self.storage.set_json("last_recommendation", payload, ttl_seconds=7 * 86400)

    async def get_last_recommendation(self) -> dict | None:
        return await self.storage.get_json("last_recommendation", None)
