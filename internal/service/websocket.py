from internal.adapters.log.logger import logger
from internal.domain.models.websocket import WebSocketClient, AudioChunkMessage, SegmentStartMessage
from internal.adapters.db.redis import redis_client
from internal.adapters.stt.whisper_stt import WhisperSpeechToText
from internal.service.interview_graph import InterviewGraph
from internal.domain.models.interview import InterviewServiceResponse
from datetime import datetime, timezone
from internal.domain.models.interview import get_step_display_name

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

    async def get_interviewer_response(self, client: WebSocketClient, final_transcript: str) -> InterviewServiceResponse:
        logger.info(f"[WebSocketService: handle segment end] Called:")

        try:
            started_at = datetime.now(timezone.utc).isoformat()
            message_data = await self.interview_graph.invoke(client.session_id, final_transcript)
            ended_at = datetime.now(timezone.utc).isoformat()
            
            current_step = get_step_display_name(message_data.current_step)
            
            resp = InterviewServiceResponse(
                message=message_data.message,
                started_at=started_at,
                ended_at=ended_at,
                current_state=current_step
            )
            return resp


        except Exception as e:
            logger.error(f"[WebSocketService: handle segment end]: {e}")
            raise e
