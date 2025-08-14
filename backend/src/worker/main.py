from __future__ import annotations

import logging
import arq
from arq import cron
from arq import func
from datetime import timedelta

from src.worker.tasks import (
    start_transcription_task,
    check_transcription_status_task,
    setup_ai_analysis_pipeline_task,
    run_single_ai_step_task,
    delete_analysis_task,
    rerun_ai_analysis_step_task,
    check_stale_transcriptions_task,
    RETRY_SETTINGS,
)
from src.worker.redis import get_redis_settings
from src.infrastructure.database import engine, async_session_factory
from src.infrastructure import sql_models as models
from src.infrastructure.repositories.analysis_repository import AnalysisRepository
from src.worker.dependencies import dependencies


async def on_startup(ctx):
    # Ensure DB tables exist when the worker starts using async engine
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)

    # Inject dependencies container into ARQ context and ensure Blob container exists
    ctx["dependencies"] = dependencies
    await dependencies.blob_storage_service.ensure_container_exists()
    
    # Check for in-progress transcriptions to resume
    try:
        logging.info("Checking for in-progress transcriptions to resume...")
        async with async_session_factory() as session:
            repo = AnalysisRepository(session)
            in_progress_analyses = await repo.get_in_progress_transcriptions()
            
            if in_progress_analyses:
                redis_settings = get_redis_settings()
                redis_pool = await arq.create_pool(redis_settings)
                try:
                    for analysis in in_progress_analyses:
                        logging.info(f"Resuming transcription check for analysis {analysis.id}")
                        await redis_pool.enqueue_job('check_transcription_status_task', analysis.id)
                finally:
                    await redis_pool.close()
    except Exception as e:
        logging.error(f"Error while resuming in-progress transcriptions: {e}")


class WorkerSettings:
    functions = [
        func(start_transcription_task, **RETRY_SETTINGS),
        func(check_transcription_status_task, **RETRY_SETTINGS),
        func(setup_ai_analysis_pipeline_task, **RETRY_SETTINGS),
        func(run_single_ai_step_task, **RETRY_SETTINGS),
        func(delete_analysis_task, **RETRY_SETTINGS),
        func(rerun_ai_analysis_step_task, **RETRY_SETTINGS),
    ]
    cron_jobs = [
        cron(check_stale_transcriptions_task, hour={0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22}, minute=0)
    ]
    redis_settings = get_redis_settings()
    on_startup = on_startup
    retry_delay = timedelta(seconds=60)
    job_timeout = 900
