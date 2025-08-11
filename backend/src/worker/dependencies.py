from contextlib import asynccontextmanager
from src.services.shared_services import (
    get_blob_storage_service,
    get_transcriber as create_transcriber,
    get_ai_analyzer
)
from src.services.analysis_service import AnalysisService
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
