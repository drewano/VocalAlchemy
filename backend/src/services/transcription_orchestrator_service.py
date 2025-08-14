import logging
from typing import Tuple, Dict, Any

from ..infrastructure.repositories.analysis_repository import AnalysisRepository
from ..infrastructure.sql_models import AnalysisStatus
from .blob_storage_service import BlobStorageService
from typing import Protocol


class Transcriber(Protocol):
    async def submit_batch_transcription(
        self, audio_sas_url: str, original_filename: str
    ) -> str: ...

    async def check_transcription_status(self, status_url: str) -> dict: ...

    async def get_transcription_files(self, status_url: str) -> dict: ...

    async def get_transcription_result(self, files_response: dict) -> str: ...

    async def delete_blob(self, blob_name: str) -> None: ...


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

    async def submit_transcription(
        self, analysis_id: str, normalized_audio_blob_name: str
    ) -> None:
        """
        Submit a transcription job for the normalized audio file.
        """
        # Retrieve the analysis object using the ID
        analysis = await self.analysis_repo.get_by_id(analysis_id)
        if not analysis:
            raise ValueError(f"Analysis not found: {analysis_id}")

        # Get SAS URL for the normalized audio blob
        audio_sas_url = await self.blob_storage_service.get_blob_sas_url(
            normalized_audio_blob_name
        )

        # Submit transcription job
        status_url = await self.transcriber.submit_batch_transcription(
            audio_sas_url, analysis.filename
        )

        # Update analysis record with job information
        analysis.transcription_job_url = status_url
        analysis.normalized_blob_name = normalized_audio_blob_name
        await self.analysis_repo.db.commit()

    async def check_and_finalize_transcription(
        self, analysis_id: str
    ) -> str:
        """
        Check the status of a transcription job and finalize if completed.
        Returns a string indicating the status: 'succeeded', 'failed', or 'running'.
        """
        # Retrieve the analysis object using the ID
        analysis = await self.analysis_repo.get_by_id(analysis_id)
        if not analysis:
            raise ValueError(f"Analysis not found: {analysis_id}")

        if analysis.status != AnalysisStatus.TRANSCRIPTION_IN_PROGRESS:
            return "running"
        if not analysis.transcription_job_url:
            error_msg = f"L'URL du job de transcription est manquante pour l'analyse {analysis.id}. Le job n'a probablement pas pu être soumis correctement."
            logging.error(error_msg)
            analysis.status = AnalysisStatus.TRANSCRIPTION_FAILED
            analysis.error_message = error_msg
            await self.analysis_repo.db.commit()
            raise ValueError(error_msg)

        status_resp = await self.transcriber.check_transcription_status(
            analysis.transcription_job_url
        )
        
        # Robustly extract status from the response
        status = status_resp.get("status")
        if not status:
            logging.warning(f"Unexpected status response format for analysis {analysis_id}: {status_resp}")
            return "running"
        status = status.lower()

        if status == "succeeded":
            files_response = await self.transcriber.get_transcription_files(
                analysis.transcription_job_url
            )
            full_text = await self.transcriber.get_transcription_result(files_response)
            transcript_blob_name = f"{analysis.id}/transcription.txt"
            await self.blob_storage_service.upload_blob(full_text, transcript_blob_name)
            await self.analysis_repo.update_paths_and_status(
                analysis.id,
                status=AnalysisStatus.ANALYSIS_PENDING,
                transcript_blob_name=transcript_blob_name,
            )
            return "succeeded"
        elif status == "failed":
            logging.error(f"Azure transcription failed. Full response: {status_resp}")
            
            # Extract detailed error message from Azure response
            azure_error = status_resp.get("properties", {}).get("error", {})
            if azure_error and isinstance(azure_error, dict):
                code = azure_error.get("code")
                message = azure_error.get("message")
                details = azure_error.get("details")
                error_str_parts = []
                if code:
                    error_str_parts.append(f"code={code}")
                if message:
                    error_str_parts.append(f"message={message}")
                if details:
                    error_str_parts.append(f"details={details}")
                formatted_error = (
                    "; ".join(error_str_parts)
                    if error_str_parts
                    else str(azure_error)
                )
            else:
                formatted_error = "Transcription failed with unknown Azure error format"
            
            # Update database with error
            analysis.status = AnalysisStatus.TRANSCRIPTION_FAILED
            analysis.error_message = formatted_error
            await self.analysis_repo.db.commit()
            
            return "failed"
        elif status in ["running", "notstarted"]:
            return "running"
        else:
            logging.warning(f"Unexpected transcription status '{status}' for analysis {analysis_id}. Treating as 'running'.")
            return "running"
