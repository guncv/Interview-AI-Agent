from internal.infra.websocket.server import WebSocketClient

class WebSocketServerCallback:
    def on_message(self, client: WebSocketClient, message: dict):
        pass

    def on_disconnect(self, client: WebSocketClient):
        pass

    def on_error(self, client: WebSocketClient, error: Exception):
        pass
    