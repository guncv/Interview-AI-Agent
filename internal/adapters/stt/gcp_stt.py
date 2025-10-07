from typing import List, Optional, Generator, Tuple
from google.cloud import speech_v2
from google.cloud.speech_v2.types import cloud_speech
from internal.adapters.log.logger import logger
from internal.config.config import nested_config as config
from internal.domain.models.speech_recognize import SpeechRecognize, Word
from internal.domain.ports.stt_port import STTPort

class GCP_SpeechToText(STTPort):
    def __init__(self):
        self.client_v2 = speech_v2.SpeechClient.from_service_account_file(
            config["stt"]["gcp_credentials_path"]
        )
        self.project_id = config["stt"]["gcp_project_id"]
        self.location = config["stt"]["gcp_location"]
        self.recognizer = f"projects/{self.project_id}/locations/global/recognizers/_"

    async def transcribe(
        self,
        prev_chunk: bytes,
        curr_chunk: bytes,
        language_code: str,
        bias_prompt: Optional[List[str]] = None,
    ) -> Tuple[SpeechRecognize, SpeechRecognize]:

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

        recognition_config = cloud_speech.RecognitionConfig(
            explicit_decoding_config=cloud_speech.ExplicitDecodingConfig(
                encoding=cloud_speech.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                audio_channel_count=1,
            ),
            language_codes=[language_code],
            model="long",
            features=cloud_speech.RecognitionFeatures(
                enable_word_time_offsets=True,
                enable_word_confidence=True,
            ),
            adaptation=adaptation,
        )

        streaming_config = cloud_speech.StreamingRecognitionConfig(config=recognition_config)
        config_request = cloud_speech.StreamingRecognizeRequest(
            recognizer=self.recognizer,
            streaming_config=streaming_config,
        )

        def requests() -> Generator[cloud_speech.StreamingRecognizeRequest, None, None]:
            yield config_request
            for chunk in self.slice_audio_chunks(prev_chunk + curr_chunk):
                yield cloud_speech.StreamingRecognizeRequest(audio=chunk)

        words = []
        transcript = ""

        try:
            responses_iterator = self.client_v2.streaming_recognize(requests=requests())
            for response in responses_iterator:
                for result in response.results:

                    best = result.alternatives[0]
                    transcript += best.transcript + " "

                    for word_info in best.words:
                        words.append(
                            Word(
                                word=word_info.word,
                                start=word_info.start_offset.total_seconds(),
                                end=word_info.end_offset.total_seconds(),
                                confidence=word_info.confidence,
                            )
                        )

        except Exception as e:
            logger.error(f"[GCP_SpeechToTextV2] Error: {e}")


        prev_duration = len(prev_chunk) / (16000 * 2)
        tolerance = 0.05
        prev_words, curr_words = self.split_words_by_overlap(words, prev_duration, tolerance)

        prev_text = " ".join(w.word for w in prev_words)
        curr_text = " ".join(w.word for w in curr_words)

        return (
            SpeechRecognize(transcript=prev_text, words=prev_words),
            SpeechRecognize(transcript=curr_text, words=curr_words),
        )

    def slice_audio_chunks(self, large_chunk: bytes) -> List[bytes]:
        SAMPLE_WIDTH = 2
        MAX_CHUNK_SIZE = 25600
        aligned_size = MAX_CHUNK_SIZE - (MAX_CHUNK_SIZE % SAMPLE_WIDTH)

        return [
            large_chunk[i:i + aligned_size]
            for i in range(0, len(large_chunk), aligned_size)
        ]

    def split_words_by_overlap(
        self, words: List[Word], boundary: float, tolerance: float = 0.05
    ) -> Tuple[List[Word], List[Word]]:
        prev_words, curr_words = [], []
        for w in words:
            if w.end <= boundary - tolerance:
                prev_words.append(w)
            elif w.start >= boundary + tolerance:
                curr_words.append(w)
            else:
                left_overlap = max(0.0, min(boundary, w.end) - w.start)
                right_overlap = max(0.0, w.end - max(boundary, w.start))
                (prev_words if left_overlap > right_overlap else curr_words).append(w)
        return prev_words, curr_words

    def transcribe_single_chunk(
        self,
        audio_chunk: bytes,
        language_code: str,
        bias_prompt: Optional[List[str]] = None,
    ) -> SpeechRecognize:

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

        recognition_config = cloud_speech.RecognitionConfig(
            explicit_decoding_config=cloud_speech.ExplicitDecodingConfig(
                encoding=cloud_speech.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                audio_channel_count=1,
            ),
            language_codes=[language_code],
            model="long",
            features=cloud_speech.RecognitionFeatures(
                enable_word_time_offsets=True,
                enable_word_confidence=True,
            ),
            adaptation=adaptation,
        )

        streaming_config = cloud_speech.StreamingRecognitionConfig(config=recognition_config)
        config_request = cloud_speech.StreamingRecognizeRequest(
            recognizer=self.recognizer,
            streaming_config=streaming_config,
        )

        def requests() -> Generator[cloud_speech.StreamingRecognizeRequest, None, None]:
            yield config_request
            for chunk in self.slice_audio_chunks(audio_chunk):
                yield cloud_speech.StreamingRecognizeRequest(audio=chunk)

        words = []
        transcript = ""

        try:
            responses_iterator = self.client_v2.streaming_recognize(requests=requests())
            for response in responses_iterator:
                for result in response.results:

                    best = result.alternatives[0]
                    transcript += best.transcript + " "

                    for word_info in best.words:
                        words.append(
                            Word(
                                word=word_info.word,
                                start=word_info.start_offset.total_seconds(),
                                end=word_info.end_offset.total_seconds(),
                                confidence=word_info.confidence,
                            )
                        )

        except Exception as e:
            logger.error(f"[GCP_SpeechToTextV2] Error: {e}")

        return SpeechRecognize(transcript=transcript.strip(), words=words)