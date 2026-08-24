from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp

from app.storage.base import PersonalStorage

logger = logging.getLogger(__name__)


class RedisRestClient:
    """Minimal Redis-over-HTTP client compatible with Upstash REST style APIs."""

    def __init__(self, url: str, token: str, timeout: float = 4.0):
        self.url = url.rstrip("/")
        self.token = token
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    async def command(self, *parts: Any) -> Any:
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        payload = [str(p) for p in parts]
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(self.url, headers=headers, json=payload) as response:
                response.raise_for_status()
                data = await response.json()
        if data.get("error"):
            raise RuntimeError(data["error"])
        return data.get("result")


class RedisPersonalStorage(PersonalStorage):
    def __init__(self, client: RedisRestClient, prefix: str = "perfume:owner"):
        self.client = client
        self.prefix = prefix

    @property
    def enabled(self) -> bool:
        return True

    def _key(self, key: str) -> str:
        return f"{self.prefix}:{key}"

    async def get_json(self, key: str, default: Any = None) -> Any:
        try:
            raw = await self.client.command("GET", self._key(key))
            return json.loads(raw) if raw is not None else default
        except Exception as exc:
            logger.warning("Persistent storage GET failed: %s", exc)
            return default

    async def set_json(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        try:
            raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
            if ttl_seconds:
                await self.client.command("SET", self._key(key), raw, "EX", ttl_seconds)
            else:
                await self.client.command("SET", self._key(key), raw)
        except Exception as exc:
            logger.warning("Persistent storage SET failed: %s", exc)

    async def delete(self, key: str) -> None:
        try:
            await self.client.command("DEL", self._key(key))
        except Exception as exc:
            logger.warning("Persistent storage DEL failed: %s", exc)


# Import aiogram lazily so pure recommendation tests do not depend on it.
try:
    from aiogram.fsm.storage.base import BaseStorage, StateType, StorageKey
except Exception:  # pragma: no cover - exercised only in stripped test environments
    BaseStorage = object  # type: ignore[misc,assignment]
    StateType = Any  # type: ignore[assignment]
    StorageKey = Any  # type: ignore[assignment]


class RedisRestFSMStorage(BaseStorage):  # type: ignore[misc]
    def __init__(self, client: RedisRestClient, ttl_seconds: int = 86400, prefix: str = "perfume:fsm"):
        self.client = client
        self.ttl_seconds = ttl_seconds
        self.prefix = prefix
        self._fallback: dict[str, dict[str, Any]] = {}

    def _key(self, key: StorageKey) -> str:
        bot_id = getattr(key, "bot_id", 0)
        chat_id = getattr(key, "chat_id", 0)
        user_id = getattr(key, "user_id", 0)
        thread_id = getattr(key, "thread_id", None)
        destiny = getattr(key, "destiny", "default")
        return f"{self.prefix}:{bot_id}:{chat_id}:{user_id}:{thread_id or 0}:{destiny}"

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        data = await self._get_payload(key)
        value = state.state if hasattr(state, "state") else state
        data["state"] = value
        await self._set_payload(key, data)

    async def get_state(self, key: StorageKey) -> str | None:
        return (await self._get_payload(key)).get("state")

    async def set_data(self, key: StorageKey, data: dict[str, Any]) -> None:
        payload = await self._get_payload(key)
        payload["data"] = dict(data)
        await self._set_payload(key, payload)

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        data = (await self._get_payload(key)).get("data") or {}
        return dict(data) if isinstance(data, dict) else {}

    async def close(self) -> None:
        return None

    async def _get_payload(self, key: StorageKey) -> dict[str, Any]:
        try:
            storage_key = self._key(key)
            raw = await self.client.command("GET", storage_key)
            if raw:
                payload = json.loads(raw)
                self._fallback[storage_key] = payload
                return payload
            return self._fallback.get(storage_key, {"state": None, "data": {}})
        except Exception as exc:
            logger.warning("FSM REST GET failed; process-memory fallback used: %s", exc)
            return self._fallback.get(self._key(key), {"state": None, "data": {}})

    async def _set_payload(self, key: StorageKey, payload: dict[str, Any]) -> None:
        try:
            storage_key = self._key(key)
            self._fallback[storage_key] = payload
            raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
            await self.client.command("SET", storage_key, raw, "EX", self.ttl_seconds)
        except Exception as exc:
            logger.warning("FSM REST SET failed; process-memory fallback kept: %s", exc)
