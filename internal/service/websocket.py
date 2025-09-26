from internal.adapters.log.logger import logger
from internal.domain.models.websocket import WebSocketClient, AudioChunkMessage, SegmentStartMessage, TTSAudioChunking
from internal.adapters.db.redis import redis_client
from internal.adapters.stt.whisper_stt import WhisperSpeechToText
from internal.domain.enum import WebSocketMessageType, WebSocketMessageAuthor
from internal.adapters.tts.openai import OpenAITTS
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
            from internal.service.interview_graph import InterviewGraph
            self._interview_graph = InterviewGraph()
        return self._interview_graph

    @property
    def websocket_server_callback(self):
        if self._websocket_server_callback is None:
            from internal.adapters.websocket.server_callback import WebSocketServerCallback
            self._websocket_server_callback = WebSocketServerCallback()
        return self._websocket_server_callback
        
    async def handle_segment_start(self, client: WebSocketClient, request: SegmentStartMessage):
        logger.info(f"[WebSocketService: handle segment start]: Called")
        if request.session_id != client.session_id:
            raise ValueError(f"Session ID mismatch: {request.session_id} != {client.session_id}")

        client.current_segment_id = request.segment_id

    async def handle_audio_chunk(self, client: WebSocketClient, audio_message: AudioChunkMessage):
        logger.info(f"[WebSocketService: handle audio chunk] Called: audio data present")

        try:
            curr_recognize = await self.stt_client.transcribe(audio_message.audio_data, client.session_id)
            self.redis_client.save_segment_stt(client.session_id, audio_message.segment_id, curr_recognize.transcript)

        except Exception as e:
            logger.error(f"[WebSocketService: handle audio chunk] Error: {e}")
            raise e
        
    async def handle_interviewer_audio_chunking(self, client: WebSocketClient, message: str):
        logger.info("[WebSocketService: handle_interviewer_audio_chunking] Called")

        try:
            async for chunk in self.tts_client.synthesize_stream(message):
                logger.info("[WebSocketService: handle_interviewer_audio_chunking] Sending audio chunk")

                tts_chunk = TTSAudioChunking(
                    type=WebSocketMessageType.INTERVIEWER_AUDIO_CHUNKING,
                    session_id=client.session_id,
                    audio=chunk
                )
                await self.websocket_server_callback.handle_interviewer_audio_chunking(client, tts_chunk)

        except WebSocketDisconnect:
            logger.warning(f"[WebSocketService: handle_interviewer_audio_chunking] WebSocket disconnected, stopping audio streaming")
            client.is_connected = False
            return
        
        except Exception as e:
            logger.error(f"[WebSocketService: handle_interviewer_audio_chunking] Error: {e}", exc_info=True)
            raise

    async def send_response_and_audio(self, client: WebSocketClient, message_data):
        logger.info("[WebSocketService: send_response_and_audio] Called")

        try:
            if not client.is_connected:
                logger.warning(f"[WebSocketService: send_response_and_audio] WebSocket is not connected, skipping response")
                return

            await self.handle_interviewer_audio_chunking(client, message_data.message)

            await client.websocket.send_text(json.dumps({
                "type": WebSocketMessageType.INTERVIEWER_RESPONSE,
                "author": WebSocketMessageAuthor.INTERVIEWER,
                "session_id": client.session_id,
                "message": message_data.message,
                "started_at": message_data.start_at,
                "ended_at": message_data.end_at,
                "current_state": message_data.current_storing_node.value
            }))
            
        except WebSocketDisconnect:
            logger.warning(f"[WebSocketService: send_response_and_audio] WebSocket disconnected, skipping response")
            client.is_connected = False
            return
        
        except Exception as e:
            logger.error(f"[WebSocketService: send_response_and_audio] Error: {e}", exc_info=True)
            raise

    async def get_interviewer_response(self, client: WebSocketClient, final_transcript: str):
        logger.info("[WebSocketService: get_interviewer_response] Called")
        
        message_data = await self.interview_graph.invoke(client.session_id, final_transcript)

        while True:
            if message_data.message:
                await self.send_response_and_audio(client, message_data)

            if not message_data.go_to_next_step:
                break

            message_data = await self.interview_graph.invoke(client.session_id, message_data.message)
        
        logger.info(f"[WebSocketService: get_interviewer_response] Sending ending interviewer turn")
        await asyncio.sleep(1)
        await client.websocket.send_text(json.dumps({
            "type": WebSocketMessageType.INTERVIEWR_TURN_END,
            "session_id": client.session_id
        }))