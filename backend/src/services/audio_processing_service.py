import logging
import os
import tempfile
from pydub import AudioSegment

from .blob_storage_service import BlobStorageService


class FFmpegError(Exception):
    pass


class AudioProcessingService:
    def __init__(self, blob_storage_service: BlobStorageService) -> None:
        self.blob_storage_service = blob_storage_service

    async def normalize_audio(self, source_blob_name: str, normalized_blob_name: str) -> None:
        """
        Normalize audio using pydub with temporary files.
        Converts audio to WAV (PCM s16le) 16kHz mono format.
        """
        source_suffix = os.path.splitext(source_blob_name)[1] or ".tmp"
        output_suffix = ".wav"

        source_temp = tempfile.NamedTemporaryFile(delete=False, suffix=source_suffix)
        output_temp = tempfile.NamedTemporaryFile(delete=False, suffix=output_suffix)
        source_path = source_temp.name
        output_path = output_temp.name
        # Close immediately so we can reopen on Windows
        source_temp.close()
        output_temp.close()

        try:
            # Download source blob to temporary file
            with open(source_path, "wb") as f:
                async for chunk in self.blob_storage_service.download_blob_as_stream(source_blob_name):
                    f.write(chunk)

            # Convert using pydub
            try:
                sound = AudioSegment.from_file(source_path)
                sound = (
                    sound.set_frame_rate(16000)
                         .set_channels(1)
                         .set_sample_width(2)
                )
                sound.export(output_path, format="wav")
            except Exception as e:
                raise FFmpegError(f"Audio conversion failed with pydub: {e}") from e

            # Upload normalized file to blob storage
            file_size = os.path.getsize(output_path)
            with open(output_path, "rb") as f:
                await self.blob_storage_service.upload_blob_from_stream(
                    f, normalized_blob_name, length=file_size
                )
        finally:
            # Cleanup temporary files
            for path in (source_path, output_path):
                try:
                    os.remove(path)
                except Exception:
                    pass