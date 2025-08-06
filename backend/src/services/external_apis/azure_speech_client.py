import os
import logging
from typing import List

import azure.cognitiveservices.speech as speechsdk


class AzureSpeechClient:
    def __init__(self, api_key: str, region: str) -> None:
        if not api_key or not isinstance(api_key, str):
            raise ValueError("Invalid Azure Speech API key provided")
        if not region or not isinstance(region, str):
            raise ValueError("Invalid Azure Speech region provided")
        self.api_key = api_key
        self.region = region

    def transcribe_audio_chunk(self, file_path: str) -> str:
        if not file_path or not isinstance(file_path, str):
            raise ValueError("Invalid file_path provided")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Audio file not found: {file_path}")

        try:
            speech_config = speechsdk.SpeechConfig(subscription=self.api_key, region=self.region)
            # Enable diarization explicitly
            speech_config.set_property(speechsdk.PropertyId.SpeechServiceResponse_ProfanityOption, "raw")

            audio_config = speechsdk.audio.AudioConfig(filename=file_path)

            # ConversationTranscriber supports diarization and speaker separation
            transcriber = speechsdk.transcription.ConversationTranscriber(speech_config=speech_config, audio_config=audio_config)

            lines: List[str] = []
            done = False

            def handle_transcribed(evt: speechsdk.SpeechRecognitionEventArgs):
                # evt.result has .text and .speaker_id (for conversation transcriber)
                try:
                    result = evt.result
                    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                        speaker_id = getattr(result, 'speaker_id', None)
                        text = result.text or ""
                        speaker_label = f"SPEAKER {speaker_id}" if speaker_id is not None else "SPEAKER ?"
                        if text:
                            lines.append(f"{speaker_label}: {text}")
                except Exception as e:
                    logging.error(f"Error in transcribed handler: {e}")

            def handle_canceled(evt: speechsdk.SessionEventArgs):
                nonlocal done
                logging.error(f"Azure transcription canceled: {getattr(evt, 'reason', 'unknown')}")
                done = True

            def handle_session_stopped(evt: speechsdk.SessionEventArgs):
                nonlocal done
                done = True

            transcriber.transcribed.connect(handle_transcribed)
            transcriber.canceled.connect(handle_canceled)
            transcriber.session_stopped.connect(handle_session_stopped)

            transcriber.start_transcribing_async().get()

            # Block until session_stopped or canceled marks done
            while not done:
                # Use a small wait on an async stop
                # The SDK raises events; we spin until stopped
                import time
                time.sleep(0.1)

            transcriber.stop_transcribing_async().get()

            return "\n".join(lines)
        except Exception as e:
            logging.error(f"Azure Speech transcription failed for file {file_path}: {e}")
            raise
