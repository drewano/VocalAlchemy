import asyncio
import io
import os
import tempfile
from pydub import AudioSegment

from .blob_storage_service import BlobStorageService


class FFmpegError(Exception):
    pass


class AudioProcessingService:
    def __init__(self, blob_storage_service: BlobStorageService) -> None:
        self.blob_storage_service = blob_storage_service

    def _blocking_audio_conversion(self, source_bytes: bytes) -> tuple[bytes, int]:
        """
        Synchronous method to handle blocking file operations for audio conversion.
        """
        source_temp = tempfile.NamedTemporaryFile(delete=False)
        output_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".flac")
        source_path = source_temp.name
        output_path = output_temp.name
        # Close immediately so we can reopen on Windows
        source_temp.close()
        output_temp.close()

        try:
            # Write source bytes to temporary file
            with open(source_path, "wb") as f:
                f.write(source_bytes)

            # Convert using pydub
            try:
                sound = AudioSegment.from_file(source_path)
                sound = sound.set_frame_rate(16000).set_channels(1).set_sample_width(2)
                sound.export(output_path, format="flac")
            except Exception as e:
                raise FFmpegError(f"Audio conversion failed with pydub: {e}") from e

            # Read the converted file
            with open(output_path, "rb") as f:
                output_bytes = f.read()

            # Get file size
            file_size = os.path.getsize(output_path)

            return output_bytes, file_size
        finally:
            # Cleanup temporary files
            for path in (source_path, output_path):
                try:
                    os.remove(path)
                except Exception:
                    pass

    async def normalize_audio(
        self, source_blob_name: str, normalized_blob_name: str
    ) -> None:
        """
        Normalize audio using pydub with temporary files.
        Converts audio to FLAC 16kHz mono format.
        """
        # Download source blob to bytes
        source_data = await self.blob_storage_service.download_blob_as_bytes(
            source_blob_name
        )

        # Run blocking audio conversion in a separate thread
        converted_bytes, file_size = await asyncio.to_thread(
            self._blocking_audio_conversion, source_bytes=source_data
        )

        # Prepare stream for upload
        output_stream = io.BytesIO(converted_bytes)

        # Upload result to destination blob
        await self.blob_storage_service.upload_blob_from_stream(
            output_stream, normalized_blob_name, length=file_size
        )
