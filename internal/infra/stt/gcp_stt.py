from google.cloud import speech
import io
from internal.config.config import nested_config as config

class GCP_SpeechToText:
    def __init__(self):
        self.credentials_path = config["stt"]["credentials_path"]
        self.client = speech.SpeechClient.from_service_account_file(self.credentials_path)

    def transcribe(self, audio_path: str, language_code: str):
        with io.open(audio_path, "rb") as audio_file:
            content = audio_file.read()

        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code=language_code,
        )

        response = self.client.recognize(config=config, audio=audio)
        return response.results[0].alternatives[0].transcript
