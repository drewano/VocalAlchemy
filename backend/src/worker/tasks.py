from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional
import json
from src.infrastructure.sql_models import AnalysisStatus
from src.worker.dependencies import (
    get_analysis_service_provider,
    get_analysis_repository_provider,
    get_transcription_orchestrator_provider,
)

# Default settings for tasks that can be retried
RETRY_SETTINGS = {
    "max_tries": 3,
}




async def _publish_status(
    redis, analysis_id: str, status: str, error_message: Optional[str] = None
):
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
            await _publish_status(
                ctx["redis"],
                analysis_id,
                AnalysisStatus.TRANSCRIPTION_IN_PROGRESS.value,
            )
            # Schedule status check in 30 seconds
            await ctx["redis"].enqueue_job(
                "check_transcription_status_task",
                analysis_id,
                _defer_by=timedelta(seconds=30),
            )
        except Exception as e:
            error_details = f"Transcription submission failed. Error type: {type(e).__name__}. Details: {e}"
            logging.error(error_details)
            await service.analysis_repo.update_status(
                analysis_id, AnalysisStatus.TRANSCRIPTION_FAILED
            )
            analysis = await service.analysis_repo.get_by_id(analysis_id)
            if analysis:
                analysis.error_message = error_details
                await service.analysis_repo.db.commit()
                # Publish status update with error
                await _publish_status(
                    ctx["redis"],
                    analysis_id,
                    AnalysisStatus.TRANSCRIPTION_FAILED.value,
                    error_details,
                )
            raise


async def check_transcription_status_task(ctx, analysis_id: str) -> None:
    async with get_transcription_orchestrator_provider(ctx) as service:
        try:
            status = await service.check_and_finalize_transcription(analysis_id)
            if status == "succeeded":
                await ctx["redis"].enqueue_job(
                    "setup_ai_analysis_pipeline_task", analysis_id
                )
                # Publish status update
                await _publish_status(
                    ctx["redis"], analysis_id, AnalysisStatus.ANALYSIS_PENDING.value
                )
            elif status == "failed":
                # Get the updated analysis record to retrieve the error message
                analysis = await service.analysis_repo.get_by_id(analysis_id)
                if analysis and analysis.error_message:
                    error_message = analysis.error_message
                else:
                    error_message = "Transcription failed with unknown error"
                
                # Log the failure
                logging.error(
                    "Transcription failed for analysis %s. Error: %s",
                    analysis_id,
                    error_message,
                )
                
                # Publish status update with error
                await _publish_status(
                    ctx["redis"],
                    analysis_id,
                    AnalysisStatus.TRANSCRIPTION_FAILED.value,
                    error_message,
                )
            else:  # status == "running"
                await ctx["redis"].enqueue_job(
                    "check_transcription_status_task",
                    analysis_id,
                    _defer_by=timedelta(seconds=30),
                )
        except ValueError as e:
            logging.error(
                "Échec de la vérification du statut de transcription pour %s: %s",
                analysis_id,
                e,
            )
            await _publish_status(
                ctx["redis"],
                analysis_id,
                AnalysisStatus.TRANSCRIPTION_FAILED.value,
                str(e),
            )
            raise


