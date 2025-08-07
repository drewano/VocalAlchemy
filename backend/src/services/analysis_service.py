import json
import logging
import time
from typing import Optional, Protocol, List

from langextract.resolver import ResolverParsingError
from src.infrastructure.repositories.analysis_repository import AnalysisRepository
from src.services.external_apis.azure_speech_client import AzureSpeechClient
from src.services.external_apis.litellm_ai_processor import LiteLLMAIProcessor
from src.infrastructure.sql_models import AnalysisStatus
from src.services import pipeline_prompts
from pydub import AudioSegment
from src.services.blob_storage_service import BlobStorageService
import io
import uuid



class AnalysisNotFoundException(Exception):
    pass


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


class AIAnalyzer(Protocol):
    async def execute_prompt(self, system_prompt: str, user_content: str) -> str:
        ...


class AnalysisService:
    def __init__(
        self,
        analysis_repo: AnalysisRepository,
        *,
        transcriber: Transcriber,
        ai_analyzer: LiteLLMAIProcessor,
        blob_storage_service: BlobStorageService,
    ) -> None:
        self.analysis_repo = analysis_repo
        self.transcriber = transcriber
        self.ai_analyzer = ai_analyzer
        self.blob_storage_service = blob_storage_service

    

    async def _execute_analysis_pipeline(self, transcript: str, original_prompt: Optional[str]) -> str:
        if not isinstance(transcript, str) or not transcript.strip():
            raise ValueError("Invalid transcript for pipeline")

        # Étape 1 : Intervenants
        intervenants_md = await self.ai_analyzer.execute_prompt(
            system_prompt=pipeline_prompts.PROMPT_INTERVENANTS,
            user_content=transcript,
        )

        # Étape 2 : Ordre du Jour
        prompt_odj = pipeline_prompts.PROMPT_ORDRE_DU_JOUR.format(intervenants=intervenants_md)
        ordre_du_jour_md = await self.ai_analyzer.execute_prompt(
            system_prompt=prompt_odj,
            user_content=transcript,
        )

        # Étape 3 : Synthèse
        prompt_synthese = pipeline_prompts.PROMPT_SYNTHESE.format(
            intervenants=intervenants_md,
            ordre_du_jour=ordre_du_jour_md,
        )
        synthese_md = await self.ai_analyzer.execute_prompt(
            system_prompt=prompt_synthese,
            user_content=transcript,
        )

        # Étape 4 : Décisions et Actions
        prompt_decisions = pipeline_prompts.PROMPT_DECISIONS.format(
            intervenants=intervenants_md,
            synthese=synthese_md,
        )
        decisions_md = await self.ai_analyzer.execute_prompt(
            system_prompt=prompt_decisions,
            user_content=transcript,
        )

        # Assemblage Final
        final_report_content = (
            "# Procès-Verbal de Réunion\n\n"
            "## Intervenants\n" + intervenants_md.strip() + "\n\n"
            "## Ordre du jour\n" + ordre_du_jour_md.strip() + "\n\n"
            "## Synthèse des échanges\n" + synthese_md.strip() + "\n\n"
            "## Relevé de décisions et d'actions\n" + decisions_md.strip() + "\n"
        )
        return final_report_content

    async def start_transcription_pipeline(self, analysis_id: str, file_content: bytes, filename: str, blob_name: str) -> None:
        if not isinstance(file_content, (bytes, bytearray)) or len(file_content) == 0:
            raise ValueError("Invalid file_content provided")
        if not filename or not isinstance(filename, str):
            raise ValueError("Invalid filename provided")
        if not blob_name or not isinstance(blob_name, str):
            raise ValueError("Invalid blob_name provided")

        try:
            # 1. Charger l'audio original depuis la mémoire
            audio = AudioSegment.from_file(io.BytesIO(file_content))
            # 2. Normaliser l'audio: 16kHz, mono, 16-bit
            normalized_audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
            # 3. Exporter en FLAC en mémoire
            buf = io.BytesIO()
            normalized_audio.export(buf, format="flac")
            buf.seek(0)
            normalized_bytes = buf.read()

            # 4. Upload to blob and submit SAS URL to Azure
            self.analysis_repo.update_status(analysis_id, AnalysisStatus.TRANSCRIPTION_IN_PROGRESS)
            # upload normalized audio to the provided blob name
            await self.blob_storage_service.upload_blob(normalized_bytes, blob_name)
            audio_sas_url = await self.blob_storage_service.get_blob_sas_url(blob_name)
            status_url = await self.transcriber.submit_batch_transcription(audio_sas_url, filename)
            analysis = self.analysis_repo.get_by_id(analysis_id)
            if analysis:
                analysis.transcription_job_url = status_url
                self.analysis_repo.db.commit()
        except Exception as e:
            error_details = f"Transcription submission failed. Error type: {type(e).__name__}. Details: {e}"
            logging.error(error_details)
            self.analysis_repo.update_status(analysis_id, AnalysisStatus.TRANSCRIPTION_FAILED)
            analysis = self.analysis_repo.get_by_id(analysis_id)
            if analysis:
                analysis.error_message = error_details
                self.analysis_repo.db.commit()
            raise

    async def check_transcription_and_run_analysis(self, analysis_id: str) -> None:
        analysis = self.analysis_repo.get_by_id(analysis_id)
        if not analysis:
            raise AnalysisNotFoundException(f"Analysis not found: {analysis_id}")
        if analysis.status != AnalysisStatus.TRANSCRIPTION_IN_PROGRESS:
            return
        if not analysis.transcription_job_url:
            logging.warning("No transcription_job_url stored for analysis %s", analysis_id)
            return
        status_resp = await self.transcriber.check_transcription_status(analysis.transcription_job_url)
        status = str(status_resp.get("status") or status_resp.get("statusCode")).lower()
        if status == "succeeded":
            files_response = await self.transcriber.get_transcription_files(analysis.transcription_job_url)
            full_text = await self.transcriber.get_transcription_result(files_response)
            transcript_blob_name = f"{analysis_id}/transcription.txt"
            await self.blob_storage_service.upload_blob(full_text, transcript_blob_name)
            self.analysis_repo.update_paths_and_status(
                analysis_id,
                status=AnalysisStatus.ANALYSIS_PENDING,
                transcript_blob_name=transcript_blob_name,
            )
            try:
                # Start background analysis task; actual scheduling handled by caller/framework
                await self.run_ai_analysis_pipeline(analysis_id)
            except Exception as e:
                logging.error("Failed to start AI analysis background task: %s", e)
        elif status == "failed":
            logging.error(f"Azure transcription failed. Full response: {status_resp}")
            self.analysis_repo.update_status(analysis_id, AnalysisStatus.TRANSCRIPTION_FAILED)

    async def run_ai_analysis_pipeline(self, analysis_id: str) -> str:
        analysis = self.analysis_repo.get_by_id(analysis_id)
        if not analysis:
            raise AnalysisNotFoundException(f"Analysis not found: {analysis_id}")
        if not getattr(analysis, "transcript_blob_name", None):
            raise FileNotFoundError("Transcript blob not found for analysis")
        transcript = await self.blob_storage_service.download_blob_as_text(analysis.transcript_blob_name)
        try:
            self.analysis_repo.update_status(analysis_id, AnalysisStatus.ANALYSIS_IN_PROGRESS)
            final_report_content = await self._execute_analysis_pipeline(transcript, analysis.prompt)
            report_blob_name = f"{analysis_id}/versions/{str(uuid.uuid4())}/report.md"
            await self.blob_storage_service.upload_blob(final_report_content, report_blob_name)
            self.analysis_repo.add_version(
                analysis_id=analysis_id,
                prompt_used=analysis.prompt or "",
                result_blob_name=report_blob_name,
                people_involved=None,
                structured_plan=None,
            )
            self.analysis_repo.update_paths_and_status(analysis_id, status=AnalysisStatus.COMPLETED, result_blob_name=report_blob_name)
            self.analysis_repo.update_progress(analysis_id, 100)
            return report_blob_name
        except Exception as e:
            error_details = f"AI analysis failed. Error type: {type(e).__name__}. Details: {e}"
            logging.error(error_details)
            self.analysis_repo.update_status(analysis_id, AnalysisStatus.ANALYSIS_FAILED)
            analysis = self.analysis_repo.get_by_id(analysis_id)
            if analysis:
                analysis.error_message = error_details
                self.analysis_repo.db.commit()
            raise

    async def delete_analysis(self, analysis_id: str, user_id: int) -> None:
        analysis = self.analysis_repo.get_detailed_by_id(analysis_id)
        if not analysis:
            raise AnalysisNotFoundException(f"Analysis not found: {analysis_id}")
        if analysis.user_id != user_id:
            raise PermissionError('Access denied')

        # Aggregate blob names to delete
        blob_names: List[str] = []
        try:
            if getattr(analysis, "source_blob_name", None):
                blob_names.append(analysis.source_blob_name)
        except Exception:
            pass
        try:
            if getattr(analysis, "transcript_blob_name", None):
                blob_names.append(analysis.transcript_blob_name)
        except Exception:
            pass
        try:
            for v in getattr(analysis, "versions", []) or []:
                if getattr(v, "result_blob_name", None):
                    blob_names.append(v.result_blob_name)
        except Exception:
            pass

        # Delete blobs safely
        for name in blob_names:
            try:
                await self.blob_storage_service.delete_blob(name)
            except Exception as e:
                logging.warning(f"Failed to delete blob '{name}' for analysis {analysis_id}: {e}")

        # Finally delete DB record
        self.analysis_repo.delete(analysis_id)
