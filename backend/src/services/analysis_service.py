import os
import shutil
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
import os
import io



class AnalysisNotFoundException(Exception):
    pass


class Transcriber(Protocol):
    def submit_batch_transcription(self, file_content: bytes, original_filename: str, blob_name: str) -> str:
        ...

    def check_transcription_status(self, status_url: str) -> dict:
        ...

    def get_transcription_files(self, status_url: str) -> dict:
        ...

    def get_transcription_result(self, files_response: dict) -> str:
        ...

    def delete_blob(self, blob_name: str) -> None:
        ...


class AIAnalyzer(Protocol):
    def execute_prompt(self, system_prompt: str, user_content: str) -> str:
        ...


class AnalysisService:
    def __init__(
        self,
        analysis_repo: AnalysisRepository,
        *,
        transcriber: Transcriber,
        ai_analyzer: LiteLLMAIProcessor,
    ) -> None:
        self.analysis_repo = analysis_repo
        self.transcriber = transcriber
        self.ai_analyzer = ai_analyzer

    def _write_text_file(self, path: str, content: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def _execute_analysis_pipeline(self, transcript: str, original_prompt: Optional[str]) -> str:
        if not isinstance(transcript, str) or not transcript.strip():
            raise ValueError("Invalid transcript for pipeline")

        # Étape 1 : Intervenants
        intervenants_md = self.ai_analyzer.execute_prompt(
            system_prompt=pipeline_prompts.PROMPT_INTERVENANTS,
            user_content=transcript,
        )

        # Étape 2 : Ordre du Jour
        prompt_odj = pipeline_prompts.PROMPT_ORDRE_DU_JOUR.format(intervenants=intervenants_md)
        ordre_du_jour_md = self.ai_analyzer.execute_prompt(
            system_prompt=prompt_odj,
            user_content=transcript,
        )

        # Étape 3 : Synthèse
        prompt_synthese = pipeline_prompts.PROMPT_SYNTHESE.format(
            intervenants=intervenants_md,
            ordre_du_jour=ordre_du_jour_md,
        )
        synthese_md = self.ai_analyzer.execute_prompt(
            system_prompt=prompt_synthese,
            user_content=transcript,
        )

        # Étape 4 : Décisions et Actions
        prompt_decisions = pipeline_prompts.PROMPT_DECISIONS.format(
            intervenants=intervenants_md,
            synthese=synthese_md,
        )
        decisions_md = self.ai_analyzer.execute_prompt(
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

    def start_transcription_pipeline(self, analysis_id: str, file_content: bytes, filename: str, blob_name: str) -> None:
        if not isinstance(file_content, (bytes, bytearray)) or len(file_content) == 0:
            raise ValueError("Invalid file_content provided")
        if not filename or not isinstance(filename, str):
            raise ValueError("Invalid filename provided")
        if not blob_name or not isinstance(blob_name, str):
            raise ValueError("Invalid blob_name provided")

        try:
            # 1. Charger l'audio original depuis la mémoire
            audio = AudioSegment.from_file(io.BytesIO(file_content))
            # 2. Normaliser l'audio: 16kHz, mono, 16-bit
            normalized_audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
            # 3. Exporter en FLAC en mémoire
            buf = io.BytesIO()
            normalized_audio.export(buf, format="flac")
            buf.seek(0)
            normalized_bytes = buf.read()

            # 4. Soumettre le FLAC à Azure
            self.analysis_repo.update_status(analysis_id, AnalysisStatus.TRANSCRIPTION_IN_PROGRESS)
            status_url = self.transcriber.submit_batch_transcription(normalized_bytes, filename, blob_name)
            analysis = self.analysis_repo.get_by_id(analysis_id)
            if analysis:
                analysis.transcription_job_url = status_url
                self.analysis_repo.db.commit()
        except Exception as e:
            error_details = f"Transcription submission failed. Error type: {type(e).__name__}. Details: {e}"
            logging.error(error_details)
            self.analysis_repo.update_status(analysis_id, AnalysisStatus.TRANSCRIPTION_FAILED)
            analysis = self.analysis_repo.get_by_id(analysis_id)
            if analysis:
                analysis.error_message = error_details
                self.analysis_repo.db.commit()
            raise

    def check_transcription_and_run_analysis(self, analysis_id: str, base_output_dir: str) -> None:
        analysis = self.analysis_repo.get_by_id(analysis_id)
        if not analysis:
            raise AnalysisNotFoundException(f"Analysis not found: {analysis_id}")
        if analysis.status != AnalysisStatus.TRANSCRIPTION_IN_PROGRESS:
            return
        if not analysis.transcription_job_url:
            logging.warning("No transcription_job_url stored for analysis %s", analysis_id)
            return
        status_resp = self.transcriber.check_transcription_status(analysis.transcription_job_url)
        status = str(status_resp.get("status") or status_resp.get("statusCode")).lower()
        if status == "succeeded":
            files_response = self.transcriber.get_transcription_files(analysis.transcription_job_url)
            full_text = self.transcriber.get_transcription_result(files_response)
            os.makedirs(base_output_dir, exist_ok=True)
            transcript_path = os.path.join(base_output_dir, "transcription.txt")
            self._write_text_file(transcript_path, full_text)
            self.analysis_repo.update_paths_and_status(
                analysis_id,
                status=AnalysisStatus.ANALYSIS_PENDING,
                transcript_path=transcript_path,
            )
            try:
                # Start background analysis task; actual scheduling handled by caller/framework
                self.run_ai_analysis_pipeline(analysis_id, base_output_dir)
            except Exception as e:
                logging.error("Failed to start AI analysis background task: %s", e)
        elif status == "failed":
            logging.error(f"Azure transcription failed. Full response: {status_resp}")
            self.analysis_repo.update_status(analysis_id, AnalysisStatus.TRANSCRIPTION_FAILED)

    def run_ai_analysis_pipeline(self, analysis_id: str, base_output_dir: str) -> str:
        analysis = self.analysis_repo.get_by_id(analysis_id)
        if not analysis:
            raise AnalysisNotFoundException(f"Analysis not found: {analysis_id}")
        if not analysis.transcript_path or not os.path.exists(analysis.transcript_path):
            raise FileNotFoundError("Transcript file not found for analysis")
        with open(analysis.transcript_path, "r", encoding="utf-8") as f:
            transcript = f.read()
        try:
            self.analysis_repo.update_status(analysis_id, AnalysisStatus.ANALYSIS_IN_PROGRESS)
            final_report_content = self._execute_analysis_pipeline(transcript, analysis.prompt)
            os.makedirs(base_output_dir, exist_ok=True)
            report_path = os.path.join(base_output_dir, "report.txt")
            self._write_text_file(report_path, final_report_content)
            self.analysis_repo.add_version(
                analysis_id=analysis_id,
                prompt_used=analysis.prompt or "",
                result_path=report_path,
                people_involved=None,
                structured_plan=None,
            )
            self.analysis_repo.update_paths_and_status(analysis_id, status=AnalysisStatus.COMPLETED)
            self.analysis_repo.update_progress(analysis_id, 100)
            return report_path
        except Exception as e:
            error_details = f"AI analysis failed. Error type: {type(e).__name__}. Details: {e}"
            logging.error(error_details)
            self.analysis_repo.update_status(analysis_id, AnalysisStatus.ANALYSIS_FAILED)
            analysis = self.analysis_repo.get_by_id(analysis_id)
            if analysis:
                analysis.error_message = error_details
                self.analysis_repo.db.commit()
            raise

    def delete_analysis(self, analysis_id: str, user_id: int) -> None:
        analysis = self.analysis_repo.get_detailed_by_id(analysis_id)
        if not analysis:
            raise AnalysisNotFoundException(f"Analysis not found: {analysis_id}")
        if analysis.user_id != user_id:
            raise PermissionError('Access denied')

        # Delete source blob in Azure Storage if available
        try:
            if getattr(analysis, "source_blob_name", None):
                self.transcriber.delete_blob(analysis.source_blob_name)
        except Exception as e:
            logging.warning(f"Failed to delete source blob for analysis {analysis_id}: {e}")

        # Remove local outputs (transcript, reports)
        base_dir = None
        try:
            possible_paths = [analysis.transcript_path, analysis.result_path]
            existing = [p for p in possible_paths if p]
            if existing:
                base_dir = os.path.dirname(existing[0])
        except Exception:
            base_dir = None
        if base_dir and os.path.exists(base_dir):
            try:
                shutil.rmtree(base_dir)
            except FileNotFoundError:
                pass

        self.analysis_repo.delete(analysis_id)
