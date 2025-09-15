from internal.adapters.log.logger import logger
from internal.domain.models.websocket import AudioChunkMessage, WebSocketClient, SegmentStartMessage, SegmentEndMessage, StartSessionConversationMessage, TTSAudioChunking
from internal.service.websocket import WebSocketService
import json
import base64

class WebSocketServerCallback:
    def __init__(self):
        self.websocket_service = WebSocketService()
        
    async def handle_start_session_conversation(self, client: WebSocketClient, request: StartSessionConversationMessage):
        try:
            if request.session_id != client.session_id:
                raise ValueError(f"Session ID mismatch: {request.session_id} != {client.session_id}")

            resp = await self.websocket_service.get_interviewer_response(client, "Let's Start the conversation")
            
            for message in resp.content:
                await client.websocket.send_text(json.dumps({
                    "type": "interviewer_response",
                    "author": "interviewer",
                    "session_id": client.session_id,
                    "message": message.message,
                    "started_at": message.started_at,
                    "ended_at": message.ended_at,
                    "current_state": message.current_state.value
                }))
            
        except Exception as e:
            logger.error(f"[WebsocketServerCallback: handle start session conversation] Error: {e}")
            raise e

    async def handle_segment_start(self, client: WebSocketClient, request: SegmentStartMessage):
        try:
            if request.session_id != client.session_id:
                raise ValueError(f"Session ID mismatch: {request.session_id} != {client.session_id}")

            await self.websocket_service.handle_segment_start(client, request)
        except Exception as e:
            logger.error(f"[WebsocketServerCallback: handle segment start] Error: {e}")
            raise e

    async def handle_audio_chunk(self, client: WebSocketClient, audio_message: AudioChunkMessage):
        try:
            if audio_message.segment_id != client.current_segment_id:
                raise ValueError(f"Segment ID mismatch: {audio_message.segment_id} != {client.current_segment_id}")

            message_data = await self.websocket_service.handle_audio_chunk(client, audio_message)

            await client.websocket.send_text(json.dumps(message_data))
        except Exception as e:
            logger.error(f"[WebsocketServerCallback: handle audio chunk] Error: {e}")
            raise e

    async def handle_segment_end(self, client: WebSocketClient, request: SegmentEndMessage):
        try:
            logger.info(f"[WebSocketServerCallback: handle segment end] Request: {request}")
            if request.session_id != client.session_id:
                raise ValueError(f"Session ID mismatch: {request.session_id} != {client.session_id}")

            if request.segment_id != client.current_segment_id:
                raise ValueError(f"Segment ID mismatch: {request.segment_id} != {client.current_segment_id}")
            
            curr_transcript = self.websocket_service.redis_client.get_segment_stt(client.session_id, request.segment_id)
            final_transcript = " ".join(curr_transcript)
            logger.info(f"[WebSocketServerCallback: handle segment end] Final joined transcript: {final_transcript}")

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
            
            for message in resp.content:
                await client.websocket.send_text(json.dumps({
                    "type": "interviewer_response",
                    "author": "interviewer",
                    "session_id": client.session_id,
                    "message": message.message,
                    "started_at": message.started_at,
                    "ended_at": message.ended_at,
                    "current_state": message.current_state.value
                }))

        except Exception as e:
            logger.error(f"[WebsocketServerCallback: handle segment end]: {e}")
            raise e

    async def handle_tts(self, client: WebSocketClient, request: TTSAudioChunking):
        logger.info(f"[WebsocketServerCallback: handle tts] Called:")
        try:
            if request.session_id != client.session_id:
                raise ValueError(f"Session ID mismatch: {request.session_id} != {client.session_id}")

            logger.info(f"[WebSocketServerCallback: handle tts] Request: {request}")
            # Encode bytes to base64 for JSON serialization
            audio_b64 = base64.b64encode(request.audio).decode('utf-8')
            await client.websocket.send_text(json.dumps({
                "type": "interviewer_audio_chunking",
                "session_id": client.session_id,
                "audio": audio_b64
            }))
        except Exception as e:
            logger.error(f"[WebsocketServerCallback: handle tts] Error: {e}")
            raise e

    async def initialize_tts_session(self, client: WebSocketClient):
        try:
            logger.info(f"[WebsocketServerCallback: initialize tts session] TTS session initialized for {client.session_id}")
            await self.websocket_service.initialize_tts_session(client.session_id)
            
        except Exception as e:
            logger.error(f"[WebsocketServerCallback: initialize tts session] Error: {e}")
            raise e

    async def cleanup_tts_session(self, client: WebSocketClient):
        try:
            await self.websocket_service.cleanup_tts_session(client.session_id)
            logger.info(f"[WebsocketServerCallback: cleanup tts session] TTS session cleaned up for {client.session_id}")
        except Exception as e:
            logger.error(f"[WebsocketServerCallback: cleanup tts session] Error: {e}")
            raise e