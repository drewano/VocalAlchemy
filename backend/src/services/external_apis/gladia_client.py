import requests
import os
import time
import mimetypes
import logging
from typing import Optional


class GladiaClient:
    def __init__(self, api_key: str) -> None:
        if not api_key or not isinstance(api_key, str):
            raise ValueError("Invalid Gladia API key provided")
        self.api_key = api_key
        self.base_url = "https://api.gladia.io"

    def transcribe_audio_chunk(self, file_path: str, timeout_seconds: int = 3600) -> str:
        """
        Transcribe an audio chunk using Gladia's asynchronous API V2.

        Flow:
          1) Upload file to /v2/upload to get an audio_url
          2) Start transcription via POST /v2/pre-recorded with requested config
          3) Poll the returned result_url until status == "done" within timeout_seconds
          4) Build final transcript from result['transcription']['utterances'] as
             lines "SPEAKER {speaker}: {text}"
        """
        if not file_path or not isinstance(file_path, str):
            raise ValueError("Invalid file_path provided")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        headers = {"x-gladia-key": self.api_key}

        # Step 1: Upload
        upload_url = f"{self.base_url}/v2/upload"
        try:
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type is None:
                mime_type = "application/octet-stream"
            with open(file_path, "rb") as f:
                files = {"audio": (os.path.basename(file_path), f, mime_type)}
                upload_resp = requests.post(upload_url, headers=headers, files=files)
        except Exception as e:
            raise Exception(f"Failed to upload audio file: {e}")

        if upload_resp.status_code != 200:
            raise Exception(
                f"Failed to upload audio: {upload_resp.status_code} - {upload_resp.text}"
            )
        try:
            upload_json = upload_resp.json()
            audio_url = upload_json.get("audio_url") or upload_json.get("url")
        except Exception:
            raise Exception(f"Invalid upload response: {upload_resp.text}")
        if not audio_url:
            raise Exception(f"audio_url not found in upload response: {upload_resp.text}")

        # Step 2: Start transcription
        start_url = f"{self.base_url}/v2/pre-recorded"
        payload = {
            "audio_url": audio_url,
            "diarization": True,
            "punctuation_enhanced": True,
            "detect_language": True,
            "language": "fr",
        }
        start_headers = {
            "x-gladia-key": self.api_key,
            "Content-Type": "application/json",
        }
        start_resp = requests.post(start_url, headers=start_headers, json=payload)
        if start_resp.status_code not in (200, 201, 202):
            raise Exception(
                f"Failed to start transcription: {start_resp.status_code} - {start_resp.text}"
            )
        try:
            start_json = start_resp.json()
            result_url = start_json.get("result_url") or start_json.get("url")
        except Exception:
            raise Exception(f"Invalid start response: {start_resp.text}")
        if not result_url:
            raise Exception(f"result_url not found in start response: {start_resp.text}")

        # Step 3: Polling with timeout window
        attempts = 0
        final_json = None
        start_poll_time = time.time()
        while time.time() - start_poll_time < timeout_seconds:
            attempts += 1
            poll_resp = requests.get(result_url, headers=headers)
            if poll_resp.status_code != 200:
                logging.info(f"Polling Gladia ({attempts} attempts)... Non-200 response: {poll_resp.status_code}")
                time.sleep(15)
                continue
            try:
                poll_json = poll_resp.json()
            except Exception:
                logging.info(f"Polling Gladia ({attempts} attempts)... Invalid JSON response")
                time.sleep(15)
                continue

            status = poll_json.get("status")
            logging.info(f"Polling Gladia ({attempts} attempts)... Status: {status}")
            if status == "done":
                final_json = poll_json
                break
            elif status in {"error", "failed"}:
                raise Exception(f"Transcription failed: {poll_json}")

            time.sleep(15)

        if final_json is None:
            raise Exception(f"Timeout after {timeout_seconds} seconds while waiting for transcription result.")

        # Step 4: Build final transcript from utterances
        result_data = final_json.get("result", {})
        transcription_data = result_data.get("transcription", {})
        utterances = transcription_data.get("utterances", [])

        # Safety fallback to full_transcript when utterances are missing
        if not utterances and transcription_data.get("full_transcript"):
            return transcription_data["full_transcript"]

        lines = []
        for utt in utterances:
            speaker = utt.get("speaker")
            text = utt.get("text") or ""
            # Normalize speaker label
            if speaker is None:
                speaker_label = "SPEAKER ?"
            else:
                speaker_label = f"SPEAKER {speaker}"
            lines.append(f"{speaker_label}: {text}".strip())

        return "\n".join(lines)