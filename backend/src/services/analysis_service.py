import os
import shutil
import concurrent.futures
import json
import logging
from typing import Optional, Protocol, List

from langextract.resolver import ResolverParsingError
from src.infrastructure.repositories.analysis_repository import AnalysisRepository
from src.services.external_apis.azure_speech_client import AzureSpeechClient
from src.services.external_apis.litellm_ai_processor import LiteLLMAIProcessor
from src.infrastructure.sql_models import AnalysisStatus
from src.services import pipeline_prompts



class AnalysisNotFoundException(Exception):
    pass


class AudioSplitter(Protocol):
    def __call__(self, source_path: str, output_dir: str) -> List[str]:
        ...


class Transcriber(Protocol):
    def transcribe_audio_chunk(self, audio_chunk_path: str) -> str:
        ...


class AIAnalyzer(Protocol):
    def execute_prompt(self, system_prompt: str, user_content: str) -> str:
        ...


class AnalysisService:
    def __init__(
        self,
        analysis_repo: AnalysisRepository,
        *,
        audio_splitter: AudioSplitter,
        transcriber: Transcriber,
        ai_analyzer: LiteLLMAIProcessor,
    ) -> None:
        self.analysis_repo = analysis_repo
        self.audio_splitter = audio_splitter
        self.transcriber = transcriber
        self.ai_analyzer = ai_analyzer

    def _prepare_segments_dir(self, base_output_dir: str) -> str:
        segments_dir = os.path.join(base_output_dir, "segments")
        os.makedirs(segments_dir, exist_ok=True)
        return segments_dir

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
            segments_dir = self._prepare_segments_dir(base_output_dir)

            # Update status and split audio
            self.analysis_repo.update_status(analysis_id, AnalysisStatus.PROCESSING)
            segment_paths = self.audio_splitter(source_path, segments_dir)

            # Transcribe in parallel
            total_chunks = len(segment_paths)
            transcriptions: List[Optional[str]] = [None] * total_chunks

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future_to_index = {
                    executor.submit(self.transcriber.transcribe_audio_chunk, segment_paths[idx]): idx
                    for idx in range(total_chunks)
                }

                completed = 0
                for future in concurrent.futures.as_completed(future_to_index):
                    idx = future_to_index[future]
                    try:
                        transcriptions[idx] = future.result()
                    except Exception as e:
                        transcriptions[idx] = ""
                        # propagate error to be caught by outer try/except
                        raise e
                    finally:
                        completed += 1
                        self.analysis_repo.update_progress(analysis_id, int((completed / max(total_chunks, 1)) * 100))

            full_text = "\n".join(t for t in transcriptions if t)
            transcript_path = os.path.join(base_output_dir, "transcription.txt")
            self._write_text_file(transcript_path, full_text)

            # Exécuter le pipeline factorisé
            final_report_content = self._execute_analysis_pipeline(full_text, user_prompt)

            # Sauvegarde et Versionnement
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
            self.analysis_repo.update_paths_and_status(analysis_id, status=AnalysisStatus.COMPLETED, transcript_path=transcript_path)
            self.analysis_repo.update_progress(analysis_id, 100)

            # Cleanup
            if os.path.exists(segments_dir):
                shutil.rmtree(segments_dir)

            return report_path
        except Exception as e:
            import logging
            logging.error(f"Pipeline failed for analysis {analysis_id}: {e}")
            # Mark FAILED and persist error details
            self.analysis_repo.update_paths_and_status(analysis_id, status=AnalysisStatus.FAILED)
            analysis = self.analysis_repo.get_by_id(analysis_id)
            if analysis:
                analysis.status = AnalysisStatus.FAILED
                analysis.error_message = str(e)
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
