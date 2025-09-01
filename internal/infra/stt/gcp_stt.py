from typing import List, Optional
from google.cloud import speech, speech_v2
from google.cloud.speech_v2.types import cloud_speech
from internal.infra.log.logger import logger
from internal.config.config import nested_config as config
from typing import Generator
from internal.domain.models.speech_recognize import SpeechRecognize, Word

class GCP_SpeechToText:
    def __init__(self):
        self.client = speech.SpeechClient.from_service_account_file(config["stt"]["gcp_credentials_path"])
        self.client_v2 = speech_v2.SpeechClient.from_service_account_file(config["stt"]["gcp_credentials_path"])
        self.project_id = config["stt"]["gcp_project_id"]
        self.location = config["stt"]["gcp_location"]
        self.recognizer = f"projects/{self.project_id}/locations/global/recognizers/_"

    def transcribe_streaming_from_chunks(
        self, audio_chunks: List[bytes], language_code: str, bias_prompt: Optional[List[str]]
    ) -> str:
        logger.info("[GCP_SpeechToText: transcribe_streaming_from_chunks] Called")
        
        speech_contexts = None
        logger.info(f"[GCP_SpeechToText: transcribe_streaming_from_chunks] Bias prompt: {bias_prompt}")
        if bias_prompt:
            speech_contexts = [speech.SpeechContext(phrases=bias_prompt)]
            logger.info(f"[GCP_SpeechToText: transcribe_streaming_from_chunks] Using bias prompts: {bias_prompt}")
    
        recognition_config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code=language_code,
            model='latest_long',
            speech_contexts=speech_contexts,
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
        
    from typing import Generator

    def transcribe_streaming_from_chunks_v2(
        self, audio_chunks: List[bytes], language_code: str, bias_prompt: Optional[List[str]] = None
    ) -> SpeechRecognize:
        logger.info(f"[GCP_SpeechToTextV2] Called with {len(audio_chunks)} chunks")

        adaptation = None
        if bias_prompt:
            adaptation = cloud_speech.SpeechAdaptation(
                phrase_sets=[
                    cloud_speech.SpeechAdaptation.AdaptationPhraseSet(
                        inline_phrase_set=cloud_speech.PhraseSet(
                            phrases=[
                                cloud_speech.PhraseSet.Phrase(value=phrase, boost=20)
                                for phrase in bias_prompt
                            ]
                        )
                    )
                ]
            )

        words = []
        recognition_config = cloud_speech.RecognitionConfig(
            explicit_decoding_config=cloud_speech.ExplicitDecodingConfig(
                encoding=cloud_speech.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                audio_channel_count=1
            ),
            language_codes=[language_code],
            model="long",
            features=cloud_speech.RecognitionFeatures(
                enable_word_time_offsets=True,
                enable_word_confidence=True,
            ),
            adaptation=adaptation,
        )

        streaming_config = cloud_speech.StreamingRecognitionConfig(
            config=recognition_config
        )

        config_request = cloud_speech.StreamingRecognizeRequest(
            recognizer=self.recognizer,
            streaming_config=streaming_config,
        )

        def requests() -> Generator[cloud_speech.StreamingRecognizeRequest, None, None]:
            yield config_request
            for chunk in audio_chunks:
                for sliced_chunk in self.slice_audio_chunks(chunk):
                    logger.info(f"[GCP_SpeechToTextV2] Yielding audio slice (≤25600 bytes)")
                    yield cloud_speech.StreamingRecognizeRequest(audio=sliced_chunk)

        transcript = ""
        try:
            responses_iterator = self.client_v2.streaming_recognize(requests=requests())
            for response in responses_iterator:
                for result in response.results:
                    transcript += result.alternatives[0].transcript + " "
                    
                    for word_info in result.alternatives[0].words:
                        word = word_info.word
                        start = word_info.start_offset.total_seconds()
                        end = word_info.end_offset.total_seconds()
                        confidence = word_info.confidence
                        logger.info(f"[GCP_SpeechToTextV2] Word: '{word}' | Start: {start:.2f}s | End: {end:.2f}s | Confidence: {confidence:.2f}")
                        words.append(
                            Word(word=word, start=start, end=end, confidence=confidence)
                        )

        except Exception as e:
            logger.error(f"[GCP_SpeechToTextV2] Error: {e}")

        logger.info(f"[GCP_SpeechToTextV2] Final Transcript: {transcript.strip()}")
        result = SpeechRecognize(transcript=transcript.strip(), words=words)
        return result

    def slice_audio_chunks(self, large_chunk: bytes) -> list[bytes]:
        SAMPLE_WIDTH = 2
        MAX_CHUNK_SIZE = 25600
        aligned_size = MAX_CHUNK_SIZE - (MAX_CHUNK_SIZE % SAMPLE_WIDTH)

        return [
            large_chunk[i:i + aligned_size]
            for i in range(0, len(large_chunk), aligned_size)
        ]


