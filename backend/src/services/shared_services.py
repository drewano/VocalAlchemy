from functools import lru_cache
from fastapi import Depends

from src.config import settings
from src.services.blob_storage_service import BlobStorageService
from src.services.external_apis.azure_speech_client import AzureSpeechClient
from src.services.external_apis.litellm_ai_processor import LiteLLMAIProcessor


@lru_cache()
def get_blob_storage_service() -> BlobStorageService:
    return BlobStorageService(
        storage_connection_string=settings.AZURE_STORAGE_CONNECTION_STRING,
        storage_container_name=settings.AZURE_STORAGE_CONTAINER_NAME,
    )


def get_transcriber(blob_storage_service: BlobStorageService) -> AzureSpeechClient:
    return AzureSpeechClient(
        api_key=settings.AZURE_SPEECH_KEY,
        region=settings.AZURE_SPEECH_REGION,
        blob_storage_service=blob_storage_service,
    )


def get_ai_analyzer() -> LiteLLMAIProcessor:
    return LiteLLMAIProcessor(model_name=settings.AZURE_AI_MODEL_NAME)