from internal.adapters.log.logger import logger
from internal.domain.models.websocket import AudioChunkMessage, WebSocketClient, SegmentStartMessage, SegmentEndMessage
from internal.service.websocket import WebSocketService
import json

class WebSocketServerCallback:
    def __init__(self):
        self.websocket_service = WebSocketService()

    async def handle_segment_start(self, client: WebSocketClient, request: SegmentStartMessage):
        await self.websocket_service.handle_segment_start(client, request)

    async def handle_audio_chunk(self, client: WebSocketClient, audio_message: AudioChunkMessage):
        try:
            message_data = await self.websocket_service.handle_audio_chunk(client, audio_message)

            await client.websocket.send_text(json.dumps(message_data))
        except Exception as e:
            logger.error(f"[Websocket: handle audio chunk] Error: {e}")
            raise e

    async def handle_segment_end(self, client: WebSocketClient, request: SegmentEndMessage):
        try:
            if request.session_id != client.session_id:
                raise ValueError(f"Session ID mismatch: {request.session_id} != {client.session_id}")
            
            curr_transcript = self.websocket_service.redis_client.get_segment_stt(client.session_id, request.segment_id)
            final_transcript = " ".join(curr_transcript)
            logger.info(f"[WebSocketService: handle segment end] Final joined transcript: {final_transcript}")

            self.websocket_service.redis_client.clear_segment_stt(client.session_id, request.segment_id)
            
            await client.websocket.send_text(json.dumps({
                "type": "user_full_transcript",
                "author": "user",
                "session_id": client.session_id,
                "segment_id": request.segment_id,
                "transcript": final_transcript
            }))
            
            resp = await self.websocket_service.handle_segment_end(client, final_transcript)
            
            logger.info(f"[WebSocketService: handle segment end] Response: {resp}")
            
            await client.websocket.send_text(json.dumps({
                "type": "interviewer_response",
                "author": "interviewer",
                "session_id": client.session_id,
                "message": resp.message,
                "started_at": resp.started_at,
                "ended_at": resp.ended_at
            }))

        except Exception as e:
            logger.error(f"[Websocket: handle segment end]: {e}")
            raise e
