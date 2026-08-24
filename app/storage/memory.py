from __future__ import annotations

from typing import Any

from app.storage.base import PersonalStorage


class DisabledPersonalStorage(PersonalStorage):
    @property
    def enabled(self) -> bool:
        return False

    async def get_json(self, key: str, default: Any = None) -> Any:
        return default

    async def set_json(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        return None

    async def delete(self, key: str) -> None:
        return None
