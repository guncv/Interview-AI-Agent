from internal.adapters.log.logger import logger
from internal.domain.models.websocket import AudioChunkMessage, WebSocketClient, SegmentStartMessage, SegmentEndMessage, StartSessionConversationMessage, TTSAudioChunking
from internal.service.websocket import WebSocketService
from internal.domain.enum import WebSocketMessageType
from starlette.websockets import WebSocketDisconnect
from internal.domain.enum import WebSocketMessageAuthor
import json
import base64
import struct
import asyncio

class WebSocketServerCallback:
    def __init__(self):
        self.websocket_service = WebSocketService()
        
    async def handle_start_session_conversation(self, client: WebSocketClient, request: StartSessionConversationMessage):
        try:
            if request.session_id != client.session_id:
                raise ValueError(f"Session ID mismatch: {request.session_id} != {client.session_id}")
            
            if not client.is_connected:
                logger.warning(f"[WebsocketServerCallback: handle start session conversation] WebSocket is not connected, skipping response")
                return
            
            logger.info(f"[WebsocketServerCallback: handle start session conversation] Sending interviewer turn start message")
            await client.websocket.send_text(json.dumps({
                "type": WebSocketMessageType.INTERVIEWR_TURN_START,
                "session_id": client.session_id
            }))
            
            await self.websocket_service.get_interviewer_response(client, "Let's Start the conversation")
            
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

            await self.websocket_service.handle_audio_chunk(client, audio_message)
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
            final_transcript = " ".join(curr_transcript) if curr_transcript else ""
            logger.info(f"[WebSocketServerCallback: handle segment end] Final joined transcript: {final_transcript}")

            self.websocket_service.redis_client.clear_segment_stt(client.session_id, request.segment_id)

            client.current_segment_id = None
            
            if client.is_connected:
                try:
                    await client.websocket.send_text(json.dumps({
                        "type": WebSocketMessageType.USER_FULL_TRANSCRIPT,
                        "author": WebSocketMessageAuthor.USER,
                        "session_id": client.session_id,
                        "segment_id": request.segment_id,
                        "transcript": final_transcript
                    }))
                    
                    await client.websocket.send_text(json.dumps({
                        "type": WebSocketMessageType.INTERVIEWR_TURN_START,
                        "session_id": client.session_id
                    }))
                    
                    await self.websocket_service.get_interviewer_response(client, final_transcript)
                    
                except WebSocketDisconnect:
                    logger.warning(f"[WebSocketServerCallback: handle segment end] WebSocket disconnected, skipping response")
                    client.is_connected = False
            else:
                logger.warning(f"[WebSocketServerCallback: handle segment end] WebSocket is not connected, skipping response")

        except Exception as e:
            logger.error(f"[WebsocketServerCallback: handle segment end]: {e}", exc_info=True)
            raise e
    
    async def handle_interviewer_audio_chunking(self, client: WebSocketClient, request: TTSAudioChunking):
        logger.info(f"[WebsocketServerCallback: handle interviewer audio chunking] Called:")
        try:
            if request.session_id != client.session_id:
                raise ValueError(f"Session ID mismatch: {request.session_id} != {client.session_id}")

            if not client.is_connected:
                logger.warning(f"[WebsocketServerCallback: handle interviewer audio chunking] WebSocket is not connected, skipping audio chunk")
                return

            header = {
                "type": WebSocketMessageType.INTERVIEWER_AUDIO_CHUNKING,
                "session_id": client.session_id,
            }
            header_bytes = json.dumps(header).encode("utf-8")
            frame = struct.pack(">I", len(header_bytes)) + header_bytes + request.audio
            await client.websocket.send_bytes(frame)

        except WebSocketDisconnect:
            logger.warning(f"[WebsocketServerCallback: handle interviewer audio chunking] WebSocket disconnected, skipping audio chunk")
            client.is_connected = False
            return
        except Exception as e:
            logger.error(f"[WebsocketServerCallback: handle interviewer audio chunking] Error: {e}", exc_info=True)
            raise e