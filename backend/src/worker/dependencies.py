from contextlib import asynccontextmanager
from src.services.shared_services import (
    get_blob_storage_service,
    get_transcriber as create_transcriber,
    get_ai_analyzer
)
from src.services.analysis_service import AnalysisService
from src.services.audio_processing_service import AudioProcessingService
from src.services.transcription_orchestrator_service import TranscriptionOrchestratorService
from src.services.ai_pipeline_service import AIPipelineService
from src.infrastructure.repositories.analysis_repository import AnalysisRepository
from src.infrastructure.database import async_session_factory
from sqlalchemy.ext.asyncio import AsyncSession


class WorkerDependencies:
    def __init__(self) -> None:
        # Initialize shared services using the centralized functions
        self.blob_storage_service = get_blob_storage_service()
        # Passez explicitement la dépendance à la fonction `get_transcriber` refactorisée
        self.speech_client = create_transcriber(blob_storage_service=self.blob_storage_service)
        self.ai_analyzer = get_ai_analyzer()
        
        # Initialize new specialized services
        self.audio_processing_service = AudioProcessingService(self.blob_storage_service)
        self.transcription_orchestrator_service = TranscriptionOrchestratorService(
            analysis_repo=AnalysisRepository(None),  # Temporary repo, will be replaced in create_analysis_service
            blob_storage_service=self.blob_storage_service,
            transcriber=self.speech_client
        )
        self.ai_pipeline_service = AIPipelineService(
            analysis_repo=AnalysisRepository(None),  # Temporary repo, will be replaced in create_analysis_service
            blob_storage_service=self.blob_storage_service,
            ai_analyzer=self.ai_analyzer
        )

    def create_analysis_service(self, db_session: AsyncSession) -> AnalysisService:
        """Create an AnalysisService instance with the given database session."""
        # Instantiate AnalysisRepository with the provided db_session
        analysis_repository = AnalysisRepository(db_session)
        
        # Update the specialized services with the correct repository
        self.transcription_orchestrator_service.analysis_repo = analysis_repository
        self.ai_pipeline_service.analysis_repo = analysis_repository
        
        # Instantiate AnalysisService with the new specialized services
        return AnalysisService(
            analysis_repo=analysis_repository,
            audio_processing_service=self.audio_processing_service,
            transcription_orchestrator_service=self.transcription_orchestrator_service,
            ai_pipeline_service=self.ai_pipeline_service,
            blob_storage_service=self.blob_storage_service,
        )


# Single global instance for worker processes
dependencies = WorkerDependencies()


@asynccontextmanager
async def get_analysis_service_provider(ctx: dict):
    """Async context manager to provide AnalysisService with database session for arq tasks."""
    # Get the dependencies instance from context
    deps = ctx["dependencies"]
    
    # Establish database session
    async with async_session_factory() as db_session:
        # Create service instance
        service = deps.create_analysis_service(db_session)
        # Provide service to caller
        yield service
