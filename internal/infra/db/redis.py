import os, json
from typing import Optional
from redis import Redis
from internal.graph.interview.interview_state import InterviewState
from enum import Enum
from internal.graph.resume.resume_state import ResumeState

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
STATE_TTL_SECONDS = int(os.getenv("STATE_TTL_SECONDS", "900"))
STATE_PREFIX = os.getenv("REDIS_STATE_PREFIX", "cpr:state")
LOCK_PREFIX = os.getenv("REDIS_LOCK_PREFIX", "cpr:lock")

r = Redis.from_url(REDIS_URL, decode_responses=True)

def _state_key(session_id: str) -> str:
    return f"{STATE_PREFIX}:{session_id}"

def save_interview_state(session_id: str, state: InterviewState) -> None:
    def enum_converter(obj):
        if isinstance(obj, Enum):
            return obj.value
        raise TypeError(f'Object of type {obj.__class__.__name__} is not JSON serializable')
    
    state_dict = state.model_dump()
    r.setex(_state_key(session_id), STATE_TTL_SECONDS, json.dumps(state_dict, ensure_ascii=False, default=enum_converter))

def load_interview_state(session_id: str) -> Optional[InterviewState]:
    raw = r.get(_state_key(session_id))
    if not raw:
        return None
    return InterviewState(**json.loads(raw))

def save_resume_state(session_id: str, state: ResumeState) -> None:
    def resume_converter(obj):
        if isinstance(obj, Enum):
            return obj.value
        if isinstance(obj, bytes):
            return obj.decode('utf-8', errors='ignore')
        raise TypeError(f'Object of type {obj.__class__.__name__} is not JSON serializable')
    
    state_dict = state.model_dump()
    r.setex(_state_key(session_id), STATE_TTL_SECONDS, json.dumps(state_dict, ensure_ascii=False, default=resume_converter))

def load_resume_state(session_id: str) -> Optional[ResumeState]:
    raw = r.get(_state_key(session_id))
    if not raw:
        return None
    return ResumeState(**json.loads(raw))

def clear_state(session_id: str) -> None:
    r.delete(_state_key(session_id))
    
def acquire_lock(session_id: str, ttl: int = 5) -> bool:
    return bool(r.set(f"{LOCK_PREFIX}:{session_id}", "1", nx=True, ex=ttl))

def release_lock(session_id: str) -> None:
    r.delete(f"{LOCK_PREFIX}:{session_id}")
