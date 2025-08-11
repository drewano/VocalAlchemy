import logging
from typing import Tuple, Dict, Any

from ..infrastructure.repositories.analysis_repository import AnalysisRepository
from ..infrastructure.sql_models import AnalysisStatus
from ..infrastructure import sql_models as models
from .blob_storage_service import BlobStorageService
from typing import Protocol


class Transcriber(Protocol):
    async def submit_batch_transcription(self, audio_sas_url: str, original_filename: str) -> str:
        ...

    async def check_transcription_status(self, status_url: str) -> dict:
        ...

    async def get_transcription_files(self, status_url: str) -> dict:
        ...

    async def get_transcription_result(self, files_response: dict) -> str:
        ...

    async def delete_blob(self, blob_name: str) -> None:
        ...


class TranscriptionOrchestratorService:
    def __init__(
        self,
        analysis_repo: AnalysisRepository,
        blob_storage_service: BlobStorageService,
        transcriber: Transcriber,
    ) -> None:
        self.analysis_repo = analysis_repo
        self.blob_storage_service = blob_storage_service
        self.transcriber = transcriber

    async def submit_transcription(self, analysis: models.Analysis, normalized_audio_blob_name: str) -> None:
        """
        Submit a transcription job for the normalized audio file.
        """
        # Get SAS URL for the normalized audio blob
        audio_sas_url = await self.blob_storage_service.get_blob_sas_url(normalized_audio_blob_name)
        
        # Submit transcription job
        status_url = await self.transcriber.submit_batch_transcription(audio_sas_url, analysis.filename)
        
        # Update analysis record with job information
        analysis.transcription_job_url = status_url
        analysis.normalized_blob_name = normalized_audio_blob_name
        try:
            await self.analysis_repo.db.commit()
        except Exception:
            pass

    async def check_and_finalize_transcription(self, analysis: models.Analysis) -> Tuple[str, Dict[Any, Any]]:
        """
        Check the status of a transcription job and finalize if completed.
        """
        if analysis.status != AnalysisStatus.TRANSCRIPTION_IN_PROGRESS:
            return ("running", {})
        if not analysis.transcription_job_url:
            logging.warning("No transcription_job_url stored for analysis %s", analysis.id)
            return ("running", {})

        status_resp = await self.transcriber.check_transcription_status(analysis.transcription_job_url)
        status = str(status_resp.get("status") or status_resp.get("statusCode")).lower()
        if status == "succeeded":
            files_response = await self.transcriber.get_transcription_files(analysis.transcription_job_url)
            full_text = await self.transcriber.get_transcription_result(files_response)
            transcript_blob_name = f"{analysis.id}/transcription.txt"
            await self.blob_storage_service.upload_blob(full_text, transcript_blob_name)
            await self.analysis_repo.update_paths_and_status(
                analysis.id,
                status=AnalysisStatus.ANALYSIS_PENDING,
                transcript_blob_name=transcript_blob_name,
            )
            return ("succeeded", status_resp)
        elif status == "failed":
            logging.error(f"Azure transcription failed. Full response: {status_resp}")
            await self.analysis_repo.update_status(analysis.id, AnalysisStatus.TRANSCRIPTION_FAILED)
            return ("failed", status_resp)
        else:
            return ("running", status_resp)