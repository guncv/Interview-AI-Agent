from enum import Enum

class WebSocketMessageType(str, Enum):
    CONNECTION_ESTABLISHED = "connection_established"
    SEGMENT_START = "segment_start"
    SEGMENT_END = "segment_end"
    ERROR = "error"
    ECHO = "echo"
    PING = "ping"
    PONG = "pong"


class WebSocketErrorCode(str, Enum):
    INVALID_TOKEN = "invalid_token"
    SESSION_NOT_FOUND = "session_not_found"
    INVALID_MESSAGE = "invalid_message"
    INVALID_SEGMENT_START = "invalid_segment_start"
    INVALID_SEGMENT_END = "invalid_segment_end"
    SESSION_ID_MISMATCH = "session_id_mismatch"
    SEGMENT_ID_MISMATCH = "segment_id_mismatch"