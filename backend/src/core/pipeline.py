import os
import shutil
from sqlalchemy.orm import Session
from ..database import SessionLocal
from .. import models

from src.core.audio_splitter import split_audio
from src.core.gladia_client import transcribe_audio_chunk
from src.core.ai_processor import analyze_transcript

def update_analysis_status(analysis_id: str, status: str, result_path: str = None, transcript_path: str = None):
    """Update the status of an analysis in the database."""
    db: Session = SessionLocal()
    try:
        analysis = db.query(models.Analysis).filter(models.Analysis.id == analysis_id).first()
        if analysis:
            analysis.status = status
            if result_path:
                analysis.result_path = result_path
            if transcript_path:
                analysis.transcript_path = transcript_path
            db.commit()
    finally:
        db.close()

def run_full_pipeline(analysis_id: str, source_path: str, base_output_dir: str, user_prompt: str = None) -> str:
    """
    Run the full audio processing pipeline: split, transcribe, and analyze.
    
    Args:
        analysis_id (str): ID of the analysis record in the database
        source_path (str): Path to the source audio file
        base_output_dir (str): Base directory for output files
        user_prompt (str, optional): Custom prompt for the AI analysis
        
    Returns:
        str: Path to the final report file
        
    Raises:
        ValueError: If source_path or base_output_dir are invalid
        FileNotFoundError: If source file doesn't exist
    """
    # Validate inputs
    if not source_path or not isinstance(source_path, str):
        raise ValueError("Invalid source_path provided")
    
    if not base_output_dir or not isinstance(base_output_dir, str):
        raise ValueError("Invalid base_output_dir provided")
    
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Source file not found: {source_path}")
    
    # Create directories for processing
    segments_dir = os.path.join(base_output_dir, "segments")
    os.makedirs(segments_dir, exist_ok=True)
    
    # Step 1: Update status and split audio
    update_analysis_status(analysis_id, "Découpage du fichier audio...")
    segment_paths = split_audio(source_path, segments_dir)
    
    # Step 2: Initialize list for transcriptions
    transcriptions = []
    
    # Step 3: Transcribe each segment
    total_chunks = len(segment_paths)
    for i, segment_path in enumerate(segment_paths):
        # Update status
        update_analysis_status(analysis_id, f"Transcription du segment {i+1}/{total_chunks}...")
        
        # Transcribe the segment
        transcription = transcribe_audio_chunk(segment_path)
        
        # Add the transcription directly to the list
        transcriptions.append(transcription)
    
    # Step 4: Concatenate all transcriptions
    full_text = "\n".join(transcriptions)
    
    # Save the raw transcription to a file
    transcript_path = os.path.join(base_output_dir, "transcription.txt")
    with open(transcript_path, "w", encoding="utf-8") as f:
        f.write(full_text)
    
    # Step 5: Update status and analyze transcription
    update_analysis_status(analysis_id, "Analyse de la transcription par l'IA...")
    analysis_result = analyze_transcript(full_text, user_prompt)
    
    # Step 6: Save the final report
    report_path = os.path.join(base_output_dir, "report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(analysis_result)
    
    # Step 7: Update status and clean up temporary files
    update_analysis_status(analysis_id, "Terminé", result_path=report_path, transcript_path=transcript_path)
    
    # Clean up temporary segments
    if os.path.exists(segments_dir):
        shutil.rmtree(segments_dir)
    
    # Return the path to the final report
    return report_path