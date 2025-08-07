from __future__ import annotations

import io
import logging
import uuid
from datetime import timedelta

from pydub import AudioSegment

from src.infrastructure.database import async_session_factory
from src.infrastructure.repositories.analysis_repository import AnalysisRepository
from src.infrastructure.sql_models import AnalysisStatus
from src.services.blob_storage_service import BlobStorageService
from src.services.external_apis.azure_speech_client import AzureSpeechClient
from src.services.external_apis.litellm_ai_processor import LiteLLMAIProcessor
from src.services import pipeline_prompts


async def start_transcription_task(ctx, analysis_id: str, file_content: bytes, filename: str, blob_name: str) -> None:
    if not isinstance(file_content, (bytes, bytearray)) or len(file_content) == 0:
        raise ValueError("Invalid file_content provided")
    if not filename or not isinstance(filename, str):
        raise ValueError("Invalid filename provided")
    if not blob_name or not isinstance(blob_name, str):
        raise ValueError("Invalid blob_name provided")

    async with async_session_factory() as db:
        analysis_repo = AnalysisRepository(db)
        blob_storage = BlobStorageService()
        speech_client = AzureSpeechClient()

        # Normalize audio to FLAC 16kHz mono 16-bit
        audio = AudioSegment.from_file(io.BytesIO(file_content))
        normalized_audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
        buf = io.BytesIO()
        normalized_audio.export(buf, format="flac")
        buf.seek(0)
        normalized_bytes = buf.read()

        try:
            # Upload normalized audio, submit transcription
            await analysis_repo.update_status(analysis_id, AnalysisStatus.TRANSCRIPTION_IN_PROGRESS)
            await blob_storage.upload_blob(normalized_bytes, blob_name)
            audio_sas_url = await blob_storage.get_blob_sas_url(blob_name)
            status_url = await speech_client.submit_batch_transcription(audio_sas_url, filename)
            analysis = await analysis_repo.get_by_id(analysis_id)
            if analysis:
                analysis.transcription_job_url = status_url
                await db.commit()

            # Schedule status check in 30 seconds
            await ctx["redis"].enqueue_job("check_transcription_status_task", analysis_id, _defer_by=timedelta(seconds=30))
        except Exception as e:
            error_details = f"Transcription submission failed. Error type: {type(e).__name__}. Details: {e}"
            logging.error(error_details)
            await analysis_repo.update_status(analysis_id, AnalysisStatus.TRANSCRIPTION_FAILED)
            analysis = await analysis_repo.get_by_id(analysis_id)
            if analysis:
                analysis.error_message = error_details
                await db.commit()
            raise


async def check_transcription_status_task(ctx, analysis_id: str) -> None:
    async with async_session_factory() as db:
        analysis_repo = AnalysisRepository(db)
        blob_storage = BlobStorageService()
        speech_client = AzureSpeechClient()

        analysis = await analysis_repo.get_by_id(analysis_id)
        if not analysis:
            raise ValueError(f"Analysis not found: {analysis_id}")
        if analysis.status != AnalysisStatus.TRANSCRIPTION_IN_PROGRESS:
            return
        if not analysis.transcription_job_url:
            logging.warning("No transcription_job_url stored for analysis %s", analysis_id)
            return

        status_resp = await speech_client.check_transcription_status(analysis.transcription_job_url)
        status = str(status_resp.get("status") or status_resp.get("statusCode")).lower()
        if status == "succeeded":
            files_response = await speech_client.get_transcription_files(analysis.transcription_job_url)
            full_text = await speech_client.get_transcription_result(files_response)
            transcript_blob_name = f"{analysis_id}/transcription.txt"
            await blob_storage.upload_blob(full_text, transcript_blob_name)
            await analysis_repo.update_paths_and_status(
                analysis_id,
                status=AnalysisStatus.ANALYSIS_PENDING,
                transcript_blob_name=transcript_blob_name,
            )
            await ctx["redis"].enqueue_job("run_ai_analysis_task", analysis_id)
        elif status == "failed":
            logging.error(f"Azure transcription failed. Full response: {status_resp}")
            await analysis_repo.update_status(analysis_id, AnalysisStatus.TRANSCRIPTION_FAILED)
        else:
            await ctx["redis"].enqueue_job("check_transcription_status_task", analysis_id, _defer_by=timedelta(seconds=30))


