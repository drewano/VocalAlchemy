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
from src.services.audio_processing_service import AudioProcessingService
from src.services.transcription_orchestrator_service import TranscriptionOrchestratorService
from src.services.ai_pipeline_service import AIPipelineService
from src.worker.redis import get_redis_pool
from arq.connections import ArqRedis


def get_analysis_repository(db: AsyncSession = Depends(get_async_db)) -> AnalysisRepository:
    return AnalysisRepository(db)


def get_transcriber_service(
    blob_storage_service: BlobStorageService = Depends(get_blob_storage_service)
) -> AzureSpeechClient:
    return create_transcriber(blob_storage_service=blob_storage_service)


def get_audio_processing_service(
    blob_storage_service: BlobStorageService = Depends(get_blob_storage_service)
) -> AudioProcessingService:
    return AudioProcessingService(blob_storage_service=blob_storage_service)


def get_transcription_orchestrator_service(
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),
    blob_storage_service: BlobStorageService = Depends(get_blob_storage_service),
    transcriber: AzureSpeechClient = Depends(get_transcriber_service),
) -> TranscriptionOrchestratorService:
    return TranscriptionOrchestratorService(
        analysis_repo=analysis_repo,
        blob_storage_service=blob_storage_service,
        transcriber=transcriber,
    )


def get_ai_pipeline_service(
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),
    blob_storage_service: BlobStorageService = Depends(get_blob_storage_service),
    ai_analyzer: LiteLLMAIProcessor = Depends(get_ai_analyzer),
) -> AIPipelineService:
    return AIPipelineService(
        analysis_repo=analysis_repo,
        blob_storage_service=blob_storage_service,
        ai_analyzer=ai_analyzer,
    )


def get_analysis_service(
    analysis_repo: AnalysisRepository = Depends(get_analysis_repository),
    audio_processing_service: AudioProcessingService = Depends(get_audio_processing_service),
    transcription_orchestrator_service: TranscriptionOrchestratorService = Depends(get_transcription_orchestrator_service),
    ai_pipeline_service: AIPipelineService = Depends(get_ai_pipeline_service),
    blob_storage_service: BlobStorageService = Depends(get_blob_storage_service),
) -> AnalysisService:
    return AnalysisService(
        analysis_repo,
        audio_processing_service=audio_processing_service,
        transcription_orchestrator_service=transcription_orchestrator_service,
        ai_pipeline_service=ai_pipeline_service,
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