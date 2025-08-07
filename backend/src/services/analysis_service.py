import logging
import os
import tempfile
from typing import Protocol
from pydub import AudioSegment

from ..infrastructure.repositories.analysis_repository import AnalysisRepository
from .external_apis.litellm_ai_processor import LiteLLMAIProcessor
from ..infrastructure.sql_models import AnalysisStatus
from . import pipeline_prompts
from .blob_storage_service import BlobStorageService
import uuid


class FFmpegError(Exception):
    pass


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

    async def get_result_content(self, analysis_id: str, user_id: int) -> str:
        analysis = await self.analysis_repo.get_by_id(analysis_id)
        if not analysis:
            raise AnalysisNotFoundException("Analysis not found")
        if analysis.user_id != user_id:
            raise PermissionError("Access denied")
        if analysis.status != AnalysisStatus.COMPLETED:
            raise ValueError("Task not completed yet")
        if not getattr(analysis, "result_blob_name", None):
            raise FileNotFoundError("Result not found")
        return await self.blob_storage_service.download_blob_as_text(analysis.result_blob_name)

    async def get_transcript_content(self, analysis_id: str, user_id: int) -> str:
        analysis = await self.analysis_repo.get_by_id(analysis_id)
        if not analysis:
            raise AnalysisNotFoundException("Analysis not found")
        if analysis.user_id != user_id:
            raise PermissionError("Access denied")
        if analysis.status != AnalysisStatus.COMPLETED:
            raise ValueError("Task not completed yet")
        if not getattr(analysis, "transcript_blob_name", None):
            raise FileNotFoundError("Transcript not found")
        return await self.blob_storage_service.download_blob_as_text(analysis.transcript_blob_name)

    async def get_audio_sas_url(self, analysis_id: str, user_id: int) -> str:
        analysis = await self.analysis_repo.get_by_id(analysis_id)
        if not analysis:
            raise AnalysisNotFoundException("Analysis not found")
        if analysis.user_id != user_id:
            raise PermissionError("Access denied")
        blob_name = getattr(analysis, "source_blob_name", None)
        if not blob_name:
            raise FileNotFoundError("No source blob available")
        return await self.blob_storage_service.get_blob_sas_url(blob_name)

    async def get_version_result_content(self, version_id: str, user_id: int) -> str:
        version = await self.analysis_repo.get_version_by_id(version_id)
        if not version:
            raise AnalysisNotFoundException("Version not found")
        analysis = await self.analysis_repo.get_by_id(version.analysis_id)
        if not analysis:
            raise AnalysisNotFoundException("Parent analysis not found")
        if analysis.user_id != user_id:
            raise PermissionError("Access denied")
        if not getattr(version, "result_blob_name", None):
            raise FileNotFoundError("Version result not found")
        return await self.blob_storage_service.download_blob_as_text(version.result_blob_name)

    async def process_audio_for_transcription(self, analysis_id: str) -> None:
        # Récupération de l'objet analysis
        analysis = await self.analysis_repo.get_by_id(analysis_id)
        if not analysis:
            raise ValueError(f"Analysis not found: {analysis_id}")
        
        # Mise à jour du statut à TRANSCRIPTION_IN_PROGRESS
        await self.analysis_repo.update_status(analysis_id, AnalysisStatus.TRANSCRIPTION_IN_PROGRESS)
        
        # Génération d'un nom de blob unique pour le fichier normalisé (WAV PCM 16k mono)
        normalized_blob_name = f"{analysis.user_id}/{analysis_id}/normalized.wav"
        
        # Normalisation audio en streaming avec ffmpeg (FLAC 16kHz mono 16-bit)
        try:
            await self._normalize_audio_with_ffmpeg_stream(analysis.source_blob_name, normalized_blob_name)
        except FFmpegError as e:
            logging.error("Audio normalization failed for analysis %s: %s", analysis_id, e)
            await self.analysis_repo.update_status(analysis_id, AnalysisStatus.TRANSCRIPTION_FAILED)
            analysis.error_message = str(e)
            try:
                await self.analysis_repo.db.commit()
            except Exception:
                pass
            raise
        
        # Obtention de l'URL SAS pour le fichier normalisé
        audio_sas_url = await self.blob_storage_service.get_blob_sas_url(normalized_blob_name)
        
        # Soumission de la transcription
        status_url = await self.transcriber.submit_batch_transcription(audio_sas_url, analysis.filename)
        
        # Mise à jour de l'enregistrement analysis avec les nouvelles informations
        analysis.transcription_job_url = status_url
        analysis.normalized_blob_name = normalized_blob_name
        try:
            await self.analysis_repo.db.commit()
        except Exception:
            pass

    async def check_transcription_status(self, analysis_id: str) -> tuple[str, dict]:
        analysis = await self.analysis_repo.get_by_id(analysis_id)
        if not analysis:
            raise ValueError(f"Analysis not found: {analysis_id}")
        if analysis.status != AnalysisStatus.TRANSCRIPTION_IN_PROGRESS:
            return ("running", {})
        if not analysis.transcription_job_url:
            logging.warning("No transcription_job_url stored for analysis %s", analysis_id)
            return ("running", {})

        status_resp = await self.transcriber.check_transcription_status(analysis.transcription_job_url)
        status = str(status_resp.get("status") or status_resp.get("statusCode")).lower()
        if status == "succeeded":
            files_response = await self.transcriber.get_transcription_files(analysis.transcription_job_url)
            full_text = await self.transcriber.get_transcription_result(files_response)
            transcript_blob_name = f"{analysis_id}/transcription.txt"
            await self.blob_storage_service.upload_blob(full_text, transcript_blob_name)
            await self.analysis_repo.update_paths_and_status(
                analysis_id,
                status=AnalysisStatus.ANALYSIS_PENDING,
                transcript_blob_name=transcript_blob_name,
            )
            return ("succeeded", status_resp)
        elif status == "failed":
            logging.error(f"Azure transcription failed. Full response: {status_resp}")
            await self.analysis_repo.update_status(analysis_id, AnalysisStatus.TRANSCRIPTION_FAILED)
            return ("failed", status_resp)
        else:
            return ("running", status_resp)

    async def run_ai_analysis_pipeline(self, analysis_id: str) -> None:
        analysis = await self.analysis_repo.get_by_id(analysis_id)
        if not analysis:
            raise ValueError(f"Analysis not found: {analysis_id}")
        if not getattr(analysis, "transcript_blob_name", None):
            raise FileNotFoundError("Transcript blob not found for analysis")

        transcript = await self.blob_storage_service.download_blob_as_text(analysis.transcript_blob_name)
        # Validate transcript content before running prompts
        if not isinstance(transcript, str) or not transcript.strip():
            # Mark as failed with a helpful message, then raise
            await self.analysis_repo.update_status(analysis_id, AnalysisStatus.ANALYSIS_FAILED)
            analysis = await self.analysis_repo.get_by_id(analysis_id)
            if analysis:
                analysis.error_message = "Transcript is empty or invalid. Cannot run AI analysis."
                try:
                    await self.analysis_repo.db.commit()
                except Exception:
                    pass
            raise ValueError("Transcript is empty or invalid")

        try:
            await self.analysis_repo.update_status(analysis_id, AnalysisStatus.ANALYSIS_IN_PROGRESS)

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
            transcript_snippet = transcript[:200]
            analysis_snippet = final_report_content[:200]

            report_blob_name = f"{analysis_id}/versions/{str(uuid.uuid4())}/report.md"
            await self.blob_storage_service.upload_blob(final_report_content, report_blob_name)
            await self.analysis_repo.add_version(
                analysis_id=analysis_id,
                prompt_used=analysis.prompt or "",
                result_blob_name=report_blob_name,
                people_involved=None,
                structured_plan=None,
            )
            await self.analysis_repo.update_paths_and_status(
                analysis_id,
                status=AnalysisStatus.COMPLETED,
                result_blob_name=report_blob_name,
                transcript_snippet=transcript_snippet,
                analysis_snippet=analysis_snippet
            )
            await self.analysis_repo.update_progress(analysis_id, 100)
        except Exception as e:
            error_details = f"AI analysis failed. Error type: {type(e).__name__}. Details: {e}"
            logging.error(error_details)
            await self.analysis_repo.update_status(analysis_id, AnalysisStatus.ANALYSIS_FAILED)
            analysis = await self.analysis_repo.get_by_id(analysis_id)
            if analysis:
                analysis.error_message = error_details
                try:
                    await self.analysis_repo.db.commit()
                except Exception:
                    pass
            raise

    async def delete_analysis_data(self, analysis_id: str, user_id: int) -> None:
        analysis = await self.analysis_repo.get_detailed_by_id(analysis_id)
        if not analysis:
            raise ValueError(f"Analysis not found: {analysis_id}")
        if analysis.user_id != user_id:
            raise PermissionError("Access denied")

        blob_names: list[str] = []
        if getattr(analysis, "source_blob_name", None):
            blob_names.append(analysis.source_blob_name)
        if getattr(analysis, "normalized_blob_name", None):
            blob_names.append(analysis.normalized_blob_name)
        if getattr(analysis, "transcript_blob_name", None):
            blob_names.append(analysis.transcript_blob_name)
        for v in getattr(analysis, "versions", []) or []:
            if getattr(v, "result_blob_name", None):
                blob_names.append(v.result_blob_name)

        for name in blob_names:
            try:
                await self.blob_storage_service.delete_blob(name)
            except Exception as e:
                logging.warning(f"Failed to delete blob '{name}' for analysis {analysis_id}: {e}")

        await self.analysis_repo.delete(analysis_id)

    async def _normalize_audio_with_ffmpeg_stream(self, source_blob_name: str, normalized_blob_name: str) -> None:
        """
        Normalize audio using pydub with temporary files.
        Converts audio to WAV (PCM s16le) 16kHz mono format.
        """
        source_suffix = os.path.splitext(source_blob_name)[1] or ".tmp"
        output_suffix = ".wav"

        source_temp = tempfile.NamedTemporaryFile(delete=False, suffix=source_suffix)
        output_temp = tempfile.NamedTemporaryFile(delete=False, suffix=output_suffix)
        source_path = source_temp.name
        output_path = output_temp.name
        # Close immediately so we can reopen on Windows
        source_temp.close()
        output_temp.close()

        try:
            # Download source blob to temporary file
            with open(source_path, "wb") as f:
                async for chunk in self.blob_storage_service.download_blob_as_stream(source_blob_name):
                    f.write(chunk)

            # Convert using pydub
            try:
                sound = AudioSegment.from_file(source_path)
                sound = (
                    sound.set_frame_rate(16000)
                         .set_channels(1)
                         .set_sample_width(2)
                )
                sound.export(output_path, format="wav")
            except Exception as e:
                raise FFmpegError(f"Audio conversion failed with pydub: {e}") from e

            # Upload normalized file to blob storage
            file_size = os.path.getsize(output_path)
            with open(output_path, "rb") as f:
                await self.blob_storage_service.upload_blob_from_stream(
                    f, normalized_blob_name, length=file_size
                )
        finally:
            # Cleanup temporary files
            for path in (source_path, output_path):
                try:
                    os.remove(path)
                except Exception:
                    pass
