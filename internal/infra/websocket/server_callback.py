from typing import TYPE_CHECKING
from internal.infra.log.logger import logger

if TYPE_CHECKING:
    from internal.infra.websocket.server import WebSocketClient

class WebSocketServerCallback:
    async def handle_segment_start(self, client: 'WebSocketClient', message: dict):
        logger.info(f"[Websocket: handle segment start]: {client.user_id} {client.session_id}, {message}")
        pass

    async def handle_audio_chunk(self, client: 'WebSocketClient', audio_message: dict):

        logger.info(f"[Websocket: handle audio chunk]: audio_message: {audio_message}")
        # TODO: Implement audio processing logic here
        # You can access the raw audio data via audio_message['audio_data']
        pass

    async def handle_segment_end(self, client: 'WebSocketClient', message: dict):
        logger.info(f"[Websocket: handle segment end]: {client.user_id} {client.session_id}, {message}")
        pass

    