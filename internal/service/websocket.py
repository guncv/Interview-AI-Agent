from internal.adapters.log.logger import logger
from internal.domain.models.websocket import WebSocketClient, AudioChunkMessage, SegmentStartMessage
from internal.adapters.db.redis import redis_client
from internal.adapters.stt.whisper_stt import WhisperSpeechToText
from internal.service.interview_graph import InterviewGraph

class WebSocketService:
    def __init__(self):
        self.interview_graph = InterviewGraph()
        self.stt_client = WhisperSpeechToText()
        self.redis_client = redis_client

    async def handle_segment_start(self, client: WebSocketClient, request: SegmentStartMessage):
        logger.info(f"[WebSocketService: handle segment start]: Called")
        if request.session_id != client.session_id:
            raise ValueError(f"Session ID mismatch: {request.session_id} != {client.session_id}")

        client.current_segment_id = request.segment_id

    async def handle_audio_chunk(self, client: WebSocketClient, audio_message: AudioChunkMessage):
        logger.info(f"[WebSocketService: handle audio chunk] Called: audio data present")

        try:
            curr_recognize = await self.stt_client.transcribe(audio_message.audio_data, client.session_id)
            logger.info(f"[WebSocketService: handle audio chunk] Curr transcript: '{curr_recognize.transcript}'")

            self.redis_client.save_segment_stt(client.session_id, audio_message.segment_id, curr_recognize.transcript)

            return {
                "type": "user_partial_transcript",
                "author": "user",
                "session_id": client.session_id,
                "segment_id": audio_message.segment_id,
                "transcript": curr_recognize.transcript
            }

        except Exception as e:
            logger.error(f"[WebSocketService: handle audio chunk] Error: {e}")
            raise e

    async def handle_segment_end(self, client: WebSocketClient, final_transcript: str) -> str:
        logger.info(f"[WebSocketService: handle segment end] Called:")

        try:
            message_data = await self.interview_graph.invoke(client.session_id, final_transcript)
            if message_data.message:
                return message_data.message
            else:
                return "Sorry, there was an error processing your request. Please try again."

        except Exception as e:
            logger.error(f"[WebSocketService: handle segment end]: {e}")
            raise e
