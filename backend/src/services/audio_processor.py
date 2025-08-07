import os
import logging
from pydub import AudioSegment


def normalize_audio_for_azure(input_path: str, output_path: str) -> str:
    """
    Normalize audio for Azure Speech service requirements:
    - ensure mono channel
    - resample to 16 kHz
    - export as WAV
    Returns the output_path on success.
    """
    if not input_path or not isinstance(input_path, str) or not os.path.exists(input_path):
        raise ValueError(f"Invalid input_path provided: {input_path}")
    if not output_path or not isinstance(output_path, str):
        raise ValueError("Invalid output_path provided")

    logging.info(f"Starting audio normalization for Azure: input={input_path}, output={output_path}")

    try:
        segment = AudioSegment.from_file(input_path)
    except Exception as exc:
        logging.error(f"Failed to load audio with pydub from {input_path}: {exc}")
        raise ValueError(f"Failed to load audio file: {exc}")

    # Convert to mono and 16 kHz
    normalized = segment.set_channels(1).set_frame_rate(16000)

    # Ensure destination directory exists
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    # Export as WAV
    normalized.export(output_path, format="wav")

    logging.info(f"Audio normalization completed: {output_path}")
    return output_path
