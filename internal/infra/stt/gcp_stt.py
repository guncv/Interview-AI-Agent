from typing import List
from google.cloud import speech_v2, speech
from internal.infra.log.logger import logger
from internal.config.config import nested_config as config

class GCP_SpeechToText:
    def __init__(self):
        self.client = speech.SpeechClient.from_service_account_file(config["stt"]["gcp_credentials_path"])
        self.client_v2 = speech_v2.SpeechClient.from_service_account_file(config["stt"]["gcp_credentials_path"])
        self.project_id = config["stt"]["gcp_project_id"]
        self.location = config["stt"]["gcp_location"]
        self.recognizer = f"projects/{self.project_id}/locations/{self.location}/recognizers/_"

    def transcribe_streaming_from_chunks(
        self, audio_chunks: List[bytes], language_code: str
    ) -> str:
        logger.info("[GCP_SpeechToText: transcribe_streaming_from_chunks] Called")
        
        recognition_config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code=language_code,
            model='latest_long', )
        
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
            responses = self.client.streaming_recognize(
                streaming_config, request_generator()
            )
            for response in responses:
                for result in response.results:
                    logger.info(f"[GCP_SpeechToText: transcribe_streaming_from_chunks] Final transcript: {result.alternatives[0].transcript}")
                    transcript += result.alternatives[0].transcript + " "
        except Exception as e:
            logger.error(f"[GCP_SpeechToText: transcribe_streaming_from_chunks] Error during streaming: {e}")
        
        return transcript.strip()
        
    def transcribe_streaming_from_chunks_v2(
        self, audio_chunks: List[bytes], language_code: str
    ) -> str:
        logger.info(f"[GCP_SpeechToTextV2: transcribe_streaming_from_chunks_v2] Called with {len(audio_chunks)} chunks")

        if not audio_chunks or len(audio_chunks) == 0:
            logger.error("[GCP_SpeechToTextV2: transcribe_streaming_from_chunks_v2] No audio chunks provided")
            return ""

        total_size = sum(len(chunk) for chunk in audio_chunks if chunk)
        logger.info(f"[GCP_SpeechToTextV2: transcribe_streaming_from_chunks_v2] Total audio size: {total_size} bytes")

        recognition_config = speech_v2.RecognitionConfig(
            auto_decoding_config=speech_v2.AutoDetectDecodingConfig(),
            language_codes=[language_code],
            model="long",
            features=speech_v2.RecognitionFeatures(
                enable_word_time_offsets=True,
                enable_word_confidence=True,
            ),
        )

        streaming_config = speech_v2.StreamingRecognitionConfig(
            config=recognition_config
        )
        logger.info(f"[GCP_SpeechToTextV2] Streaming config created")

        logger.info(f"[GCP_SpeechToTextV2] Recognizer: {self.recognizer}")
        def request_generator():
            logger.info("[GCP_SpeechToTextV2] Yielding initial config request")
            yield speech_v2.StreamingRecognizeRequest(
                streaming_config=streaming_config,
            )
            for i, chunk in enumerate(audio_chunks):
                if chunk is None or len(chunk) == 0:
                    logger.warning(f"[GCP_SpeechToTextV2] Skipping empty chunk at index {i}")
                    continue
                logger.info(f"[GCP_SpeechToTextV2] Yielding audio chunk {i} with size {len(chunk)}")
                yield speech_v2.StreamingRecognizeRequest(
                    audio=speech_v2.RecognitionAudio(content=chunk)
                )

        transcript = ""
        try:
            responses = self.client_v2.streaming_recognize(requests=request_generator())
            for response in responses:
                for result in response.results:
                    alt = result.alternatives[0]
                    logger.info(
                        f"[GCP_SpeechToTextV2] Final transcript: {alt.transcript} "
                        f"(confidence={alt.confidence:.2f})"
                    )
                    transcript += alt.transcript + " "
        except Exception as e:
            logger.error(
                f"[GCP_SpeechToTextV2: transcribe_streaming_from_chunks_v2] Error: {e}"
            )

        return transcript.strip()