async def setup_ai_analysis_pipeline_task(ctx, analysis_id: str) -> None:
    async with get_analysis_service_provider(ctx) as service:
        try:
            logging.info(
                f"Initializing AI analysis pipeline for analysis_id: {analysis_id}"
            )
            # Publish status update before starting analysis
            await _publish_status(
                ctx["redis"], analysis_id, AnalysisStatus.ANALYSIS_IN_PROGRESS.value
            )

            # Setup the analysis run and get the first step ID
            first_step_id = await service.ai_pipeline_service.setup_analysis_run(
                analysis_id
            )

            # If there's a first step, enqueue it
            if first_step_id:
                await ctx["redis"].enqueue_job("run_single_ai_step_task", first_step_id)
                logging.info(
                    f"AI analysis pipeline initialized for analysis_id: {analysis_id}. First step enqueued: {first_step_id}"
                )
            else:
                # No steps to execute, mark analysis as completed
                await service.analysis_repo.update_status(
                    analysis_id, AnalysisStatus.COMPLETED
                )
                await service.analysis_repo.update_progress(analysis_id, 100)
                await _publish_status(
                    ctx["redis"], analysis_id, AnalysisStatus.COMPLETED.value
                )
                logging.info(
                    f"AI analysis pipeline completed for analysis_id: {analysis_id} (no steps to execute)"
                )
        except ValueError as e:
            if "No prompt flow configured" in str(e):
                # Handle the specific "No prompt flow configured" error
                logging.error(
                    "AI analysis failed for analysis %s: %s", analysis_id, str(e)
                )

                # Update analysis status to ANALYSIS_FAILED
                await service.analysis_repo.update_status(
                    analysis_id, AnalysisStatus.ANALYSIS_FAILED
                )

                # Get the analysis object and set the error message
                analysis = await service.analysis_repo.get_by_id(analysis_id)
                if analysis:
                    analysis.error_message = str(e)
                    await service.analysis_repo.db.commit()
                    # Publish status update with error
                    await _publish_status(
                        ctx["redis"],
                        analysis_id,
                        AnalysisStatus.ANALYSIS_FAILED.value,
                        str(e),
                    )
            else:
                # Re-raise other ValueError exceptions
                raise
        except Exception as e:
            error_details = (
                f"AI analysis failed. Error type: {type(e).__name__}. Details: {e}"
            )
            logging.error(error_details)
            # Publish status update with error
            await _publish_status(
                ctx["redis"],
                analysis_id,
                AnalysisStatus.ANALYSIS_FAILED.value,
                error_details,
            )
            # Error handling and status updates are managed inside the service; re-raise to let ARQ handle retries/logging
            raise


async def run_single_ai_step_task(ctx, step_result_id: str) -> None:
    async with get_analysis_service_provider(ctx) as service:
        try:
            logging.info(f"Executing AI step for step_result_id: {step_result_id}")

            # Execute the step
            await service.ai_pipeline_service.execute_step_by_id(step_result_id)

            # Find the next step or finalize
            next_step_id = await service.ai_pipeline_service.find_next_step_or_finalize(
                step_result_id
            )

            # If there's a next step, enqueue it
            if next_step_id:
                await ctx["redis"].enqueue_job("run_single_ai_step_task", next_step_id)
            else:
                logging.info(
                    f"AI analysis pipeline completed for analysis associated with step {step_result_id}"
                )

            logging.info(
                f"Successfully executed AI step for step_result_id: {step_result_id}"
            )
        except Exception as e:
            error_details = f"AI step execution failed for step_result_id {step_result_id}. Error type: {type(e).__name__}. Details: {e}"
            logging.error(error_details)
            # Error handling and status updates are managed inside the service; re-raise to let ARQ handle retries/logging
            raise


async def delete_analysis_task(ctx, analysis_id: str, user_id: int) -> None:
    async with get_analysis_service_provider(ctx) as service:
        try:
            await service.delete_analysis_data(analysis_id, user_id)
        except Exception as e:
            logging.error(
                "Unexpected error while deleting analysis %s: %s", analysis_id, e
            )
            raise


async def rerun_ai_analysis_step_task(
    ctx, step_result_id: str, new_prompt_content: Optional[str] = None
) -> None:
    async with get_analysis_service_provider(ctx) as service:
        try:
            await service.rerun_ai_analysis_step(step_result_id, new_prompt_content)
        except Exception:
            # Error handling and status updates are managed inside the service; re-raise to let ARQ handle retries/logging
            raise


async def check_stale_transcriptions_task(ctx) -> None:
    """Vérifie et nettoie les analyses dont la transcription est bloquée depuis trop longtemps."""
    async with get_analysis_repository_provider(ctx) as repo:
        # Définir le seuil de timeout (2 heures)
        timeout = timedelta(hours=2)
        
        # Trouver les analyses bloquées
        stale_analyses = await repo.find_stale_in_progress_analyses(timeout_delta=timeout)
        
        # Itérer sur chaque analyse bloquée
        for analysis in stale_analyses:
            # Loguer un message d'avertissement
            logging.warning(f"Analyse {analysis.id} bloquée en transcription. Marquage comme échouée.")
            
            # Définir le message d'erreur
            error_message = "La transcription a dépassé le délai maximum et a été annulée."
            
            # Mettre à jour le statut de l'analyse
            await repo.update_status(analysis.id, AnalysisStatus.TRANSCRIPTION_FAILED)
            
            # Mettre à jour le message d'erreur et commiter
            analysis.error_message = error_message
            await repo.db.commit()
            
            # Notifier le front-end de l'échec
            await _publish_status(
                ctx["redis"], 
                analysis.id, 
                AnalysisStatus.TRANSCRIPTION_FAILED.value, 
                error_message
            )