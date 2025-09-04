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
            message_data = await self.websocket_service.handle_segment_end(client, request)

            await client.websocket.send_text(json.dumps(message_data))
        except Exception as e:
            logger.error(f"[Websocket: handle segment end]: {e}")
            raise e

    