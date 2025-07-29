import os
from pydub import AudioSegment
from typing import List


def split_audio(source_path: str, output_dir: str, segment_length_ms: int = 3600000) -> List[str]:
    """
    Split an audio file into segments of specified length.
    
    Args:
        source_path (str): Path to the source audio file
        output_dir (str): Directory where segments will be saved
        segment_length_ms (int): Length of each segment in milliseconds (default: 3600000 ms = 1 hour)
        
    Returns:
        List[str]: List of paths to the created segment files
        
    Raises:
        ValueError: If source_path or output_dir are invalid
        FileNotFoundError: If source file doesn't exist
    """
    # Validate inputs
    if not source_path or not isinstance(source_path, str):
        raise ValueError("Invalid source_path provided")
    
    if not output_dir or not isinstance(output_dir, str):
        raise ValueError("Invalid output_dir provided")
    
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Source file not found: {source_path}")
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Load the audio file
    audio = AudioSegment.from_file(source_path)
    
    # Get file extension for consistent output format
    file_extension = os.path.splitext(source_path)[1][1:]  # Get extension without the dot
    
    # Calculate number of segments needed
    total_length_ms = len(audio)
    num_segments = (total_length_ms + segment_length_ms - 1) // segment_length_ms  # Ceiling division
    
    # List to store paths of created segments
    segment_paths = []
    
    # Split audio into segments
    for i in range(num_segments):
        start_time = i * segment_length_ms
        end_time = min((i + 1) * segment_length_ms, total_length_ms)
        
        # Extract segment
        segment = audio[start_time:end_time]
        
        # Generate output filename
        output_filename = f"chunk_{i}.{file_extension}"
        output_path = os.path.join(output_dir, output_filename)
        
        # Export segment
        segment.export(output_path, format=file_extension)
        
        # Add to list of segment paths
        segment_paths.append(output_path)
    
    return segment_paths