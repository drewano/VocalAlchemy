import logging

from ..infrastructure.repositories.analysis_repository import AnalysisRepository
from ..infrastructure.sql_models import AnalysisStatus
from .blob_storage_service import BlobStorageService
from .audio_processing_service import AudioProcessingService
from .transcription_orchestrator_service import TranscriptionOrchestratorService
from .ai_pipeline_service import AIPipelineService


class AnalysisNotFoundException(Exception):
    pass


class AnalysisService:
    def __init__(
        self,
        analysis_repo: AnalysisRepository,
        *,
        audio_processing_service: AudioProcessingService,
        transcription_orchestrator_service: TranscriptionOrchestratorService,
        ai_pipeline_service: AIPipelineService,
        blob_storage_service: BlobStorageService,
    ) -> None:
        self.analysis_repo = analysis_repo
        self.audio_processing_service = audio_processing_service
        self.transcription_orchestrator_service = transcription_orchestrator_service
        self.ai_pipeline_service = ai_pipeline_service
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
        return await self.blob_storage_service.download_blob_as_text(
            analysis.result_blob_name
        )

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
        return await self.blob_storage_service.download_blob_as_text(
            analysis.transcript_blob_name
        )

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
        return await self.blob_storage_service.download_blob_as_text(
            version.result_blob_name
        )

    async def process_audio_for_transcription(self, analysis_id: str) -> None:
        # Récupération de l'objet analysis
        analysis = await self.analysis_repo.get_by_id(analysis_id)
        if not analysis:
            raise ValueError(f"Analysis not found: {analysis_id}")

        # Mise à jour du statut à TRANSCRIPTION_IN_PROGRESS
        await self.analysis_repo.update_status(
            analysis_id, AnalysisStatus.TRANSCRIPTION_IN_PROGRESS
        )

        # Génération d'un nom de blob unique pour le fichier normalisé (WAV PCM 16k mono)
        normalized_blob_name = f"{analysis.user_id}/{analysis_id}/normalized.wav"

        # Normalisation audio en streaming avec ffmpeg (FLAC 16kHz mono 16-bit)
        try:
            await self.audio_processing_service.normalize_audio(
                analysis.source_blob_name, normalized_blob_name
            )
        except FFmpegError as e:
            logging.error(
                "Audio normalization failed for analysis %s: %s", analysis_id, e
            )
            await self.analysis_repo.update_status(
                analysis_id, AnalysisStatus.TRANSCRIPTION_FAILED
            )
            analysis.error_message = str(e)
            try:
                await self.analysis_repo.db.commit()
            except Exception:
                pass
            raise

        # Submit transcription using the new orchestrator service
        await self.transcription_orchestrator_service.submit_transcription(
            analysis.id, normalized_blob_name
        )

    async def check_transcription_status(self, analysis_id: str) -> tuple[str, dict]:
        analysis = await self.analysis_repo.get_by_id(analysis_id)
        if not analysis:
            raise ValueError(f"Analysis not found: {analysis_id}")

        # Use the new orchestrator service to check and finalize transcription
        return await self.transcription_orchestrator_service.check_and_finalize_transcription(
            analysis_id
        )

    async def run_ai_analysis_pipeline(self, analysis_id: str) -> None:
        # Use the new AI pipeline service to run the analysis
        await self.ai_pipeline_service.run_pipeline(analysis_id)

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
                logging.warning(
                    f"Failed to delete blob '{name}' for analysis {analysis_id}: {e}"
                )

        await self.analysis_repo.delete(analysis_id)

    async def overwrite_transcript_content(
        self, analysis_id: str, user_id: int, content: str
    ) -> None:
        analysis = await self.analysis_repo.get_by_id(analysis_id)
        if not analysis:
            raise AnalysisNotFoundException("Analysis not found")
        if analysis.user_id != user_id:
            raise PermissionError("Access denied")
        if not getattr(analysis, "transcript_blob_name", None):
            raise FileNotFoundError("Transcript not found")

        # Overwrite transcript blob
        await self.blob_storage_service.upload_blob(
            content, analysis.transcript_blob_name
        )
        # Update snippet
        snippet = (content or "")[:200]
        await self.analysis_repo.update_paths_and_status(
            analysis_id,
            transcript_snippet=snippet,
        )

    async def update_step_result_content(
        self, step_result_id: str, user_id: int, content: str
    ) -> None:
        # Ensure the step result belongs to the requesting user via version -> analysis
        step_result = await self.analysis_repo.get_step_result_with_analysis_owner(
            step_result_id
        )
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

    async def rerun_transcription(self, analysis_id: str, user_id: int) -> None:
        """
        Relance uniquement la transcription d'une analyse.
        """
        # Vérifier que l'analyse existe et appartient à l'utilisateur
        analysis = await self.analysis_repo.get_by_id(analysis_id)
        if not analysis:
            raise AnalysisNotFoundException("Analysis not found")
        if analysis.user_id != user_id:
            raise PermissionError("Access denied")

        # Mettre à jour le statut à TRANSCRIPTION_PENDING
        await self.analysis_repo.update_status(
            analysis_id, AnalysisStatus.TRANSCRIPTION_PENDING
        )

        # Enfiler la tâche de transcription
        # Note: L'enfilement de la tâche se fait dans la couche API/worker, pas dans le service

    async def rerun_ai_analysis_step(
        self, step_result_id: str, new_prompt_content: str = None
    ) -> None:
        """
        Relance une seule étape de l'analyse IA.
        """
        # Use the new AI pipeline service to rerun the step
        await self.ai_pipeline_service.rerun_step(step_result_id, new_prompt_content)

    async def get_detailed_analysis_dto(self, analysis_id: str, user_id: int):
        """
        Récupère les détails d'une analyse et les retourne sous forme de DTO.
        """
        from src.api import schemas

        a = await self.analysis_repo.get_detailed_by_id(analysis_id)
        if not a:
            raise AnalysisNotFoundException("Analysis not found")
        if a.user_id != user_id:
            raise PermissionError("Access denied")

        # Sort versions by created_at desc
        versions_sorted = sorted(
            a.versions or [], key=lambda v: v.created_at or 0, reverse=True
        )

        # Read transcript content
        transcript_content = ""
        if getattr(a, "transcript_blob_name", None):
            try:
                transcript_content = (
                    await self.blob_storage_service.download_blob_as_text(
                        a.transcript_blob_name
                    )
                )
            except Exception:
                transcript_content = ""

        # Latest analysis content and people involved (keep compatibility)
        latest_analysis_content = ""
        people_involved = None
        action_plan = None
        if versions_sorted:
            latest_version = versions_sorted[0]
            if getattr(latest_version, "result_blob_name", None):
                try:
                    latest_analysis_content = (
                        await self.blob_storage_service.download_blob_as_text(
                            latest_version.result_blob_name
                        )
                    )
                except Exception:
                    latest_analysis_content = ""
            people_involved = latest_version.people_involved
            try:
                if latest_version.structured_plan is not None:
                    if (
                        isinstance(latest_version.structured_plan, dict)
                        and "extractions" in latest_version.structured_plan
                    ):
                        action_plan = latest_version.structured_plan.get("extractions")
                    elif isinstance(latest_version.structured_plan, list):
                        action_plan = latest_version.structured_plan
                    else:
                        action_plan = latest_version.structured_plan
            except Exception:
                action_plan = None

        return schemas.AnalysisDetail(
            id=a.id,
            status=a.status,
            created_at=a.created_at,
            filename=a.filename,
            prompt=None,
            transcript=transcript_content,
            latest_analysis=latest_analysis_content or "",
            people_involved=people_involved,
            action_plan=action_plan,
            error_message=a.error_message,
            versions=[
                schemas.AnalysisVersion(
                    id=v.id,
                    prompt_used=v.prompt_used,
                    created_at=v.created_at,
                    people_involved=v.people_involved,
                    steps=[
                        schemas.AnalysisStepResult(
                            id=sr.id,
                            step_name=sr.step_name,
                            step_order=sr.step_order,
                            status=str(sr.status.value)
                            if hasattr(sr.status, "value")
                            else str(sr.status),
                            content=sr.content,
                        )
                        for sr in (v.steps or [])
                    ],
                )
                for v in versions_sorted
            ],
        )
