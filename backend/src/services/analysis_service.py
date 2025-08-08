import logging
import os
import tempfile
from typing import Protocol
from pydub import AudioSegment
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from ..infrastructure.repositories.analysis_repository import AnalysisRepository
from .external_apis.litellm_ai_processor import LiteLLMAIProcessor
from ..infrastructure.sql_models import AnalysisStatus
from ..infrastructure import sql_models as models
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
        # Load analysis with associated prompt flow and steps
        stmt = (
            select(models.Analysis)
            .options(
                joinedload(models.Analysis.prompt_flow).joinedload(models.PromptFlow.steps)
            )
            .where(models.Analysis.id == analysis_id)
        )
        result = await self.analysis_repo.db.execute(stmt)
        analysis = result.unique().scalar_one_or_none()
        if not analysis:
            raise ValueError(f"Analysis not found: {analysis_id}")
        if not getattr(analysis, "transcript_blob_name", None):
            raise FileNotFoundError("Transcript blob not found for analysis")

        # If using a predefined (legacy) prompt, run single-step analysis path
        if (pf_id := getattr(analysis, "prompt_flow_id", None)) and str(pf_id).startswith("predefined_"):
            from ..services.prompts import PREDEFINED_PROMPTS

            # Load transcript
            transcript = await self.blob_storage_service.download_blob_as_text(analysis.transcript_blob_name)
            if not isinstance(transcript, str) or not transcript.strip():
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

                # Extract legacy prompt name from id and fetch content
                legacy_name_key = str(pf_id).removeprefix("predefined_").replace("_", " ")
                prompt_content = PREDEFINED_PROMPTS.get(legacy_name_key)
                if not prompt_content:
                    raise ValueError(f"Unknown predefined prompt: {legacy_name_key}")

                # Execute single-step prompt
                result_text = await self.ai_analyzer.execute_prompt(
                    system_prompt=prompt_content,
                    user_content=transcript,
                )

                final_report_content = f"# Rapport d'analyse\n\n## {legacy_name_key}\n\n{result_text}\n"

                transcript_snippet = transcript[:200]
                analysis_snippet = final_report_content[:200]

                report_blob_name = f"{analysis_id}/versions/{str(uuid.uuid4())}/report.md"
                await self.blob_storage_service.upload_blob(final_report_content, report_blob_name)
                await self.analysis_repo.add_version(
                    analysis_id=analysis_id,
                    prompt_used=legacy_name_key,
                    result_blob_name=report_blob_name,
                    people_involved=None,
                    structured_plan=None,
                )
                await self.analysis_repo.update_paths_and_status(
                    analysis_id,
                    status=AnalysisStatus.COMPLETED,
                    result_blob_name=report_blob_name,
                    transcript_snippet=transcript_snippet,
                    analysis_snippet=analysis_snippet,
                )
                await self.analysis_repo.update_progress(analysis_id, 100)
                return
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

        # Resolve prompt flow
        prompt_flow = getattr(analysis, "prompt_flow", None)
        if not prompt_flow or not getattr(prompt_flow, "steps", None):
            raise ValueError("No prompt flow configured for this analysis")

        # Ensure steps are ordered
        ordered_steps = sorted(prompt_flow.steps, key=lambda s: int(getattr(s, "step_order", 0)))

        # Load transcript content
        transcript = await self.blob_storage_service.download_blob_as_text(analysis.transcript_blob_name)
        if not isinstance(transcript, str) or not transcript.strip():
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

            # Create an analysis version for this run
            version = await self.analysis_repo.add_version(
                analysis_id=analysis_id,
                prompt_used=getattr(prompt_flow, "name", ""),
                result_blob_name=None,
                people_involved=None,
                structured_plan=None,
            )

            # Pre-create step result rows with PENDING status
            from ..infrastructure.sql_models import AnalysisStepResult, AnalysisStepStatus
            step_results_index: dict[int, AnalysisStepResult] = {}
            for step in ordered_steps:
                sr = AnalysisStepResult(
                    analysis_version_id=version.id,
                    step_name=step.name,
                    step_order=int(getattr(step, "step_order", 0)),
                    status=AnalysisStepStatus.PENDING,
                    content=None,
                )
                self.analysis_repo.db.add(sr)
                step_results_index[sr.step_order] = sr
            await self.analysis_repo.db.commit()
            # Refresh to obtain IDs
            for sr in step_results_index.values():
                await self.analysis_repo.db.refresh(sr)

            # Shared context across steps
            flow_context: dict[str, str] = {
                "transcript": transcript,
                "analysis_id": analysis_id,
                "flow_name": prompt_flow.name,
            }

            # Execute each step and update its result progressively
            for step in ordered_steps:
                order = int(getattr(step, "step_order", 0))
                sr = step_results_index.get(order)
                if not sr:
                    continue

                # Mark IN_PROGRESS
                sr.status = AnalysisStepStatus.IN_PROGRESS
                await self.analysis_repo.db.commit()

                # Prepare system prompt
                try:
                    system_prompt = (step.content or "").format(**flow_context)
                except Exception:
                    system_prompt = step.content or ""

                # Execute
                try:
                    result_text = await self.ai_analyzer.execute_prompt(
                        system_prompt=system_prompt,
                        user_content=transcript,
                    )
                    sr.content = result_text
                    sr.status = AnalysisStepStatus.COMPLETED
                    flow_context[step.name] = result_text
                except Exception as e:
                    sr.content = f"Step failed: {e}"
                    sr.status = AnalysisStepStatus.FAILED
                    # Still continue to process next steps or break? Choose continue for resilience
                finally:
                    await self.analysis_repo.db.commit()

            # Finally, mark analysis as COMPLETED
            await self.analysis_repo.update_status(analysis_id, AnalysisStatus.COMPLETED)
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

    async def overwrite_transcript_content(self, analysis_id: str, user_id: int, content: str) -> None:
        analysis = await self.analysis_repo.get_by_id(analysis_id)
        if not analysis:
            raise AnalysisNotFoundException("Analysis not found")
        if analysis.user_id != user_id:
            raise PermissionError("Access denied")
        if not getattr(analysis, "transcript_blob_name", None):
            raise FileNotFoundError("Transcript not found")

        # Overwrite transcript blob
        await self.blob_storage_service.upload_blob(content, analysis.transcript_blob_name)
        # Update snippet
        snippet = (content or "")[:200]
        await self.analysis_repo.update_paths_and_status(
            analysis_id,
            transcript_snippet=snippet,
        )

    async def update_step_result_content(self, step_result_id: str, user_id: int, content: str) -> None:
        # Ensure the step result belongs to the requesting user via version -> analysis
        from ..infrastructure import sql_models as models
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload

        stmt = (
            select(models.AnalysisStepResult)
            .options(joinedload(models.AnalysisStepResult.version).joinedload(models.AnalysisVersion.analysis_record))
            .where(models.AnalysisStepResult.id == step_result_id)
        )
        result = await self.analysis_repo.db.execute(stmt)
        step_result = result.unique().scalar_one_or_none()
        if not step_result:
            raise ValueError("Step result not found")

        version = getattr(step_result, "version", None)
        analysis = getattr(version, "analysis_record", None)
        if not analysis or analysis.user_id != user_id:
            raise PermissionError("Access denied")

        step_result.content = content
        try:
            await self.analysis_repo.db.commit()
        except Exception:
            pass
