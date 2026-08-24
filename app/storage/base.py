from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PersonalStorage(ABC):
    @property
    @abstractmethod
    def enabled(self) -> bool: ...

    @abstractmethod
    async def get_json(self, key: str, default: Any = None) -> Any: ...

    @abstractmethod
    async def set_json(self, key: str, value: Any, ttl_seconds: int | None = None) -> None: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    async def append_json(self, key: str, value: Any, limit: int = 200) -> None:
        items = await self.get_json(key, [])
        if not isinstance(items, list):
            items = []
        items.append(value)
        await self.set_json(key, items[-limit:])
