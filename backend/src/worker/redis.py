from __future__ import annotations

import arq
from arq.connections import RedisSettings
from src.config import settings


async def get_redis_pool() -> arq.ArqRedis:
    """
    Create and return an ArqRedis connection pool using default RedisSettings.
    Intended for use as a FastAPI dependency in request handlers.
    """
    # Use REDIS_URL from settings if provided; otherwise RedisSettings defaults apply
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL) if settings.REDIS_URL else RedisSettings()
    return await arq.create_pool(redis_settings)


def create_pool() -> arq.ArqRedis:
    """
    Create and return a synchronous ArqRedis client for worker startup code.
    """
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL) if settings.REDIS_URL else RedisSettings()
    return arq.ArqRedis.from_pool_or_new(redis_settings)
