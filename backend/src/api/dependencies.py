from functools import lru_cache
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database import get_async_db
from src.infrastructure.repositories.analysis_repository import AnalysisRepository
from src.services.analysis_service import AnalysisService
from src.services.export_service import ExportService
from src.services.shared_services import (
    get_blob_storage_service,
    get_transcriber as create_transcriber,
    get_ai_analyzer
)
from src.services.external_apis.azure_speech_client import AzureSpeechClient
from src.services.external_apis.litellm_ai_processor import LiteLLMAIProcessor
from src.services.blob_storage_service import BlobStorageService
from src.worker.redis import get_redis_pool
from arq.connections import ArqRedis


def get_analysis_repository(db: AsyncSession = Depends(get_async_db)) -> AnalysisRepository:
    return AnalysisRepository(db)


def get_transcriber_service(
    blob_storage_service: BlobStorageService = Depends(get_blob_storage_service)
) -> AzureSpeechClient:
    return create_transcriber(blob_storage_service=blob_storage_service)


def get_analysis_service(
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),
    transcriber: AzureSpeechClient = Depends(get_transcriber_service),
    ai_analyzer: LiteLLMAIProcessor = Depends(get_ai_analyzer),
    blob_storage_service: BlobStorageService = Depends(get_blob_storage_service),
) -> AnalysisService:
    return AnalysisService(
        analysis_repo,
        transcriber=transcriber,
        ai_analyzer=ai_analyzer,
        blob_storage_service=blob_storage_service,
    )


def get_export_service(
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),
    blob_storage_service: BlobStorageService = Depends(get_blob_storage_service),
) -> ExportService:
    return ExportService(
        analysis_repo,
        blob_storage_service,
    )


# Constant for ARQ pool dependency
ARQ_POOL = Depends(get_redis_pool)