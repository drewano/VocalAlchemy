from typing import List, Optional
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload, selectinload
from .base_repository import BaseRepository
from .. import sql_models as models


class AnalysisRepository(BaseRepository):
    async def create(self, user_id: int, filename: str, status: models.AnalysisStatus = models.AnalysisStatus.PENDING, source_blob_name: str = "") -> models.Analysis:
        analysis = models.Analysis(
            user_id=user_id,
            filename=filename,
            status=status,
            source_blob_name=source_blob_name,
        )
        self.db.add(analysis)
        await self.db.commit()
        await self.db.refresh(analysis)
        return analysis

    async def update_filename(self, analysis_id: str, new_filename: str) -> Optional[models.Analysis]:
        analysis = await self.get_by_id(analysis_id)
        if not analysis:
            return None
        analysis.filename = new_filename
        await self.db.commit()
        await self.db.refresh(analysis)
        return analysis

    async def delete(self, analysis_id: str) -> None:
        analysis = await self.get_by_id(analysis_id)
        if not analysis:
            return
        await self.db.delete(analysis)
        await self.db.commit()

    async def get_by_id(self, analysis_id: str) -> Optional[models.Analysis]:
        result = await self.db.execute(
            select(models.Analysis).where(models.Analysis.id == analysis_id)
        )
        return result.scalar_one_or_none()

    async def get_detailed_by_id(self, analysis_id: str) -> Optional[models.Analysis]:
        stmt = (
            select(models.Analysis)
            .options(
                joinedload(models.Analysis.versions).joinedload(models.AnalysisVersion.steps)
            )
            .where(models.Analysis.id == analysis_id)
        )
        result = await self.db.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def list_by_user(self, user_id: int, skip: int = 0, limit: int = 100) -> List[models.Analysis]:
        stmt = (
            select(models.Analysis)
            .where(models.Analysis.user_id == user_id)
            .order_by(models.Analysis.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def count_by_user(self, user_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(models.Analysis)
            .where(models.Analysis.user_id == user_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def update_paths_and_status(self, analysis_id: str, *, status: Optional[models.AnalysisStatus] = None, result_blob_name: Optional[str] = None, transcript_blob_name: Optional[str] = None, transcript_snippet: Optional[str] = None, analysis_snippet: Optional[str] = None) -> None:
        analysis = await self.get_by_id(analysis_id)
        if not analysis:
            return
        if status is not None:
            analysis.status = status
        if result_blob_name is not None:
            analysis.result_blob_name = result_blob_name
        if transcript_blob_name is not None:
            analysis.transcript_blob_name = transcript_blob_name
        if transcript_snippet is not None:
            analysis.transcript_snippet = transcript_snippet
        if analysis_snippet is not None:
            analysis.analysis_snippet = analysis_snippet
        await self.db.commit()

    async def update_status(self, analysis_id: str, status: models.AnalysisStatus) -> None:
        await self.update_paths_and_status(analysis_id, status=status)

    async def update_progress(self, analysis_id: str, progress: int) -> None:
        analysis = await self.get_by_id(analysis_id)
        if not analysis:
            return
        analysis.progress = max(0, min(100, int(progress)))
        await self.db.commit()

    async def add_version(self, analysis_id: str, prompt_used: str, result_blob_name: Optional[str] = None, people_involved: Optional[str] = None, structured_plan: Optional[dict] = None) -> models.AnalysisVersion:
        version = models.AnalysisVersion(
            analysis_id=analysis_id,
            prompt_used=prompt_used,
            result_blob_name=result_blob_name,
            people_involved=people_involved,
            structured_plan=structured_plan,
        )
        self.db.add(version)
        await self.db.commit()
        await self.db.refresh(version)
        return version

    async def get_version_by_id(self, version_id: str) -> Optional[models.AnalysisVersion]:
        result = await self.db.execute(
            select(models.AnalysisVersion).where(models.AnalysisVersion.id == version_id)
        )
        return result.scalar_one_or_none()

    async def get_step_result_by_id(self, step_result_id: str) -> Optional[models.AnalysisStepResult]:
        result = await self.db.execute(
            select(models.AnalysisStepResult).where(models.AnalysisStepResult.id == step_result_id)
        )
        return result.scalar_one_or_none()

    async def get_step_result_with_analysis_owner(self, step_result_id: str) -> Optional[models.AnalysisStepResult]:
        stmt = (
            select(models.AnalysisStepResult)
            .options(
                joinedload(models.AnalysisStepResult.version)
                .joinedload(models.AnalysisVersion.analysis_record)
            )
            .where(models.AnalysisStepResult.id == step_result_id)
        )
        result = await self.db.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def get_step_result_with_full_context(self, step_result_id: str) -> Optional[models.AnalysisStepResult]:
        stmt = (
            select(models.AnalysisStepResult)
            .options(
                # Étape 1: On charge la relation "version" depuis AnalysisStepResult
                joinedload(models.AnalysisStepResult.version).options(
                    # Étape 2: Depuis "version", on charge deux chemins différents
                    
                    # Chemin A: On charge l'enregistrement d'analyse principal et son prompt flow
                    joinedload(models.AnalysisVersion.analysis_record)
                    .joinedload(models.Analysis.prompt_flow)
                    .joinedload(models.PromptFlow.steps),

                    # Chemin B: On charge tous les "steps" (résultats d'étapes) associés à cette version
                    # On utilise selectinload car c'est une relation "one-to-many"
                    selectinload(models.AnalysisVersion.steps)
                )
            )
            .where(models.AnalysisStepResult.id == step_result_id)
        )
        result = await self.db.execute(stmt)
        return result.unique().scalar_one_or_none()