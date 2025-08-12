from __future__ import annotations

from arq import cron  # noqa: F401 (may be useful later)
from arq import func
from datetime import timedelta

from src.worker.tasks import (
    start_transcription_task,
    check_transcription_status_task,
    setup_ai_analysis_pipeline_task,
    run_single_ai_step_task,
    delete_analysis_task,
    rerun_ai_analysis_step_task,
    RETRY_SETTINGS,
)
from src.worker.redis import get_redis_settings
from src.infrastructure.database import engine
from src.infrastructure import sql_models as models
from src.worker.dependencies import dependencies


async def on_startup(ctx):
    # Ensure DB tables exist when the worker starts using async engine
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)

    # Inject dependencies container into ARQ context and ensure Blob container exists
    ctx["dependencies"] = dependencies
    await dependencies.blob_storage_service.ensure_container_exists()


class WorkerSettings:
    functions = [
        func(start_transcription_task, **RETRY_SETTINGS),
        func(check_transcription_status_task, **RETRY_SETTINGS),
        func(setup_ai_analysis_pipeline_task, **RETRY_SETTINGS),
        func(run_single_ai_step_task, **RETRY_SETTINGS),
        func(delete_analysis_task, **RETRY_SETTINGS),
        func(rerun_ai_analysis_step_task, **RETRY_SETTINGS),
    ]
    redis_settings = get_redis_settings()
    on_startup = on_startup
    retry_delay = timedelta(seconds=60)
    job_timeout = 900
