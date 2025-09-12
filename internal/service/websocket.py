from internal.adapters.log.logger import logger
from internal.domain.models.websocket import WebSocketClient, AudioChunkMessage, SegmentStartMessage, TTSAudioChunking
from internal.adapters.db.redis import redis_client
from internal.adapters.stt.whisper_stt import WhisperSpeechToText
from internal.domain.models.interview import InterviewServiceResponse
from internal.adapters.tts.openai import OpenAITTS

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
        
    async def handle_tts(self, client: WebSocketClient, message: str):
        logger.info(f"[WebSocketService: handle tts] Called:")

        try:
            async for chunk in self.tts_client.synthesize_stream(message, client.session_id):
                await self.websocket_server_callback.handle_tts(client, chunk)
        except Exception as e:
            logger.error(f"[WebSocketService: handle tts] Error: {e}")
            raise e

    async def get_interviewer_response(self, client: WebSocketClient, final_transcript: str) -> InterviewServiceResponse:
        logger.info(f"[WebSocketService: get interviewer response] Called:")

        try:
            message_data = await self.interview_graph.invoke(client.session_id, final_transcript, client)
            logger.info(f"[WebSocketService: get interviewer response] Message data: {message_data}")
            resp = InterviewServiceResponse(content=message_data.message)
            return resp

        except Exception as e:
            logger.error(f"[WebSocketService: get interviewer response]: {e}")
            raise e
