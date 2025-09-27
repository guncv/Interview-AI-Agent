import os
from enum import Enum

class RedisKeys(Enum):
    STATE_TTL_SECONDS = 900
    STATE_PREFIX = "interview-sim:state"
    LOCK_PREFIX = "interview-sim:lock"
    SEGMENT_AUDIO_PREFIX = "interview-sim:segment_audio"