from typing import List, Optional

from google.cloud import speech

from internal.infra.log.logger import logger
from internal.config.config import nested_config as config

class GCP_SpeechToText:
    def __init__(self):
        self.client = speech.SpeechClient.from_service_account_file(config["stt"]["gcp_credentials_path"])

    def transcribe(self, curr_chunk: bytes, language_code: str, prev_transcript: Optional[str] = None) -> str:
        logger.info("[GCP_SpeechToText: transcribe] Called")

        audio = speech.RecognitionAudio(content=curr_chunk)

        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code=language_code,
            model='latest_long',
        )

        try:
            response = self.client.recognize(config=config, audio=audio, )
            logger.info(f"[GCP_SpeechToText: transcribe] Raw response: {response}")

            if not response.results or not response.results[0].alternatives:
                logger.warning("[GCP_SpeechToText: transcribe] No valid transcript found")
                return ""

            curr_transcript = response.results[0].alternatives[0].transcript.strip()

            if prev_transcript:
                logger.info(f"[GCP_SpeechToText: transcribe] Prev transcript for context (not sent to API): {prev_transcript}")

            logger.info(f"[GCP_SpeechToText: transcribe] Final transcript: {curr_transcript}")
            return curr_transcript

        except Exception as e:
            logger.error(f"[GCP_SpeechToText: transcribe] Error: {e}")
            return ""
    
    def transcribe_streaming_from_chunks(self, audio_chunks: List[bytes], language_code: str) -> str:
        logger.info("[GCP_SpeechToText: transcribe_streaming_from_chunks] Called")

        recognition_config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code=language_code,
            model='latest_long',
        )

        streaming_config = speech.StreamingRecognitionConfig(
            config=recognition_config,
            interim_results=False,
            single_utterance=False
        )

        def request_generator():
            for chunk in audio_chunks:
                yield speech.StreamingRecognizeRequest(audio_content=chunk)

        transcript = ""
        try:
            responses = self.client.streaming_recognize(streaming_config, request_generator())
            for response in responses:
                for result in response.results:
                    logger.info(f"[GCP_SpeechToText: transcribe_streaming_from_chunks] Final transcript: {result.alternatives[0].transcript}")
                    transcript += result.alternatives[0].transcript + " "
        except Exception as e:
            logger.error(f"[GCP_SpeechToText: transcribe_streaming_from_chunks] Error during streaming: {e}")
        
        return transcript.strip()

    def remove_prefix(self, text: str, prefix: str) -> str:
        if text.startswith(prefix):
            return text[len(prefix):].lstrip()
        return text


