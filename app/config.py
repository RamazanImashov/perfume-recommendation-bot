from dataclasses import dataclass
import os
from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Config:
    bot_token: str
    owner_id: int | None = None


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is missing. Add it to .env")

    owner_id_raw = os.getenv("OWNER_ID")
    owner_id = int(owner_id_raw) if owner_id_raw and owner_id_raw.isdigit() else None

    return Config(bot_token=token, owner_id=owner_id)
