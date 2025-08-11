from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional
import json

from src.infrastructure.sql_models import AnalysisStatus
from src.worker.dependencies import get_analysis_service_provider


async def _publish_status(redis, analysis_id: str, status: str, error_message: Optional[str] = None):
    channel = f"analysis:{analysis_id}:updates"
    message = {"status": status}
    if error_message:
        message["error_message"] = error_message
    await redis.publish(channel, json.dumps(message))


async def start_transcription_task(ctx, analysis_id: str) -> None:
    async with get_analysis_service_provider(ctx) as service:
        try:
            await service.process_audio_for_transcription(analysis_id)
            # Publish status update
            await _publish_status(ctx["redis"], analysis_id, AnalysisStatus.TRANSCRIPTION_IN_PROGRESS.value)
            # Schedule status check in 30 seconds
            await ctx["redis"].enqueue_job("check_transcription_status_task", analysis_id, _defer_by=timedelta(seconds=30))
        except Exception as e:
            error_details = f"Transcription submission failed. Error type: {type(e).__name__}. Details: {e}"
            logging.error(error_details)
            await service.analysis_repo.update_status(analysis_id, AnalysisStatus.TRANSCRIPTION_FAILED)
            analysis = await service.analysis_repo.get_by_id(analysis_id)
            if analysis:
                analysis.error_message = error_details
                await service.analysis_repo.db.commit()
                # Publish status update with error
                await _publish_status(ctx["redis"], analysis_id, AnalysisStatus.TRANSCRIPTION_FAILED.value, error_details)
            raise


async def check_transcription_status_task(ctx, analysis_id: str) -> None:
    async with get_analysis_service_provider(ctx) as service:
        status, status_resp = await service.check_transcription_status(analysis_id)
        if status == "succeeded":
            await ctx["redis"].enqueue_job("run_ai_analysis_task", analysis_id)
            # Publish status update
            await _publish_status(ctx["redis"], analysis_id, AnalysisStatus.ANALYSIS_PENDING.value)
        elif status == "failed":
            # Extract detailed error from Azure response if available
            azure_error = (status_resp or {}).get("properties", {}).get("error", {})
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
                formatted_error = "; ".join(error_str_parts) if error_str_parts else str(azure_error)
            else:
                formatted_error = "Transcription failed with unknown Azure error format"

            # Log full response for debugging
            logging.error("Transcription failed for analysis %s. Full Azure response: %s", analysis_id, status_resp)

            # Update status and persist error message
            await service.analysis_repo.update_status(analysis_id, AnalysisStatus.TRANSCRIPTION_FAILED)
            analysis = await service.analysis_repo.get_by_id(analysis_id)
            if analysis:
                analysis.error_message = formatted_error
                await service.analysis_repo.db.commit()
                # Publish status update with error
                await _publish_status(ctx["redis"], analysis_id, AnalysisStatus.TRANSCRIPTION_FAILED.value, formatted_error)
        else:
            await ctx["redis"].enqueue_job("check_transcription_status_task", analysis_id, _defer_by=timedelta(seconds=30))


async def run_ai_analysis_task(ctx, analysis_id: str) -> None:
    async with get_analysis_service_provider(ctx) as service:
        try:
            # Publish status update before starting analysis
            await _publish_status(ctx["redis"], analysis_id, AnalysisStatus.ANALYSIS_IN_PROGRESS.value)
            await service.run_ai_analysis_pipeline(analysis_id)
            # Publish status update when completed
            await _publish_status(ctx["redis"], analysis_id, AnalysisStatus.COMPLETED.value)
        except ValueError as e:
            if "No prompt flow configured" in str(e):
                # Handle the specific "No prompt flow configured" error
                logging.error("AI analysis failed for analysis %s: %s", analysis_id, str(e))
                
                # Update analysis status to ANALYSIS_FAILED
                await service.analysis_repo.update_status(analysis_id, AnalysisStatus.ANALYSIS_FAILED)
                
                # Get the analysis object and set the error message
                analysis = await service.analysis_repo.get_by_id(analysis_id)
                if analysis:
                    analysis.error_message = str(e)
                    await service.analysis_repo.db.commit()
                    # Publish status update with error
                    await _publish_status(ctx["redis"], analysis_id, AnalysisStatus.ANALYSIS_FAILED.value, str(e))
            else:
                # Re-raise other ValueError exceptions
                raise
        except Exception as e:
            error_details = f"AI analysis failed. Error type: {type(e).__name__}. Details: {e}"
            logging.error(error_details)
            # Publish status update with error
            await _publish_status(ctx["redis"], analysis_id, AnalysisStatus.ANALYSIS_FAILED.value, error_details)
            # Error handling and status updates are managed inside the service; re-raise to let ARQ handle retries/logging
            raise


async def delete_analysis_task(ctx, analysis_id: str, user_id: int) -> None:
    async with get_analysis_service_provider(ctx) as service:
        try:
            await service.delete_analysis_data(analysis_id, user_id)
        except Exception as e:
            logging.error("Unexpected error while deleting analysis %s: %s", analysis_id, e)
            raise


async def rerun_ai_analysis_step_task(ctx, step_result_id: str, new_prompt_content: Optional[str] = None) -> None:
    async with get_analysis_service_provider(ctx) as service:
        try:
            await service.rerun_ai_analysis_step(step_result_id, new_prompt_content)
        except Exception:
            # Error handling and status updates are managed inside the service; re-raise to let ARQ handle retries/logging
            raise