from core.log.logger import logger
from domain.models.websocket import WebSocketClient, AudioChunkMessage, SegmentStartMessage, TTSAudioChunking
from infrastructure.redis.redis import redis_client
from infrastructure.stt.whisper_stt import WhisperSpeechToText
from domain.enums.websocket import WebSocketMessageType, WebSocketMessageAuthor
from infrastructure.tts.openai import OpenAITTS
from domain.models.interview import InterviewProcessStep
from infrastructure.llm.state_store import clearMemory, clear_state
from starlette.websockets import WebSocketDisconnect
import json
import asyncio

class WebSocketService:
    def __init__(self):
        self._interview_graph = None
        self.stt_client = WhisperSpeechToText()
        self.tts_client = OpenAITTS()
        self.redis_client = redis_client
        self._websocket_server_callback = None

    @property
    def interview_graph(self):
        if self._interview_graph is None:
            from services.interview_graph import InterviewGraph
            self._interview_graph = InterviewGraph()
        return self._interview_graph

    @property
    def websocket_server_callback(self):
        if self._websocket_server_callback is None:
            from infrastructure.websocket.server_callback import WebSocketServerCallback
            self._websocket_server_callback = WebSocketServerCallback()
        return self._websocket_server_callback
        
    async def handle_segment_start(self, client: WebSocketClient, request: SegmentStartMessage):
        if request.session_id != client.session_id:
            raise ValueError(f"Session ID mismatch: {request.session_id} != {client.session_id}")

        client.current_segment_id = request.segment_id

    async def handle_audio_chunk(self, client: WebSocketClient, audio_message: AudioChunkMessage):
        try:
            self.redis_client.save_segment_audio(client.session_id, audio_message.segment_id, audio_message.audio_data)

        except Exception as e:
            logger.error(f"[WebSocketService: handle audio chunk] Error: {e}")
            raise e
        
    async def handle_interviewer_audio_chunking(self, client: WebSocketClient, message: str) -> int:
        try:
            chunking_count = 0
            async for chunk in self.tts_client.synthesize_stream(message):
                tts_chunk = TTSAudioChunking(
                    type=WebSocketMessageType.INTERVIEWER_AUDIO_CHUNKING,
                    session_id=client.session_id,
                    audio=chunk
                )
                await self.websocket_server_callback.handle_interviewer_audio_chunking(client, tts_chunk)
                chunking_count += 1

            return chunking_count

        except WebSocketDisconnect:
            logger.warning(f"[WebSocketService: handle_interviewer_audio_chunking] WebSocket disconnected, stopping audio streaming")
            client.is_connected = False
            return
        
        except Exception as e:
            logger.error(f"[WebSocketService: handle_interviewer_audio_chunking] Error: {e}", exc_info=True)
            raise

    async def send_response_and_audio(self, client: WebSocketClient, message_data):
        try:
            if not client.is_connected:
                logger.warning(f"[WebSocketService: send_response_and_audio] WebSocket is not connected, skipping response")
                return

            chunking_count = await self.handle_interviewer_audio_chunking(client, message_data.message)

            await client.websocket.send_text(json.dumps({
                "type": WebSocketMessageType.INTERVIEWER_RESPONSE,
                "author": WebSocketMessageAuthor.INTERVIEWER,
                "session_id": client.session_id,
                "message": message_data.message,
                "started_at": message_data.start_at,
                "ended_at": message_data.end_at,
                "current_state": message_data.current_storing_node.value,
                "chunking_count": chunking_count
            }))
            
        except WebSocketDisconnect:
            logger.warning(f"[WebSocketService: send_response_and_audio] WebSocket disconnected, skipping response")
            client.is_connected = False
            return
        
        except Exception as e:
            logger.error(f"[WebSocketService: send_response_and_audio] Error: {e}", exc_info=True)
            raise

    async def get_interviewer_response(self, client: WebSocketClient, final_transcript: str):
        message_data = await self.interview_graph.invoke(client.session_id, final_transcript, client.position, client.selected_stages)

        while True:
            if message_data.message:
                await self.send_response_and_audio(client, message_data)
                
            if message_data.current_step == InterviewProcessStep.COMPLETED:
                try:
                    clearMemory(client.session_id)
                except Exception as e:
                    logger.error(f"[WebSocketService: get_interviewer_response] Failed to clear memory: {e}")
                
                try:
                    clear_state(client.session_id)
                except Exception as e:
                    logger.error(f"[WebSocketService: get_interviewer_response] Failed to clear state: {e}")

                break

            if not message_data.go_to_next_step:
                break

            message_data = await self.interview_graph.invoke(client.session_id, message_data.message, client.position, client.selected_stages)
        
        if message_data.current_step != InterviewProcessStep.COMPLETED:
            await asyncio.sleep(1)
            await client.websocket.send_text(json.dumps({
                    "type": WebSocketMessageType.INTERVIEWR_TURN_END,
                    "session_id": client.session_id
                }))
            
        if message_data.current_step == InterviewProcessStep.COMPLETED:
            await asyncio.sleep(0.5)
            await client.websocket.send_text(json.dumps({
                "type": WebSocketMessageType.INTERVIEW_COMPLETED,
                "session_id": client.session_id,
            }))