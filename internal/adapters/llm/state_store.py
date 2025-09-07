from __future__ import annotations
import os
from typing import Dict
import os, json
from typing import Optional
from redis import Redis
from internal.domain.models.interview import InterviewProcessState
from enum import Enum

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
STATE_TTL_SECONDS = int(os.getenv("STATE_TTL_SECONDS", "900"))
STATE_PREFIX = os.getenv("REDIS_STATE_PREFIX", "interview-sim:state")
LOCK_PREFIX = os.getenv("REDIS_LOCK_PREFIX", "interview-sim:lock")

r = Redis.from_url(REDIS_URL, decode_responses=True)

def _state_key(session_id: str) -> str:
    return f"{STATE_PREFIX}:{session_id}"

def save_state(session_id: str, state: InterviewProcessState) -> None:
    def enum_converter(obj):
        if isinstance(obj, Enum):
            return obj.value
        raise TypeError(f'Object of type {obj.__class__.__name__} is not JSON serializable')
    
    state_dict = state.dict()
    r.setex(_state_key(session_id), STATE_TTL_SECONDS, json.dumps(state_dict, ensure_ascii=False, default=enum_converter))

def load_state(session_id: str) -> Optional[InterviewProcessState]:
    raw = r.get(_state_key(session_id))
    if not raw:
        return None
    return InterviewProcessState(**json.loads(raw))

def clear_state(session_id: str) -> None:
    r.delete(_state_key(session_id))

def acquire_lock(session_id: str, ttl: int = 5) -> bool:
    return bool(r.set(f"{LOCK_PREFIX}:{session_id}", "1", nx=True, ex=ttl))

def release_lock(session_id: str) -> None:
    r.delete(f"{LOCK_PREFIX}:{session_id}")
