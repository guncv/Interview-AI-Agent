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
        logger.info(f"[Websocket: handle segment start]: Called")
        client.current_segment_id = request.segment_id

    async def handle_audio_chunk(self, client: WebSocketClient, audio_message: AudioChunkMessage):
        logger.info(f"[Websocket: handle audio chunk] Called: audio data: {audio_message.audio_data}")
        try:
            self.redis_client.save_segment_stt(client.session_id, audio_message.segment_id, audio_message.audio_data)
        except Exception as e:
            logger.error(f"[Websocket: handle audio chunk]: {e}")
            raise e

    async def handle_segment_end(self, client: WebSocketClient, request: SegmentEndMessage):
        logger.info(f"[Websocket: handle segment end]:")
        try:
            chunk_data_list = self.redis_client.get_segment_stt(client.session_id, request.segment_id)
            logger.info(f"[Websocket: handle segment end]: chunk_data_list: {chunk_data_list}")
            if not chunk_data_list:
                logger.info(f"[Websocket: handle segment end]: Segment STT not found")
                return
            stt = self.stt_client.transcribe_streaming_from_chunks(chunk_data_list, client.language)
            logger.info(f"[Websocket: handle segment end after stt]: {stt}")
            self.redis_client.clear_segment_stt(client.session_id, request.segment_id)
        except Exception as e:
            logger.error(f"[Websocket: handle segment end]: {e}")
            raise e

    