import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from ..infrastructure.repositories.analysis_repository import AnalysisRepository
from ..infrastructure.sql_models import (
    AnalysisStatus,
    AnalysisStepStatus,
    AnalysisStepResult,
    PromptStep,
)
from ..infrastructure import sql_models as models
from .blob_storage_service import BlobStorageService
from typing import Protocol


class AIAnalyzer(Protocol):
    async def execute_prompt(self, system_prompt: str, user_content: str) -> str:
        ...


class AIPipelineService:
    def __init__(
        self,
        analysis_repo: AnalysisRepository,
        blob_storage_service: BlobStorageService,
        ai_analyzer: AIAnalyzer,
    ) -> None:
        self.analysis_repo = analysis_repo
        self.blob_storage_service = blob_storage_service
        self.ai_analyzer = ai_analyzer

    async def _execute_step(self, step: PromptStep, sr: AnalysisStepResult, transcript: str, flow_context: dict) -> None:
        """
        Execute a single AI analysis step.
        
        Args:
            step: The PromptStep object
            sr: The AnalysisStepResult object
            transcript: The transcript string
            flow_context: The context dictionary
        """
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
        finally:
            await self.analysis_repo.db.commit()

    async def run_pipeline(self, analysis_id: str) -> None:
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

                # Execute the AI step using the new private method
                await self._execute_step(step, sr, transcript, flow_context)

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

    async def rerun_step(self, step_result_id: str, new_prompt_content: Optional[str] = None) -> None:
        """
        Relance une seule étape de l'analyse IA.
        """
        # Récupérer le step_result avec tout le contexte nécessaire
        step_result = await self.analysis_repo.get_step_result_with_full_context(step_result_id)
        if not step_result:
            raise ValueError("Step result not found")
        
        # Vérifier les permissions
        version = step_result.version
        analysis = version.analysis_record
        if not analysis:
            raise PermissionError("Access denied")
        
        # Récupérer la transcription originale
        if not getattr(analysis, "transcript_blob_name", None):
            raise FileNotFoundError("Transcript not found")
        
        transcript = await self.blob_storage_service.download_blob_as_text(analysis.transcript_blob_name)
        if not isinstance(transcript, str) or not transcript.strip():
            raise ValueError("Transcript is empty or invalid")
        
        # Trouver le step original
        prompt_flow = analysis.prompt_flow
        if not prompt_flow or not getattr(prompt_flow, "steps", None):
            raise ValueError("No prompt flow configured for this analysis")
        
        step = None
        for s in prompt_flow.steps:
            if s.name == step_result.step_name:
                step = s
                break
        
        if not step:
            raise ValueError(f"Step '{step_result.step_name}' not found in prompt flow")
        
        # Si un nouveau prompt est fourni, on le met à jour temporairement
        original_content = step.content
        if new_prompt_content:
            step.content = new_prompt_content
        
        try:
            # Construire le contexte pour cette étape
            flow_context: dict[str, str] = {
                "transcript": transcript,
                "analysis_id": analysis.id,
                "flow_name": prompt_flow.name,
            }
            
            # Exécuter l'étape en utilisant la méthode partagée
            await self._execute_step(step, step_result, transcript, flow_context)
        finally:
            # Restaurer le contenu original du step
            if new_prompt_content:
                step.content = original_content