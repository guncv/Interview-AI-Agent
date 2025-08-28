from dataclasses import dataclass
from typing import Optional


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
class SegmentEndMessage:
    type: str
    session_id: str
    segment_id: str
    timestamp: Optional[float] = None


@dataclass
class ErrorMessage:
    type: str = "error"
    code: str = ""
    message: str = ""