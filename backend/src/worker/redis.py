from __future__ import annotations

import arq
from arq.connections import RedisSettings
from src.config import settings


async def get_redis_pool() -> arq.ArqRedis:
    """
    Create and return an ArqRedis connection pool using RedisSettings.
    Intended for use as a FastAPI dependency in request handlers.
    """
    redis_settings = get_redis_settings()
    return await arq.create_pool(redis_settings)


def get_redis_settings() -> RedisSettings:
    """
    Get and return RedisSettings configuration object.
    Uses REDIS_URL from settings if provided, otherwise uses default RedisSettings.
    """
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL) if settings.REDIS_URL else RedisSettings()
    return redis_settings