async def run_ai_analysis_task(ctx, analysis_id: str) -> None:
    async with async_session_factory() as db:
        analysis_repo = AnalysisRepository(db)
        blob_storage = BlobStorageService()
        ai_analyzer = LiteLLMAIProcessor()

        analysis = await analysis_repo.get_by_id(analysis_id)
        if not analysis:
            raise ValueError(f"Analysis not found: {analysis_id}")
        if not getattr(analysis, "transcript_blob_name", None):
            raise FileNotFoundError("Transcript blob not found for analysis")

        transcript = await blob_storage.download_blob_as_text(analysis.transcript_blob_name)

        try:
            await analysis_repo.update_status(analysis_id, AnalysisStatus.ANALYSIS_IN_PROGRESS)

            # Execute pipeline steps
            intervenants_md = await ai_analyzer.execute_prompt(
                system_prompt=pipeline_prompts.PROMPT_INTERVENANTS,
                user_content=transcript,
            )
            prompt_odj = pipeline_prompts.PROMPT_ORDRE_DU_JOUR.format(intervenants=intervenants_md)
            ordre_du_jour_md = await ai_analyzer.execute_prompt(
                system_prompt=prompt_odj,
                user_content=transcript,
            )
            prompt_synthese = pipeline_prompts.PROMPT_SYNTHESE.format(
                intervenants=intervenants_md,
                ordre_du_jour=ordre_du_jour_md,
            )
            synthese_md = await ai_analyzer.execute_prompt(
                system_prompt=prompt_synthese,
                user_content=transcript,
            )
            prompt_decisions = pipeline_prompts.PROMPT_DECISIONS.format(
                intervenants=intervenants_md,
                synthese=synthese_md,
            )
            decisions_md = await ai_analyzer.execute_prompt(
                system_prompt=prompt_decisions,
                user_content=transcript,
            )

            final_report_content = (
                "# Procès-Verbal de Réunion\n\n"
                "## Intervenants\n" + intervenants_md.strip() + "\n\n"
                "## Ordre du jour\n" + ordre_du_jour_md.strip() + "\n\n"
                "## Synthèse des échanges\n" + synthese_md.strip() + "\n\n"
                "## Relevé de décisions et d'actions\n" + decisions_md.strip() + "\n"
            )

            report_blob_name = f"{analysis_id}/versions/{str(uuid.uuid4())}/report.md"
            await blob_storage.upload_blob(final_report_content, report_blob_name)
            await analysis_repo.add_version(
                analysis_id=analysis_id,
                prompt_used=analysis.prompt or "",
                result_blob_name=report_blob_name,
                people_involved=None,
                structured_plan=None,
            )
            await analysis_repo.update_paths_and_status(analysis_id, status=AnalysisStatus.COMPLETED, result_blob_name=report_blob_name)
            await analysis_repo.update_progress(analysis_id, 100)
        except Exception as e:
            error_details = f"AI analysis failed. Error type: {type(e).__name__}. Details: {e}"
            logging.error(error_details)
            await analysis_repo.update_status(analysis_id, AnalysisStatus.ANALYSIS_FAILED)
            analysis = await analysis_repo.get_by_id(analysis_id)
            if analysis:
                analysis.error_message = error_details
                await db.commit()
            raise


async def delete_analysis_task(ctx, analysis_id: str, user_id: int) -> None:
    async with async_session_factory() as db:
        analysis_repo = AnalysisRepository(db)
        blob_storage = BlobStorageService()

        analysis = await analysis_repo.get_detailed_by_id(analysis_id)
        if not analysis:
            raise ValueError(f"Analysis not found: {analysis_id}")
        if analysis.user_id != user_id:
            raise PermissionError("Access denied")

        blob_names = []
        if getattr(analysis, "source_blob_name", None):
            blob_names.append(analysis.source_blob_name)
        if getattr(analysis, "transcript_blob_name", None):
            blob_names.append(analysis.transcript_blob_name)
        for v in getattr(analysis, "versions", []) or []:
            if getattr(v, "result_blob_name", None):
                blob_names.append(v.result_blob_name)

        for name in blob_names:
            try:
                await blob_storage.delete_blob(name)
            except Exception as e:
                logging.warning(f"Failed to delete blob '{name}' for analysis {analysis_id}: {e}")

        await analysis_repo.delete(analysis_id)
