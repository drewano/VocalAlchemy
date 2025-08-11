import logging
from io import BytesIO
from typing import Optional, List

from docx import Document

from ..infrastructure.repositories.analysis_repository import AnalysisRepository
from ..infrastructure import sql_models as models
from ..api.schemas import AnalysisExportDTO, AnalysisStepExportDTO
from .blob_storage_service import BlobStorageService
from .analysis_service import AnalysisNotFoundException


class ExportService:
    def __init__(
        self,
        analysis_repo: AnalysisRepository,
        blob_storage_service: BlobStorageService,
    ) -> None:
        self.analysis_repo = analysis_repo
        self.blob_storage_service = blob_storage_service

    async def generate_word_document(self, analysis_detail: AnalysisExportDTO, content_type: str = "assembly") -> BytesIO:
        """
        Génère un document Word à partir des détails d'une analyse.
        
        Args:
            analysis_detail: Détails de l'analyse
            content_type: Type de contenu à inclure ('transcription' ou 'assembly')
            
        Returns:
            BytesIO: Buffer contenant le document Word
        """
        document = Document()
        
        # Titre du document
        document.add_heading(f'Analyse: {analysis_detail.filename}', 0)
        
        if content_type == "transcription":
            # Inclure uniquement le titre et la transcription
            # Note: With the simplified DTO, we no longer have transcript data
            document.add_heading('Transcription', level=1)
            document.add_paragraph("Transcription non disponible dans cet export.")
        else:  # content_type == "assembly"
            # Ajoutez un titre principal au document
            document.add_heading('Assemblage des résultats', level=1)
            
            # Itérez sur la liste analysis_detail.steps
            for step in analysis_detail.steps:
                # Ajoutez le nom de l'étape comme un titre de niveau 2
                document.add_heading(step.step_name, level=2)
                # Ajoutez le contenu de l'étape comme un paragraphe
                document.add_paragraph(step.content or "")
        
        # Sauvegarder dans un buffer
        buffer = BytesIO()
        document.save(buffer)
        buffer.seek(0)
        return buffer

    async def get_analysis_detail_for_export(self, analysis_id: str, user_id: int) -> AnalysisExportDTO:
        """
        Récupère les détails d'une analyse pour l'export.
        """
        # Conservez la récupération de l'analyse et les vérifications de permissions
        analysis = await self.analysis_repo.get_detailed_by_id(analysis_id)
        if not analysis:
            raise AnalysisNotFoundException("Analysis not found")
        if analysis.user_id != user_id:
            raise PermissionError("Access denied")
            
        # Conservez la logique qui trie les versions de l'analyse pour trouver la plus récente
        versions_sorted = sorted(analysis.versions or [], key=lambda v: v.created_at or 0, reverse=True)
        
        # Initialisez une liste vide
        steps_for_export = []
        
        # Si versions_sorted n'est pas vide, prenez la première version
        if versions_sorted:
            latest_version = versions_sorted[0]
            
            # Itérez sur les steps de latest_version
            for step in (latest_version.steps or []):
                # Créez une instance de AnalysisStepExportDTO avec step_name et content
                if step.content:  # Only add steps that have content
                    step_dto = AnalysisStepExportDTO(
                        step_name=step.step_name,
                        content=step.content
                    )
                    # Ajoutez-la à steps_for_export
                    steps_for_export.append(step_dto)
        
        # À la fin, retournez une instance de AnalysisExportDTO
        return AnalysisExportDTO(
            id=analysis.id,
            filename=analysis.filename,
            status=analysis.status,
            created_at=analysis.created_at,
            steps=steps_for_export
        )