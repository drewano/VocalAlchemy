import requests
import os
from typing import Optional


class GladiaClient:
    def __init__(self, api_key: str) -> None:
        if not api_key or not isinstance(api_key, str):
            raise ValueError("Invalid Gladia API key provided")
        self.api_key = api_key
        self.base_url = "https://api.gladia.io"

    def transcribe_audio_chunk(self, file_path: str) -> str:
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
        if not file_path or not isinstance(file_path, str):
            raise ValueError("Invalid file_path provided")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        url = f"{self.base_url}/audio/text/audio-transcription/"
        headers = {"x-gladia-key": self.api_key}

        with open(file_path, "rb") as audio_file:
            files = {"audio": (file_path, audio_file, "audio/mpeg")}
            data = {"speaker_diarization": "true", "language": "french"}
            response = requests.post(url, headers=headers, files=files, data=data)

        if response.status_code != 200:
            raise Exception(
                f"Failed to transcribe audio: {response.status_code} - {response.text}"
            )

        result_data = response.json()
        if "prediction" not in result_data:
            raise Exception(f"Prediction data not found in response: {result_data}")

        prediction = result_data.get("prediction", [])
        transcription_segments = [segment.get("transcription", "") for segment in prediction]
        return " ".join(transcription_segments)