from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp
from pydantic import ValidationError

from app.config import Config
from app.models.situation import Situation
from app.services.scoring_config import AI_MAX_ADJUSTMENT, AI_RERANK_MAX_GAP

logger = logging.getLogger(__name__)


class AIClient:
    def __init__(self, config: Config):
        self.enabled = bool(config.ai_enabled and config.ai_api_key and config.ai_model and config.ai_base_url)
        self.api_key = config.ai_api_key
        self.base_url = config.ai_base_url or ""
        self.model = config.ai_model
        self.timeout = aiohttp.ClientTimeout(total=10)

    async def _chat_json(self, messages: list[dict[str, str]]) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(f"{self.base_url}/chat/completions", headers=headers, json=payload) as response:
                    response.raise_for_status()
                    data = await response.json()
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
        except Exception as exc:
            logger.warning("AI API unavailable; deterministic fallback used: %s", exc)
            return None

    async def parse_situation(self, text: str, base: Situation) -> Situation | None:
        data = await self._chat_json([
            {"role": "system", "content": "Extract only a perfume recommendation Situation JSON. Never invent weather or perfume facts. Return only fields present or strongly implied by the user text."},
            {"role": "user", "content": json.dumps({"text": text, "base": base.model_dump(mode="json")}, ensure_ascii=False)},
        ])
        if not data:
            return None
        try:
            merged = base.model_dump()
            for key, value in data.items():
                if key in merged and value is not None:
                    merged[key] = value
            return Situation.model_validate(merged)
        except ValidationError as exc:
            logger.warning("AI Situation JSON rejected: %s", exc)
            return None

    async def rerank(self, situation: Situation, candidates: list[dict]) -> dict[str, float]:
        if not self.enabled or not candidates:
            return {}
        safe = [{
            "name": c["name"], "score": c["score"], "facts": c.get("facts", {}), "breakdown": c.get("breakdown", {}), "warnings": c.get("warnings", []),
        } for c in candidates[:6]]
        data = await self._chat_json([
            {"role": "system", "content": "Rerank only the provided candidates. Do not add perfumes, change facts, ignore warnings, or invent notes/weather. Return {\"order\":[names...]} only."},
            {"role": "user", "content": json.dumps({"situation": situation.model_dump(mode="json"), "candidates": safe}, ensure_ascii=False)},
        ])
        order = data.get("order") if isinstance(data, dict) else None
        if not isinstance(order, list):
            return {}
        scores = {c["name"]: float(c["score"]) for c in safe}
        if not scores:
            return {}
        best = max(scores.values())
        adjustments: dict[str, float] = {}
        for rank, name in enumerate(order):
            if name not in scores or best - scores[name] > AI_RERANK_MAX_GAP:
                continue
            desired = AI_MAX_ADJUSTMENT * max(0.0, 1.0 - rank / max(1, len(order) - 1))
            adjustments[name] = round(desired, 2)
        return adjustments
