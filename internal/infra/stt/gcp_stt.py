from google.cloud import speech
from internal.infra.log.logger import logger
from internal.config.config import nested_config as config

class GCP_SpeechToText:
    def __init__(self):
        self.client = speech.SpeechClient.from_service_account_file(config["stt"]["gcp_credentials_path"])

    def transcribe(self, audio_data: bytes, language_code: str):
        logger.info(f"[GCP_SpeechToText: transcribe] Called")
        audio = speech.RecognitionAudio(content=audio_data)
        
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code=language_code,
        )

        logger.info(f"[GCP_SpeechToText: transcribe] config: {config}")
        response = self.client.recognize(config=config, audio=audio)

        logger.info(f"[GCP_SpeechToText: transcribe] response: {response}")

        # Check if there are any results
        if not response.results:
            logger.warning(f"[GCP_SpeechToText: transcribe] No speech detected in audio")
            return ""

        # Check if the first result has alternatives
        if not response.results[0].alternatives:
            logger.warning(f"[GCP_SpeechToText: transcribe] No alternatives found in first result")
            return ""

        transcript = response.results[0].alternatives[0].transcript
        return transcript

