from enum import Enum

class WebSocketMessageType(str, Enum):
    START_SESSION_CONVERSATION = "start_session_conversation"
    CONNECTION_ESTABLISHED = "connection_established"
    SEGMENT_START = "segment_start"
    SEGMENT_END = "segment_end"
    INTERVIEWER_AUDIO_CHUNKING = "interviewer_audio_chunking"
    USER_FULL_TRANSCRIPT = "user_full_transcript"
    USER_PARTIAL_TRANSCRIPT = "user_partial_transcript"
    INTERVIEWER_RESPONSE = "interviewer_response"
    INTERVIEWR_TURN_START = "interviewer_turn_start"
    INTERVIEWR_TURN_END = "interviewer_turn_end"
    INTERVIEW_COMPLETED = "interview_completed"
    ERROR = "error"
    ECHO = "echo"
    PING = "ping"
    PONG = "pong"

class WebSocketMessageAuthor(str, Enum):
    USER = "user"
    INTERVIEWER = "interviewer"

class WebSocketErrorCode(str, Enum):
    INVALID_TOKEN = "invalid_token"
    SESSION_NOT_FOUND = "session_not_found"
    INVALID_MESSAGE = "invalid_message"
    INVALID_SEGMENT_START = "invalid_segment_start"
    INVALID_SEGMENT_END = "invalid_segment_end"
    SESSION_ID_MISMATCH = "session_id_mismatch"
    SEGMENT_ID_MISMATCH = "segment_id_mismatch"

