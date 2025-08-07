import logging
from datetime import datetime, timedelta, timezone
from typing import Union, AsyncIterator

from azure.storage.blob.aio import BlobServiceClient
from azure.storage.blob import (
    BlobSasPermissions,
    generate_blob_sas,
)
from azure.storage.blob import ContentSettings
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError


class BlobStorageService:
    def __init__(
        self,
        storage_connection_string: str,
        storage_container_name: str,
    ) -> None:
        if not storage_connection_string or not isinstance(storage_connection_string, str):
            raise ValueError("Invalid Azure Storage connection string provided")
        if not storage_container_name or not isinstance(storage_container_name, str):
            raise ValueError("Invalid Azure Storage container name provided")

        self.storage_connection_string = storage_connection_string
        self.storage_container_name = storage_container_name

        # Initialize async blob service and container client (no awaited calls here)
        self._blob_service = BlobServiceClient.from_connection_string(storage_connection_string)
        self._container_client = self._blob_service.get_container_client(storage_container_name)
        # Container creation is async; caller should ensure to call `ensure_container_exists` once.

    async def ensure_container_exists(self) -> None:
        try:
            await self._container_client.create_container()
        except ResourceExistsError:
            pass

    async def upload_blob(self, content: Union[str, bytes, bytearray], blob_name: str, sas_ttl_hours: int = 24) -> str:
        """
        Upload content to a blob and return a SAS URL with read permission.
        If content is a string, it is encoded in UTF-8 before upload.
        """
        if isinstance(content, str):
            data: bytes = content.encode("utf-8")
        elif isinstance(content, (bytes, bytearray)):
            data = bytes(content)
        else:
            raise ValueError("content must be of type str, bytes or bytearray")

        if not blob_name or not isinstance(blob_name, str):
            raise ValueError("Invalid blob_name provided")

        blob_client = self._container_client.get_blob_client(blob_name)
        content_settings = None
        lower = blob_name.lower()
        if lower.endswith(".flac"):
            content_settings = ContentSettings(content_type="audio/flac")
        elif lower.endswith(".wav"):
            content_settings = ContentSettings(content_type="audio/wav")
        await blob_client.upload_blob(data, overwrite=True, content_settings=content_settings)

        # Build SAS with read permission
        account_name = self._blob_service.account_name
        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=self.storage_container_name,
            blob_name=blob_name,
            account_key=self._blob_service.credential.account_key,  # type: ignore[attr-defined]
            permission=BlobSasPermissions(read=True),
            expiry=datetime.now(timezone.utc) + timedelta(hours=sas_ttl_hours),
        )
        return f"{blob_client.url}?{sas_token}"

    async def get_blob_sas_url(self, blob_name: str, ttl_hours: int = 1) -> str:
        if not blob_name or not isinstance(blob_name, str):
            raise ValueError("Invalid blob_name provided")
        blob_client = self._container_client.get_blob_client(blob_name)
        account_name = self._blob_service.account_name
        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=self.storage_container_name,
            blob_name=blob_name,
            account_key=self._blob_service.credential.account_key,  # type: ignore[attr-defined]
            permission=BlobSasPermissions(read=True),
            expiry=datetime.now(timezone.utc) + timedelta(hours=ttl_hours),
        )
        return f"{blob_client.url}?{sas_token}"

    async def get_blob_upload_sas_url(self, blob_name: str, ttl_minutes: int = 60) -> str:
        if not blob_name or not isinstance(blob_name, str):
            raise ValueError("Invalid blob_name provided")
        blob_client = self._container_client.get_blob_client(blob_name)
        account_name = self._blob_service.account_name
        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=self.storage_container_name,
            blob_name=blob_name,
            account_key=self._blob_service.credential.account_key,  # type: ignore[attr-defined]
            permission=BlobSasPermissions(create=True, write=True),
            expiry=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
        )
        return f"{blob_client.url}?{sas_token}"

    async def delete_blob(self, blob_name: str) -> None:
        if not blob_name or not isinstance(blob_name, str):
            raise ValueError("Invalid blob_name provided")
        blob_client = self._container_client.get_blob_client(blob_name)
        try:
            await blob_client.delete_blob()
        except ResourceNotFoundError:
            logging.warning(f"Blob not found for deletion: {blob_name}")
        except Exception as e:
            logging.error(f"Unexpected error deleting blob '{blob_name}': {e}")
            raise

    async def download_blob_as_text(self, blob_name: str) -> str:
        if not blob_name or not isinstance(blob_name, str):
            raise ValueError("Invalid blob_name provided")
        blob_client = self._container_client.get_blob_client(blob_name)
        try:
            stream = await blob_client.download_blob()
            data = await stream.readall()
            return data.decode("utf-8")
        except ResourceNotFoundError:
            logging.error(f"Blob not found for download: {blob_name}")
            raise
        except Exception:
            # Let unexpected exceptions bubble up for caller handling
            raise

    async def upload_blob_from_stream(self, stream: any, blob_name: str, length: int) -> None:
        if not blob_name or not isinstance(blob_name, str):
            raise ValueError("Invalid blob_name provided")
        if not isinstance(length, int) or length < 0:
            raise ValueError("Invalid length provided")
        blob_client = self._container_client.get_blob_client(blob_name)
        await blob_client.upload_blob(stream, length=length, overwrite=True)

    async def download_blob_as_bytes(self, blob_name: str) -> bytes:
        if not blob_name or not isinstance(blob_name, str):
            raise ValueError("Invalid blob_name provided")
        blob_client = self._container_client.get_blob_client(blob_name)
        try:
            stream = await blob_client.download_blob()
            data = await stream.readall()
            return data
        except ResourceNotFoundError:
            logging.error(f"Blob not found for download: {blob_name}")
            raise
        except Exception:
            # Let unexpected exceptions bubble up for caller handling
            raise

    async def download_blob_as_stream(self, blob_name: str) -> AsyncIterator[bytes]:
        """
        Download a blob as a stream of bytes chunks.
        Returns an async iterator that yields bytes chunks.
        """
        if not blob_name or not isinstance(blob_name, str):
            raise ValueError("Invalid blob_name provided")
        blob_client = self._container_client.get_blob_client(blob_name)
        try:
            stream = await blob_client.download_blob()
            async for chunk in stream.chunks():
                yield chunk
        except ResourceNotFoundError:
            logging.error(f"Blob not found for download: {blob_name}")
            raise
        except Exception:
            # Let unexpected exceptions bubble up for caller handling
            raise

    async def upload_blob_from_generator(self, generator: AsyncIterator[bytes], blob_name: str) -> None:
        """
        Upload blob content from an async generator/iterator of bytes chunks.
        The total size of the stream is unknown, so no length parameter is passed.
        """
        if not blob_name or not isinstance(blob_name, str):
            raise ValueError("Invalid blob_name provided")
        blob_client = self._container_client.get_blob_client(blob_name)
        content_settings = None
        lower = blob_name.lower()
        if lower.endswith(".flac"):
            content_settings = ContentSettings(content_type="audio/flac")
        elif lower.endswith(".wav"):
            content_settings = ContentSettings(content_type="audio/wav")
        await blob_client.upload_blob(generator, overwrite=True, content_settings=content_settings)
