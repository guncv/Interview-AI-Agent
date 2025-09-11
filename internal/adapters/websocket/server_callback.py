from internal.adapters.log.logger import logger
from internal.domain.models.websocket import AudioChunkMessage, WebSocketClient, SegmentStartMessage, SegmentEndMessage, StartSessionConversationMessage
from internal.domain.models.interview import get_step_display_name
from internal.service.websocket import WebSocketService
import json

class WebSocketServerCallback:
    def __init__(self):
        self.websocket_service = WebSocketService()
        
    async def handle_start_session_conversation(self, client: WebSocketClient, request: StartSessionConversationMessage):
        try:
            if request.session_id != client.session_id:
                raise ValueError(f"Session ID mismatch: {request.session_id} != {client.session_id}")

            resp = await self.websocket_service.get_interviewer_response(client, "Let's Start the conversation")
            
            await client.websocket.send_text(json.dumps({
                "type": "interviewer_response",
                "author": "interviewer",
                "session_id": client.session_id,
                "message": resp.message,
                "started_at": resp.started_at,
                "ended_at": resp.ended_at,
                "current_state": resp.current_state
            }))
        except Exception as e:
            logger.error(f"[Websocket: handle start session conversation] Error: {e}")
            raise e

    async def handle_segment_start(self, client: WebSocketClient, request: SegmentStartMessage):
        try:
            if request.session_id != client.session_id:
                raise ValueError(f"Session ID mismatch: {request.session_id} != {client.session_id}")

            await self.websocket_service.handle_segment_start(client, request)
        except Exception as e:
            logger.error(f"[Websocket: handle segment start] Error: {e}")
            raise e

    async def handle_audio_chunk(self, client: WebSocketClient, audio_message: AudioChunkMessage):
        try:
            if audio_message.segment_id != client.current_segment_id:
                raise ValueError(f"Segment ID mismatch: {audio_message.segment_id} != {client.current_segment_id}")

            message_data = await self.websocket_service.handle_audio_chunk(client, audio_message)

            await client.websocket.send_text(json.dumps(message_data))
        except Exception as e:
            logger.error(f"[Websocket: handle audio chunk] Error: {e}")
            raise e

    async def handle_segment_end(self, client: WebSocketClient, request: SegmentEndMessage):
        try:
            if request.session_id != client.session_id:
                raise ValueError(f"Session ID mismatch: {request.session_id} != {client.session_id}")

            if request.segment_id != client.current_segment_id:
                raise ValueError(f"Segment ID mismatch: {request.segment_id} != {client.current_segment_id}")
            
            curr_transcript = self.websocket_service.redis_client.get_segment_stt(client.session_id, request.segment_id)
            final_transcript = " ".join(curr_transcript)
            logger.info(f"[WebSocketService: handle segment end] Final joined transcript: {final_transcript}")

            self.websocket_service.redis_client.clear_segment_stt(client.session_id, request.segment_id)

            client.current_segment_id = None
            
            await client.websocket.send_text(json.dumps({
                "type": "user_full_transcript",
                "author": "user",
                "session_id": client.session_id,
                "segment_id": request.segment_id,
                "transcript": final_transcript
            }))
            
            resp = await self.websocket_service.get_interviewer_response(client, final_transcript)
            
            logger.info(f"[WebSocketService: handle segment end] Response: {resp}")
            
            await client.websocket.send_text(json.dumps({
                "type": "interviewer_response",
                "author": "interviewer",
                "session_id": client.session_id,
                "message": resp.message,
                "started_at": resp.started_at,
                "ended_at": resp.ended_at,
                "current_state": resp.current_state
            }))

        except Exception as e:
            logger.error(f"[Websocket: handle segment end]: {e}")
            raise e
