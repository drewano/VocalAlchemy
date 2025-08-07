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



class AnalysisNotFoundException(Exception):
    pass


class Transcriber(Protocol):
    def submit_batch_transcription(self, file_path: str) -> str:
        ...

    def check_transcription_status(self, status_url: str) -> dict:
        ...

    def get_transcription_files(self, status_url: str) -> dict:
        ...

    def get_transcription_result(self, files_response: dict) -> str:
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

    def run_full_pipeline(self, analysis_id: str, source_path: str, base_output_dir: str, user_prompt: Optional[str] = None) -> str:
        if not source_path or not isinstance(source_path, str):
            raise ValueError("Invalid source_path provided")
        if not base_output_dir or not isinstance(base_output_dir, str):
            raise ValueError("Invalid base_output_dir provided")
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source file not found: {source_path}")

        try:
            # 1) Update status to PROCESSING
            self.analysis_repo.update_status(analysis_id, AnalysisStatus.PROCESSING)

            # 2) Submit batch transcription job
            status_url = self.transcriber.submit_batch_transcription(source_path)

            # 3) Persist job tracking URL on Analysis
            analysis = self.analysis_repo.get_by_id(analysis_id)
            if analysis:
                analysis.transcription_job_url = status_url
                self.analysis_repo.db.commit()

            # 4) Polling loop for job status
            start_time = time.time()
            POLLING_TIMEOUT_SECONDS = 3600  # 1 hour
            while True:
                # Timeout guard
                if time.time() - start_time > POLLING_TIMEOUT_SECONDS:
                    raise TimeoutError("Transcription polling timed out after 1 hour.")

                status_resp = self.transcriber.check_transcription_status(status_url)
                status = status_resp.get("status") or status_resp.get("statusCode")
                logging.info(f"Transcription status for {analysis_id}: {status}")

                if str(status).lower() in {"succeeded"}:
                    break
                if str(status).lower() == "failed":
                    # Log full Azure response for debugging/observability
                    logging.error(f"Azure transcription failed. Full response: {status_resp}")
                    # Prefer specific errors if present, otherwise include full JSON payload
                    errors = status_resp.get("errors") or status_resp.get("properties", {}).get("errors")
                    if not errors:
                        try:
                            errors = json.dumps(status_resp, ensure_ascii=False)
                        except Exception:
                            errors = str(status_resp)
                    raise RuntimeError(f"Transcription failed: {errors}")

                # Optionally update progress if provided by service
                progress = status_resp.get("properties", {}).get("progress")
                if isinstance(progress, (int, float)):
                    try:
                        self.analysis_repo.update_progress(analysis_id, int(progress))
                    except Exception:
                        pass

                time.sleep(30)

            # 7) Retrieve files list and fetch final transcription text
            logging.info("Fetching transcription files list from Azure Speech...")
            files_response = self.transcriber.get_transcription_files(status_url)
            full_text = self.transcriber.get_transcription_result(files_response)

            # 8) Save transcript to file
            os.makedirs(base_output_dir, exist_ok=True)
            transcript_path = os.path.join(base_output_dir, "transcription.txt")
            self._write_text_file(transcript_path, full_text)

            # 9) Run downstream analysis pipeline
            final_report_content = self._execute_analysis_pipeline(full_text, user_prompt)

            # 10) Save report and create version entry
            report_path = os.path.join(base_output_dir, "report.txt")
            self._write_text_file(report_path, final_report_content)

            self.analysis_repo.add_version(
                analysis_id=analysis_id,
                prompt_used=user_prompt or "",
                result_path=report_path,
                people_involved=None,
                structured_plan=None,
            )

            # Finish
            self.analysis_repo.update_paths_and_status(
                analysis_id,
                status=AnalysisStatus.COMPLETED,
                transcript_path=transcript_path,
            )
            self.analysis_repo.update_progress(analysis_id, 100)

            return report_path
        except Exception as e:
            error_details = f"Pipeline failed unexpectedly. Error type: {type(e).__name__}. Details: {e}"
            logging.error(error_details)
            # Mark FAILED and persist error details
            self.analysis_repo.update_paths_and_status(analysis_id, status=AnalysisStatus.FAILED)
            analysis = self.analysis_repo.get_by_id(analysis_id)
            if analysis:
                analysis.status = AnalysisStatus.FAILED
                analysis.error_message = error_details
                self.analysis_repo.db.commit()
            raise

    def delete_analysis(self, analysis_id: str, user_id: int) -> None:
        analysis = self.analysis_repo.get_detailed_by_id(analysis_id)
        if not analysis:
            raise AnalysisNotFoundException(f"Analysis not found: {analysis_id}")
        if analysis.user_id != user_id:
            raise PermissionError('Access denied')

        base_dir = None
        if analysis.source_file_path:
            try:
                base_dir = os.path.dirname(analysis.source_file_path)
            except Exception:
                base_dir = None
        if base_dir and os.path.exists(base_dir):
            try:
                shutil.rmtree(base_dir)
            except FileNotFoundError:
                pass

        self.analysis_repo.delete(analysis_id)

    def rerun_analysis_from_transcript(self, analysis_id: str, transcript: str, new_prompt: Optional[str], base_output_dir: str) -> str:
        if not transcript or not isinstance(transcript, str):
            raise ValueError("Invalid transcript provided")
        if not base_output_dir or not isinstance(base_output_dir, str):
            raise ValueError("Invalid base_output_dir provided")

        self.analysis_repo.update_status(analysis_id, AnalysisStatus.PROCESSING)

        # Exécuter le pipeline factorisé
        final_report_content = self._execute_analysis_pipeline(transcript, new_prompt)

        # Sauvegarde dans un fichier versionné pour ne pas écraser l'existant
        report_path = os.path.join(base_output_dir, f"report_{int(__import__('time').time())}.txt")
        self._write_text_file(report_path, final_report_content)

        # Versionnement
        self.analysis_repo.add_version(
            analysis_id=analysis_id,
            prompt_used=new_prompt or "",
            result_path=report_path,
            people_involved=None,
            structured_plan=None,
        )

        self.analysis_repo.update_status(analysis_id, AnalysisStatus.COMPLETED)
        self.analysis_repo.update_progress(analysis_id, 100)
        return report_path
