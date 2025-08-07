from contextlib import asynccontextmanager
from src.config import settings
from src.services.blob_storage_service import BlobStorageService
from src.services.external_apis.azure_speech_client import AzureSpeechClient
from src.services.external_apis.litellm_ai_processor import LiteLLMAIProcessor
from src.services.analysis_service import AnalysisService
from src.infrastructure.repositories.analysis_repository import AnalysisRepository
from src.infrastructure.database import async_session_factory
from sqlalchemy.ext.asyncio import AsyncSession


class WorkerDependencies:
    def __init__(self) -> None:
        # Initialize Blob Storage service
        self.blob_storage_service = BlobStorageService(
            storage_connection_string=settings.AZURE_STORAGE_CONNECTION_STRING,
            storage_container_name=settings.AZURE_STORAGE_CONTAINER_NAME,
        )

        # Initialize Azure Speech client with BlobStorageService
        self.speech_client = AzureSpeechClient(
            api_key=settings.AZURE_SPEECH_KEY,
            region=settings.AZURE_SPEECH_REGION,
            blob_storage_service=self.blob_storage_service,
        )

        # Initialize AI analyzer (LiteLLM)
        self.ai_analyzer = LiteLLMAIProcessor(
            model_name=settings.AZURE_AI_MODEL_NAME,
        )

    def create_analysis_service(self, db_session: AsyncSession) -> AnalysisService:
        """Create an AnalysisService instance with the given database session."""
        # Instantiate AnalysisRepository with the provided db_session
        analysis_repository = AnalysisRepository(db_session)
        
        # Instantiate AnalysisService with the repository and existing services
        return AnalysisService(
            analysis_repo=analysis_repository,
            transcriber=self.speech_client,
            ai_analyzer=self.ai_analyzer,
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
