from internal.infra.log.logger import logger
from internal.domain.models.websocket import AudioChunkMessage, WebSocketClient, SegmentStartMessage, SegmentEndMessage
from internal.infra.db.redis import redis_client
from internal.graph.interview.interview_state import InterviewState
from internal.infra.stt.gcp_stt import GCP_SpeechToText

class WebSocketServerCallback:
    def __init__(self):
        self.stt_client = GCP_SpeechToText()
        self.redis_client = redis_client

    async def handle_segment_start(self, client: WebSocketClient, request: SegmentStartMessage):
        logger.info(f"[Websocket: handle segment start]: {client.user_id} {client.session_id}, {request}")

        client.current_segment_id = request.segment_id
        logger.info(f"[Websocket: handle segment start]: Set current segment to {request.segment_id} for session {client.session_id}")

    async def handle_audio_chunk(self, client: WebSocketClient, audio_message: AudioChunkMessage):
        logger.info(f"[Websocket: handle audio chunk] Called: audio data: {audio_message.audio_data}")
        try:
            stt = self.stt_client.transcribe(audio_message.audio_data, client.language)
            self.redis_client.save_segment_stt(client.session_id, audio_message.segment_id, stt)
        except Exception as e:
            logger.error(f"[Websocket: handle audio chunk]: {e}")
            raise e

    async def handle_segment_end(self, client: WebSocketClient, request: SegmentEndMessage):
        logger.info(f"[Websocket: handle segment end]:")
        stt_list = self.redis_client.get_segment_stt(client.session_id, request.segment_id)
        if stt_list:
            logger.info(f"[Websocket: handle segment end]: {stt_list}")
            self.redis_client.clear_segment_stt(client.session_id, request.segment_id)
        else:
            logger.error(f"[Websocket: handle segment end]: {client.user_id} {client.session_id}, {request}")
            raise Exception("Segment STT not found")

    