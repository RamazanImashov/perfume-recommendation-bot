from __future__ import annotations

from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    bot_token: str
    owner_id: int | None = None
    public_url: str | None = None
    webhook_secret: str = "perfume-bot-secret"
    environment: str = "development"
    redis_rest_url: str | None = None
    redis_rest_token: str | None = None
    fsm_ttl_seconds: int = 86400
    ai_enabled: bool = False
    ai_api_key: str | None = None
    ai_base_url: str | None = None
    ai_model: str | None = None

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"} or bool(self.public_url)


def _as_bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is missing. Add it to .env")

    owner_id_raw = os.getenv("OWNER_ID")
    owner_id = int(owner_id_raw) if owner_id_raw and owner_id_raw.isdigit() else None
    public_url = os.getenv("PUBLIC_URL") or None
    environment = os.getenv("APP_ENV", "production" if public_url else "development")
    if public_url and owner_id is None:
        raise RuntimeError("OWNER_ID is required for public/Vercel deployment")

    redis_url = os.getenv("REDIS_REST_URL") or os.getenv("UPSTASH_REDIS_REST_URL") or os.getenv("KV_REST_API_URL")
    redis_token = os.getenv("REDIS_REST_TOKEN") or os.getenv("UPSTASH_REDIS_REST_TOKEN") or os.getenv("KV_REST_API_TOKEN")
    return Config(
        bot_token=token,
        owner_id=owner_id,
        public_url=public_url,
        webhook_secret=os.getenv("WEBHOOK_SECRET", "perfume-bot-secret"),
        environment=environment,
        redis_rest_url=redis_url,
        redis_rest_token=redis_token,
        fsm_ttl_seconds=int(os.getenv("FSM_TTL_SECONDS", "86400")),
        ai_enabled=_as_bool(os.getenv("AI_ENABLED")),
        ai_api_key=os.getenv("AI_API_KEY") or None,
        ai_base_url=(os.getenv("AI_BASE_URL") or "https://integrate.api.nvidia.com/v1").rstrip("/"),
        ai_model=os.getenv("AI_MODEL") or None,
    )
