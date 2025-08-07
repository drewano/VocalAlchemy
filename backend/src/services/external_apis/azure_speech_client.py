import os
import logging
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import requests
from azure.storage.blob import (
    BlobServiceClient,
    BlobSasPermissions,
    generate_blob_sas,
)
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError


class AzureSpeechClient:
    def __init__(
        self,
        api_key: str,
        region: str,
        storage_connection_string: str,
        storage_container_name: str,
    ) -> None:
        # Validate inputs
        if not api_key or not isinstance(api_key, str):
            raise ValueError("Invalid Azure Speech API key provided")
        if not region or not isinstance(region, str):
            raise ValueError("Invalid Azure Speech region provided")
        if not storage_connection_string or not isinstance(storage_connection_string, str):
            raise ValueError("Invalid Azure Storage connection string provided")
        if not storage_container_name or not isinstance(storage_container_name, str):
            raise ValueError("Invalid Azure Storage container name provided")

        self.api_key = api_key
        self.region = region
        self.storage_connection_string = storage_connection_string
        self.storage_container_name = storage_container_name

        # Initialize blob service and ensure container exists
        self._blob_service = BlobServiceClient.from_connection_string(storage_connection_string)
        self._container_client = self._blob_service.get_container_client(storage_container_name)
        try:
            self._container_client.create_container()
        except ResourceExistsError:
            # Container already exists, ignore
            pass

        self._speech_base_url = f"https://{self.region}.api.cognitive.microsoft.com/speechtotext/v3.1"

    def delete_blob(self, blob_name: str) -> None:
        if not blob_name or not isinstance(blob_name, str):
            raise ValueError("Invalid blob_name provided")
        blob_client = self._container_client.get_blob_client(blob_name)
        try:
            blob_client.delete_blob()
        except ResourceNotFoundError:
            logging.warning(f"Blob not found for deletion: {blob_name}")
        except Exception as e:
            # Log and re-raise unexpected errors to avoid masking issues
            logging.error(f"Unexpected error deleting blob '{blob_name}': {e}")
            raise

    def _upload_audio_to_blob(self, file_content: bytes, blob_name: str, sas_ttl_hours: int = 24) -> str:
        if not isinstance(file_content, (bytes, bytearray)) or len(file_content) == 0:
            raise ValueError("Invalid file_content provided")
        if not blob_name or not isinstance(blob_name, str):
            raise ValueError("Invalid blob_name provided")

        blob_client = self._container_client.get_blob_client(blob_name)
        blob_client.upload_blob(file_content, overwrite=True)

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
        sas_url = f"{blob_client.url}?{sas_token}"
        return sas_url

    def get_blob_sas_url(self, blob_name: str, ttl_hours: int = 1) -> str:
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

    def submit_batch_transcription(self, file_content: bytes, original_filename: str, blob_name: str) -> str:
        """
        Soumet un job de transcription par lot, optimisé pour la vitesse avec le français comme langue par défaut.
        """
        if not isinstance(file_content, (bytes, bytearray)) or len(file_content) == 0:
            raise ValueError("Invalid file_content provided")
        if not original_filename or not isinstance(original_filename, str):
            raise ValueError("Invalid original_filename provided")
        if not blob_name or not isinstance(blob_name, str):
            raise ValueError("Invalid blob_name provided")

        audio_sas_url = self._upload_audio_to_blob(file_content, blob_name)

        logging.info("Submitting transcription with 'fr-FR' locale for maximum speed.")

        # Build payload for batch transcription, optimized for speed.
        payload: Dict = {
            "displayName": f"Transcription-{uuid.uuid4()}",
            "description": "Batch transcription via API",
            
            # OPTIMISATION 1: Spécifier la langue directement.
            # On supprime la détection automatique qui est lente.
            "locale": "fr-FR",
            
            "contentUrls": [audio_sas_url],
            "properties": {
                # OPTIMISATION 2: On garde UNIQUEMENT les fonctionnalités nécessaires.
                # La diarisation est conservée car utile pour les réunions.
                # Si vous n'en avez pas besoin, mettez-la à False pour un gain de vitesse.
                "diarizationEnabled": True, 
                # wordLevelTimestampsEnabled est utile mais a un coût. Mettez à False si non essentiel.
                "wordLevelTimestampsEnabled": True,
                "punctuationMode": "DictatedAndAutomatic",
                "profanityFilterMode": "Masked",
            },
        }

        url = f"{self._speech_base_url}/transcriptions"
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Content-Type": "application/json",
        }
        resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
        
        if resp.status_code not in [201, 202]:
            raise RuntimeError(
                f"Failed to submit transcription. Expected status 201 or 202, but got {resp.status_code}. Body: {resp.text}"
            )
        
        location = resp.headers.get("Location")
        if not location:
            raise RuntimeError("Missing Location header on response from transcription submit")
        return location

    def check_transcription_status(self, status_url: str) -> dict:
        if not status_url or not isinstance(status_url, str):
            raise ValueError("Invalid status_url provided")
        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        resp = requests.get(status_url, headers=headers, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(
                f"Failed to get transcription status. status={resp.status_code}, body={resp.text}"
            )
        return resp.json()

    def get_transcription_files(self, status_url: str) -> dict:
        if not status_url or not isinstance(status_url, str):
            raise ValueError("Invalid status_url provided")
        url = f"{status_url}/files"
        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(
                f"Failed to get transcription files. status={resp.status_code}, body={resp.text}"
            )
        return resp.json()

    def get_transcription_result(self, files_response: dict) -> str:
        if not isinstance(files_response, dict):
            raise ValueError("files_response must be a dict")

        # Find the JSON result file URL from the files list by kind == "Transcription"
        files = files_response.get("values") or files_response.get("files") or []
        result_url: Optional[str] = None
        for f in files:
            if not isinstance(f, dict):
                continue
            if f.get("kind") == "Transcription":
                content_url = f.get("links", {}).get("contentUrl") or f.get("contentUrl")
                if content_url:
                    result_url = content_url
                    break

        if not result_url:
            raise RuntimeError("No Transcription result file found in files response")

        # Download the result JSON
        result_resp = requests.get(result_url, timeout=60)
        if result_resp.status_code != 200:
            raise RuntimeError(
                f"Failed to download result JSON. status={result_resp.status_code}, body={result_resp.text}"
            )
        result_json = result_resp.json()

        # result_json structure typically: { "recognizedPhrases": [ { "speaker": 1, "nBest": [ { "display": "..." } ] } ] }
        lines: List[str] = []
        phrases = result_json.get("recognizedPhrases") or []
        for p in phrases:
            try:
                speaker = p.get("speaker")
                nbest = p.get("nBest") or []
                display_text = None
                if nbest and isinstance(nbest[0], dict):
                    display_text = nbest[0].get("display") or nbest[0].get("lexical") or ""
                if display_text:
                    speaker_label = f"SPEAKER {speaker}" if speaker is not None else "SPEAKER ?"
                    lines.append(f"{speaker_label}: {display_text}")
            except Exception as e:
                logging.error(f"Error parsing recognized phrase: {e}")

        return "\n".join(lines)