from __future__ import annotations

from arq import cron  # noqa: F401 (may be useful later)

from src.worker.tasks import (
    start_transcription_task,
    check_transcription_status_task,
    run_ai_analysis_task,
    delete_analysis_task,
)
from src.worker.redis import create_pool
from src.infrastructure.database import engine
from src.infrastructure import sql_models as models


async def on_startup(ctx):
    # Ensure DB tables exist when the worker starts using async engine
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)


class WorkerSettings:
    functions = [
        start_transcription_task,
        check_transcription_status_task,
        run_ai_analysis_task,
        delete_analysis_task,
    ]
    redis_pool = create_pool()
    on_startup = on_startup
