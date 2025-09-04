import os
from enum import Enum

class RedisKeys(Enum):
    STATE_TTL_SECONDS = 900
    STATE_PREFIX = "interview-sim:state"
    LOCK_PREFIX = "interview-sim:lock"
    SEGMENT_STT_PREFIX = "interview-sim:segment_stt"
    PREV_SEGMENT_CHUNK_PREFIX = "interview-sim:prev_segment_chunk"
    BIAS_PROMPT_PREFIX = "interview-sim:bias_prompt"
    PREV_SEGMENT_STT_PREFIX = "interview-sim:prev_segment_stt"