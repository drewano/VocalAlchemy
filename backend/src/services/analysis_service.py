import json
import logging
import time
from typing import Optional, Protocol, List

from langextract.resolver import ResolverParsingError
from src.infrastructure.repositories.analysis_repository import AnalysisRepository
from src.services.external_apis.azure_speech_client import AzureSpeechClient
from src.services.external_apis.litellm_ai_processor import LiteLLMAIProcessor
from src.infrastructure.sql_models import AnalysisStatus
from src.services import pipeline_prompts
from pydub import AudioSegment
from src.services.blob_storage_service import BlobStorageService
import io
import uuid



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

    

    async def _execute_analysis_pipeline(self, transcript: str, original_prompt: Optional[str]) -> str:
        if not isinstance(transcript, str) or not transcript.strip():
            raise ValueError("Invalid transcript for pipeline")

        # Étape 1 : Intervenants
        intervenants_md = await self.ai_analyzer.execute_prompt(
            system_prompt=pipeline_prompts.PROMPT_INTERVENANTS,
            user_content=transcript,
        )

        # Étape 2 : Ordre du Jour
        prompt_odj = pipeline_prompts.PROMPT_ORDRE_DU_JOUR.format(intervenants=intervenants_md)
        ordre_du_jour_md = await self.ai_analyzer.execute_prompt(
            system_prompt=prompt_odj,
            user_content=transcript,
        )

        # Étape 3 : Synthèse
        prompt_synthese = pipeline_prompts.PROMPT_SYNTHESE.format(
            intervenants=intervenants_md,
            ordre_du_jour=ordre_du_jour_md,
        )
        synthese_md = await self.ai_analyzer.execute_prompt(
            system_prompt=prompt_synthese,
            user_content=transcript,
        )

        # Étape 4 : Décisions et Actions
        prompt_decisions = pipeline_prompts.PROMPT_DECISIONS.format(
            intervenants=intervenants_md,
            synthese=synthese_md,
        )
        decisions_md = await self.ai_analyzer.execute_prompt(
            system_prompt=prompt_decisions,
            user_content=transcript,
        )

        # Assemblage Final
        final_report_content = (
            "# Procès-Verbal de Réunion\n\n"
            "## Intervenants\n" + intervenants_md.strip() + "\n\n"
            "## Ordre du jour\n" + ordre_du_jour_md.strip() + "\n\n"
            "## Synthèse des échanges\n" + synthese_md.strip() + "\n\n"
            "## Relevé de décisions et d'actions\n" + decisions_md.strip() + "\n"
        )
        return final_report_content
