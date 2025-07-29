import requests
import os
from typing import Dict, Any
from src.config import GLADIA_API_KEY


def transcribe_audio_chunk(file_path: str) -> str:
    """
    Transcribe an audio chunk using Gladia's synchronous API.
    
    Args:
        file_path (str): Path to the audio file to transcribe
        
    Returns:
        str: The complete transcription text
        
    Raises:
        Exception: If the transcription fails
        ValueError: If file_path is invalid
        FileNotFoundError: If file doesn't exist
    """
    # Validate inputs
    if not file_path or not isinstance(file_path, str):
        raise ValueError("Invalid file_path provided")
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Audio file not found: {file_path}")
    
    # API endpoint for audio transcription
    url = "https://api.gladia.io/audio/text/audio-transcription/"
    
    # Headers with authentication
    headers = {
        "x-gladia-key": GLADIA_API_KEY,
    }
    
    # Prepare the file and parameters for the request
    with open(file_path, "rb") as audio_file:
        files = {
            "audio": (file_path, audio_file, "audio/mpeg")
        }
        
        data = {
            "speaker_diarization": "true",
            "language": "french"
        }
        
        # Send the transcription request
        response = requests.post(url, headers=headers, files=files, data=data)
        
    # Check if the request was successful
    if response.status_code != 200:
        raise Exception(f"Failed to transcribe audio: {response.status_code} - {response.text}")
    
    # Get the result data from the response
    result_data = response.json()
    
    # Extract transcription segments from prediction
    if "prediction" not in result_data:
        raise Exception(f"Prediction data not found in response: {result_data}")
    
    prediction = result_data.get("prediction", [])
    
    # Extract transcription text from each segment and concatenate
    transcription_segments = [segment.get("transcription", "") for segment in prediction]
    full_transcription = " ".join(transcription_segments)
    
    return full_transcription