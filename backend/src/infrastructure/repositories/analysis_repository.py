from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from src.infrastructure.repositories.base_repository import BaseRepository
from src.infrastructure import sql_models as models


class AnalysisRepository(BaseRepository):
    def create(self, user_id: int, filename: str, status: models.AnalysisStatus = models.AnalysisStatus.PENDING, source_file_path: str = "", prompt: Optional[str] = None) -> models.Analysis:
        analysis = models.Analysis(
            user_id=user_id,
            filename=filename,
            status=status,
            source_file_path=source_file_path,
            prompt=prompt,
        )
        self.db.add(analysis)
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def update_filename(self, analysis_id: str, new_filename: str) -> Optional[models.Analysis]:
        analysis = self.get_by_id(analysis_id)
        if not analysis:
            return None
        analysis.filename = new_filename
        self.db.commit()
        self.db.refresh(analysis)
        return analysis

    def delete(self, analysis_id: str) -> None:
        analysis = self.get_by_id(analysis_id)
        if not analysis:
            return
        self.db.delete(analysis)
        self.db.commit()

    def get_by_id(self, analysis_id: str) -> Optional[models.Analysis]:
        return (
            self.db.query(models.Analysis)
            .filter(models.Analysis.id == analysis_id)
            .first()
        )

    def get_detailed_by_id(self, analysis_id: str) -> Optional[models.Analysis]:
        return (
            self.db.query(models.Analysis)
            .options(joinedload(models.Analysis.versions))
            .filter(models.Analysis.id == analysis_id)
            .first()
        )

    def list_by_user(self, user_id: int, skip: int = 0, limit: int = 100) -> List[models.Analysis]:
        return (
            self.db.query(models.Analysis)
            .filter(models.Analysis.user_id == user_id)
            .order_by(models.Analysis.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_by_user(self, user_id: int) -> int:
        return (
            self.db.query(models.Analysis)
            .filter(models.Analysis.user_id == user_id)
            .count()
        )

    def update_paths_and_status(self, analysis_id: str, *, status: Optional[models.AnalysisStatus] = None, result_path: Optional[str] = None, transcript_path: Optional[str] = None) -> None:
        analysis = self.get_by_id(analysis_id)
        if not analysis:
            return
        if status is not None:
            analysis.status = status
        if result_path is not None:
            analysis.result_path = result_path
        if transcript_path is not None:
            analysis.transcript_path = transcript_path
        self.db.commit()

    def update_status(self, analysis_id: str, status: models.AnalysisStatus) -> None:
        self.update_paths_and_status(analysis_id, status=status)

    def update_progress(self, analysis_id: str, progress: int) -> None:
        analysis = self.get_by_id(analysis_id)
        if not analysis:
            return
        analysis.progress = max(0, min(100, int(progress)))
        self.db.commit()

    def add_version(self, analysis_id: str, prompt_used: str, result_path: str, people_involved: Optional[str] = None) -> models.AnalysisVersion:
        version = models.AnalysisVersion(
            analysis_id=analysis_id,
            prompt_used=prompt_used,
            result_path=result_path,
            people_involved=people_involved,
        )
        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)
        return version

    def get_version_by_id(self, version_id: str) -> Optional[models.AnalysisVersion]:
        return (
            self.db.query(models.AnalysisVersion)
            .filter(models.AnalysisVersion.id == version_id)
            .first()
        )
