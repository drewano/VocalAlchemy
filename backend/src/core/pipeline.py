import os
import shutil
from src.core.audio_splitter import split_audio
from src.core.gladia_client import transcribe_audio_chunk
from src.core.ai_processor import analyze_transcript

def run_full_pipeline(source_path: str, base_output_dir: str, update_status_callback: callable) -> str:
    """
    Run the full audio processing pipeline: split, transcribe, and analyze.
    
    Args:
        source_path (str): Path to the source audio file
        base_output_dir (str): Base directory for output files
        update_status_callback (callable): Function to call with status updates
        
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
    update_status_callback("Découpage du fichier audio...")
    segment_paths = split_audio(source_path, segments_dir)
    
    # Step 2: Initialize list for transcriptions
    transcriptions = []
    
    # Step 3: Transcribe each segment
    total_chunks = len(segment_paths)
    for i, segment_path in enumerate(segment_paths):
        # Update status
        update_status_callback(f"Transcription du segment {i+1}/{total_chunks}...")
        
        # Transcribe the segment
        transcription = transcribe_audio_chunk(segment_path)
        
        # Add the transcription directly to the list
        transcriptions.append(transcription)
    
    # Step 4: Concatenate all transcriptions
    full_text = "\n".join(transcriptions)
    
    # Step 5: Update status and analyze transcription
    update_status_callback("Analyse de la transcription par l'IA...")
    analysis_result = analyze_transcript(full_text)
    
    # Step 6: Save the final report
    report_path = os.path.join(base_output_dir, "report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(analysis_result)
    
    # Step 7: Update status and clean up temporary files
    update_status_callback("Terminé", result_path=report_path)
    
    # Clean up temporary segments
    if os.path.exists(segments_dir):
        shutil.rmtree(segments_dir)
    
    # Return the path to the final report
    return report_path