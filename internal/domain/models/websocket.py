from dataclasses import dataclass
from typing import Optional
from fastapi import WebSocket


@dataclass
class WebSocketClient:
    websocket: WebSocket
    user_id: str
    session_id: str
    resume_id: str
    position: str
    selected_stages: list[str]
    is_connected: bool = True
    current_segment_id: Optional[str] = None


@dataclass
class AudioChunkHeader:
    type: str
    session_id: str
    segment_id: str

@dataclass
class SegmentStartMessage:
    type: str
    session_id: str
    segment_id: str

@dataclass
class StartSessionConversationMessage:
    type: str
    session_id: str

@dataclass
class SegmentEndMessage:
    type: str
    session_id: str
    segment_id: str

@dataclass
class ErrorMessage:
    type: str = "error"
    code: str = ""
    message: str = ""
    
@dataclass
class AudioChunkMessage:
    type: str
    session_id: str
    segment_id: str
    audio_data: bytes

@dataclass
class TTSAudioChunking:
    type: str
    session_id: str
    audio: bytes