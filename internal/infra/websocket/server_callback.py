from internal.infra.log.logger import logger
from internal.domain.models.websocket import AudioChunkMessage, WebSocketClient, SegmentStartMessage, SegmentEndMessage
from internal.infra.db.redis import redis_client
from internal.infra.stt.gcp_stt import GCP_SpeechToText
from typing import List
from internal.utils.format import correct_text
from internal.domain.models.speech_recognize import SpeechRecognize
from internal.infra.stt.whisper_stt import WhisperSpeechToText
from internal.llm.post_stt_corrector import correct_transcript

class WebSocketServerCallback:
    def __init__(self):
        self.stt_client = GCP_SpeechToText()
        self.whisper_client = WhisperSpeechToText()
        self.redis_client = redis_client

    async def handle_segment_start(self, client: WebSocketClient, request: SegmentStartMessage):
        logger.info(f"[Websocket: handle segment start]: Called")
        client.current_segment_id = request.segment_id

    async def handle_audio_chunk(self, client: WebSocketClient, audio_message: AudioChunkMessage):
        logger.info(f"[Websocket: handle audio chunk] Called: audio data: ")
        try:
            curr_recognize = self.whisper_client.transcribe_audio(audio_message.audio_data)
            logger.info(f"[Websocket: handle audio chunk] Curr transcript: '{curr_recognize}'")
            self.redis_client.save_segment_stt(client.session_id, audio_message.segment_id, curr_recognize.transcript)

        except Exception as e:
            logger.error(f"[Websocket: handle audio chunk] Error: {e}")
            raise e

    async def handle_segment_end(self, client: WebSocketClient, request: SegmentEndMessage):
        logger.info(f"[Websocket: handle segment end]:")
        try:
            curr_transcript = self.redis_client.get_segment_stt(client.session_id, request.segment_id)
            final_transcript = " ".join(curr_transcript)
            logger.info(f"[Websocket: handle segment end] Final joined transcript: {final_transcript}")
            formatted_transcript = correct_text(final_transcript)
            logger.info(f"[Websocket: handle segment end] Final formatted transcript: {formatted_transcript}")
            self.redis_client.clear_segment_stt(client.session_id, request.segment_id)
        except Exception as e:
            logger.error(f"[Websocket: handle segment end]: {e}")
            raise e

    