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
    async def execute_prompt(self, system_prompt: str, user_content: str) -> str: ...


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

    async def _execute_step(
        self,
        step: PromptStep,
        sr: AnalysisStepResult,
        transcript: str,
        flow_context: dict,
    ) -> None:
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

    async def setup_analysis_run(self, analysis_id: str) -> Optional[str]:
        """
        Setup an analysis run by creating version and pre-creating step results.

        Args:
            analysis_id: The ID of the analysis to setup

        Returns:
            The ID of the first AnalysisStepResult to execute, or None if no steps exist
        """
        # Load analysis with associated prompt flow and steps
        stmt = (
            select(models.Analysis)
            .options(
                joinedload(models.Analysis.prompt_flow).joinedload(
                    models.PromptFlow.steps
                )
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
        ordered_steps = sorted(
            prompt_flow.steps, key=lambda s: int(getattr(s, "step_order", 0))
        )

        # Update analysis status to ANALYSIS_IN_PROGRESS
        await self.analysis_repo.update_status(
            analysis_id, AnalysisStatus.ANALYSIS_IN_PROGRESS
        )

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

        # Find the first step (lowest step_order)
        if not step_results_index:
            return None

        first_step_order = min(step_results_index.keys())
        first_step_result = step_results_index[first_step_order]
        return first_step_result.id

    async def execute_step_by_id(self, step_result_id: str) -> None:
        """
        Execute a single analysis step by its ID.

        Args:
            step_result_id: The ID of the AnalysisStepResult to execute
        """
        # Récupérer le step_result avec tout le contexte nécessaire
        step_result = await self.analysis_repo.get_step_result_with_full_context(
            step_result_id
        )
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

        transcript = await self.blob_storage_service.download_blob_as_text(
            analysis.transcript_blob_name
        )
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

        # Construire le contexte pour cette étape
        flow_context: dict[str, str] = {
            "transcript": transcript,
            "analysis_id": analysis.id,
            "flow_name": prompt_flow.name,
        }

        # Ajouter les résultats des étapes précédentes déjà complétées
        for prev_step_result in version.steps:
            if (
                prev_step_result.status == AnalysisStepStatus.COMPLETED
                and prev_step_result.step_name != step_result.step_name
            ):
                flow_context[prev_step_result.step_name] = (
                    prev_step_result.content or ""
                )

        # Exécuter l'étape en utilisant la méthode partagée
        await self._execute_step(step, step_result, transcript, flow_context)

    async def find_next_step_or_finalize(
        self, completed_step_result_id: str
    ) -> Optional[str]:
        """
        Find the next pending step or finalize the analysis if all steps are completed.

        Args:
            completed_step_result_id: The ID of the completed AnalysisStepResult

        Returns:
            The ID of the next AnalysisStepResult to execute, or None if analysis is completed
        """
        # Récupérer le step_result complété
        completed_step_result = (
            await self.analysis_repo.get_step_result_with_full_context(
                completed_step_result_id
            )
        )
        if not completed_step_result:
            raise ValueError("Step result not found")

        # Récupérer la version avec toutes ses étapes
        version = completed_step_result.version
        analysis = version.analysis_record

        # Vérifier si toutes les étapes sont terminées
        all_completed = True
        next_step = None
        next_step_order = float("inf")

        for step_result in version.steps:
            if step_result.status == AnalysisStepStatus.FAILED:
                # Si une étape a échoué, on considère l'analyse comme échouée
                await self.analysis_repo.update_status(
                    analysis.id, AnalysisStatus.ANALYSIS_FAILED
                )
                analysis.error_message = f"Step '{step_result.step_name}' failed"
                try:
                    await self.analysis_repo.db.commit()
                except Exception:
                    pass
                return None
            elif step_result.status == AnalysisStepStatus.PENDING:
                all_completed = False
                # Trouver la prochaine étape avec le step_order immédiatement supérieur
                if (
                    step_result.step_order > completed_step_result.step_order
                    and step_result.step_order < next_step_order
                ):
                    next_step = step_result
                    next_step_order = step_result.step_order

        if all_completed:
            # Toutes les étapes sont terminées, finaliser l'analyse
            await self.analysis_repo.update_status(
                analysis.id, AnalysisStatus.COMPLETED
            )
            await self.analysis_repo.update_progress(analysis.id, 100)
            return None
        elif next_step:
            # Retourner l'ID de la prochaine étape
            return next_step.id
        else:
            # Aucune étape suivante trouvée mais pas toutes terminées - cas d'erreur
            return None

    async def rerun_step(
        self, step_result_id: str, new_prompt_content: Optional[str] = None
    ) -> None:
        """
        Relance une seule étape de l'analyse IA.
        """
        # Récupérer le step_result avec tout le contexte nécessaire
        step_result = await self.analysis_repo.get_step_result_with_full_context(
            step_result_id
        )
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

        transcript = await self.blob_storage_service.download_blob_as_text(
            analysis.transcript_blob_name
        )
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
