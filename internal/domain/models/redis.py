import os
from enum import Enum

class RedisKeys(Enum):
    STATE_TTL_SECONDS = 900
    STATE_PREFIX = "interview-sim:state"
    LOCK_PREFIX = "interview-sim:lock"
    SEGMENT_AUDIO_PREFIX = "interview-sim:segment_audio"
    RESUME_CONTEXT_PREFIX = "interview-sim:resume_context"
    RESUME_CONTEXT_TTL_SECONDS = 3600  # 1 hour cache for resume context