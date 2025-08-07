import logging
import asyncio
from typing import Protocol

from src.infrastructure.repositories.analysis_repository import AnalysisRepository
from src.services.external_apis.litellm_ai_processor import LiteLLMAIProcessor
from src.infrastructure.sql_models import AnalysisStatus
from src.services import pipeline_prompts
from src.services.blob_storage_service import BlobStorageService
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
        
        # Génération d'un nom de blob unique pour le fichier normalisé
        normalized_blob_name = f"{analysis.user_id}/{analysis_id}/normalized.flac"
        
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
        Normalize audio using ffmpeg with streaming I/O to minimize memory usage.
        Converts audio to FLAC 16kHz mono 16-bit format.
        """
        # Define ffmpeg command
        ffmpeg_command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            "pipe:0",
            "-f",
            "flac",
            "-acodec",
            "flac",
            "-ar",
            "16000",
            "-ac",
            "1",
            "-sample_fmt",
            "s16",
            "-",
        ]
        
        # Create subprocess
        process = await asyncio.create_subprocess_exec(
            *ffmpeg_command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        async def writer():
            """Download source blob and write chunks to ffmpeg stdin"""
            try:
                async for chunk in self.blob_storage_service.download_blob_as_stream(source_blob_name):
                    process.stdin.write(chunk)
                    await process.stdin.drain()
                # Signal end of input to ffmpeg
                try:
                    process.stdin.close()
                    if hasattr(process.stdin, "wait_closed"):
                        await process.stdin.wait_closed()
                except Exception:
                    pass
            except Exception as e:
                logging.error("Error in writer coroutine: %s", e)
                try:
                    process.stdin.close()
                    if hasattr(process.stdin, "wait_closed"):
                        await process.stdin.wait_closed()
                except Exception:
                    pass
                raise
        
        async def uploader():
            """Read ffmpeg stdout and upload chunks to normalized blob"""
            async def stdout_generator():
                # Read raw binary from stdout in fixed-size chunks
                # Using read() avoids newline-delimited iteration which corrupts binary streams
                CHUNK_SIZE_BYTES = 64 * 1024
                while True:
                    try:
                        chunk = await process.stdout.read(CHUNK_SIZE_BYTES)
                    except Exception as e:
                        logging.error("Error reading from ffmpeg stdout: %s", e)
                        raise
                    if not chunk:
                        break
                    yield chunk
            
            await self.blob_storage_service.upload_blob_from_generator(
                stdout_generator(), normalized_blob_name
            )
        
        # Execute both coroutines simultaneously
        await asyncio.gather(writer(), uploader())
        
        # Wait for process completion and check return code
        return_code = await process.wait()
        
        if return_code != 0:
            # Read stderr for error details
            stderr_data = await process.stderr.read()
            error_message = stderr_data.decode('utf-8') if stderr_data else "Unknown ffmpeg error"
            logging.error("FFmpeg failed with return code %d: %s", return_code, error_message)
            raise FFmpegError(f"FFmpeg normalization failed: {error_message}")
