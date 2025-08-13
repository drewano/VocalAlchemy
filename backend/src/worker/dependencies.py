from contextlib import asynccontextmanager
from src.services.shared_services import (
    get_blob_storage_service,
    get_transcriber as create_transcriber,
    get_ai_analyzer,
)
from src.services.analysis_service import AnalysisService
from src.services.audio_processing_service import AudioProcessingService
from src.services.transcription_orchestrator_service import (
    TranscriptionOrchestratorService,
)
from src.services.ai_pipeline_service import AIPipelineService
from src.infrastructure.repositories.analysis_repository import AnalysisRepository
from src.infrastructure.database import async_session_factory


class WorkerDependencies:
    def __init__(self) -> None:
        # Initialize shared services using the centralized functions
        self.blob_storage_service = get_blob_storage_service()
        # Passez explicitement la dépendance à la fonction `get_transcriber` refactorisée
        self.speech_client = create_transcriber(
            blob_storage_service=self.blob_storage_service
        )
        self.ai_analyzer = get_ai_analyzer()


# Single global instance for worker processes
dependencies = WorkerDependencies()


@asynccontextmanager
async def get_analysis_service_provider(ctx: dict):
    """Async context manager to provide AnalysisService with database session for arq tasks."""
    # Get the dependencies instance from context
    deps = ctx["dependencies"]

    # Establish database session
    async with async_session_factory() as db_session:
        # Instantiate AnalysisRepository with the provided db_session
        analysis_repository = AnalysisRepository(db_session)

        # Create all services with task-scoped instances
        audio_processing_service = AudioProcessingService(deps.blob_storage_service)
        transcription_orchestrator_service = TranscriptionOrchestratorService(
            analysis_repo=analysis_repository,
            blob_storage_service=deps.blob_storage_service,
            transcriber=deps.speech_client,
        )
        ai_pipeline_service = AIPipelineService(
            analysis_repo=analysis_repository,
            blob_storage_service=deps.blob_storage_service,
            ai_analyzer=deps.ai_analyzer,
        )
        analysis_service = AnalysisService(
            analysis_repo=analysis_repository,
            audio_processing_service=audio_processing_service,
            transcription_orchestrator_service=transcription_orchestrator_service,
            ai_pipeline_service=ai_pipeline_service,
            blob_storage_service=deps.blob_storage_service,
        )

        # Provide service to caller
        yield analysis_service


@asynccontextmanager
async def get_transcription_orchestrator_provider(ctx: dict):
    """Async context manager to provide TranscriptionOrchestratorService with database session for arq tasks."""
    # Get the dependencies instance from context
    deps = ctx["dependencies"]

    # Establish database session
    async with async_session_factory() as db_session:
        # Instantiate AnalysisRepository with the provided db_session
        analysis_repository = AnalysisRepository(db_session)

        # Create TranscriptionOrchestratorService with task-scoped instances
        transcription_orchestrator_service = TranscriptionOrchestratorService(
            analysis_repo=analysis_repository,
            blob_storage_service=deps.blob_storage_service,
            transcriber=deps.speech_client,
        )

        # Provide service to caller
        yield transcription_orchestrator_service


@asynccontextmanager
async def get_analysis_repository_provider(ctx: dict):
    """Async context manager to provide AnalysisRepository with database session for arq tasks."""
    # Establish database session
    async with async_session_factory() as db_session:
        # Instantiate AnalysisRepository with the provided db_session
        analysis_repository = AnalysisRepository(db_session)
        
        # Provide repository to caller
        yield analysis_repository