import os
import shutil
from typing import Optional, Protocol, List

from src.infrastructure.repositories.analysis_repository import AnalysisRepository


class AnalysisNotFoundException(Exception):
    pass


class AudioSplitter(Protocol):
    def __call__(self, source_path: str, output_dir: str) -> List[str]:
        ...


class Transcriber(Protocol):
    def __call__(self, audio_chunk_path: str) -> str:
        ...


class AIAnalyzer(Protocol):
    def __call__(self, transcript: str, user_prompt: Optional[str] = None) -> str:
        ...


class AnalysisService:
    def __init__(
        self,
        analysis_repo: AnalysisRepository,
        *,
        audio_splitter: AudioSplitter,
        transcriber: Transcriber,
        ai_analyzer: AIAnalyzer,
    ) -> None:
        self.analysis_repo = analysis_repo
        self.audio_splitter = audio_splitter
        self.transcriber = transcriber
        self.ai_analyzer = ai_analyzer

    def _extract_people_involved(self, analysis_text: str) -> Optional[str]:
        if not analysis_text:
            return None
        marker = "### Personnes Concernées"
        idx = analysis_text.find(marker)
        if idx == -1:
            return None
        return analysis_text[idx + len(marker):].strip() or None

    def _prepare_segments_dir(self, base_output_dir: str) -> str:
        segments_dir = os.path.join(base_output_dir, "segments")
        os.makedirs(segments_dir, exist_ok=True)
        return segments_dir

    def _write_text_file(self, path: str, content: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def run_full_pipeline(self, analysis_id: str, source_path: str, base_output_dir: str, user_prompt: Optional[str] = None) -> str:
        if not source_path or not isinstance(source_path, str):
            raise ValueError("Invalid source_path provided")
        if not base_output_dir or not isinstance(base_output_dir, str):
            raise ValueError("Invalid base_output_dir provided")
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source file not found: {source_path}")

        segments_dir = self._prepare_segments_dir(base_output_dir)

        # Update status and split audio
        self.analysis_repo.update_status(analysis_id, "Découpage du fichier audio...")
        segment_paths = self.audio_splitter(source_path, segments_dir)

        # Transcribe
        transcriptions: List[str] = []
        total_chunks = len(segment_paths)
        for i, segment_path in enumerate(segment_paths):
            self.analysis_repo.update_status(analysis_id, f"Transcription du segment {i+1}/{total_chunks}...")
            transcription = self.transcriber(segment_path)
            transcriptions.append(transcription)

        full_text = "\n".join(transcriptions)
        transcript_path = os.path.join(base_output_dir, "transcription.txt")
        self._write_text_file(transcript_path, full_text)

        # Analyze
        self.analysis_repo.update_status(analysis_id, "Analyse de la transcription par l'IA...")
        analysis_result = self.ai_analyzer(full_text, user_prompt)

        # Save report
        report_path = os.path.join(base_output_dir, "report.txt")
        self._write_text_file(report_path, analysis_result)

        people_involved = self._extract_people_involved(analysis_result)
        self.analysis_repo.add_version(
            analysis_id=analysis_id,
            prompt_used=user_prompt or "",
            result_path=report_path,
            people_involved=people_involved,
        )

        # Finish
        self.analysis_repo.update_paths_and_status(analysis_id, status="Terminé", transcript_path=transcript_path)

        # Cleanup
        if os.path.exists(segments_dir):
            shutil.rmtree(segments_dir)

        return report_path

    def rerun_analysis_from_transcript(self, analysis_id: str, transcript: str, new_prompt: Optional[str], base_output_dir: str) -> str:
        if not transcript or not isinstance(transcript, str):
            raise ValueError("Invalid transcript provided")
        if not base_output_dir or not isinstance(base_output_dir, str):
            raise ValueError("Invalid base_output_dir provided")

        self.analysis_repo.update_status(analysis_id, "Ré-analyse de la transcription par l'IA...")
        analysis_result = self.ai_analyzer(transcript, new_prompt)

        ts = str(int(__import__("time").time()))
        report_path = os.path.join(base_output_dir, f"report_{ts}.txt")
        self._write_text_file(report_path, analysis_result)

        people_involved = self._extract_people_involved(analysis_result)
        self.analysis_repo.add_version(
            analysis_id=analysis_id,
            prompt_used=new_prompt or "",
            result_path=report_path,
            people_involved=people_involved,
        )

        self.analysis_repo.update_status(analysis_id, "Terminé")
        return report_path
