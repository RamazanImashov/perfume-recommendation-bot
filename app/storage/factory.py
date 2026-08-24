from __future__ import annotations

from app.config import Config
from app.storage.memory import DisabledPersonalStorage
from app.storage.redis import RedisPersonalStorage, RedisRestClient, RedisRestFSMStorage


def create_personal_storage(config: Config):
    if config.redis_rest_url and config.redis_rest_token:
        return RedisPersonalStorage(RedisRestClient(config.redis_rest_url, config.redis_rest_token))
    return DisabledPersonalStorage()


def create_fsm_storage(config: Config):
    if config.redis_rest_url and config.redis_rest_token:
        return RedisRestFSMStorage(RedisRestClient(config.redis_rest_url, config.redis_rest_token), ttl_seconds=config.fsm_ttl_seconds)
    from aiogram.fsm.storage.memory import MemoryStorage
    return MemoryStorage()
