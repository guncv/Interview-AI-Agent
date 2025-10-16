from __future__ import annotations
import os
import os, json
from typing import Optional
from redis import Redis
from domain.models.interview import InterviewState
from enum import Enum
from langchain_community.chat_message_histories import (
    ChatMessageHistory,
    RedisChatMessageHistory,
)
from typing import Dict

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
STATE_TTL_SECONDS = int(os.getenv("STATE_TTL_SECONDS", "900"))
STATE_PREFIX = os.getenv("REDIS_STATE_PREFIX", "interview-sim:state")
LOCK_PREFIX = os.getenv("REDIS_LOCK_PREFIX", "interview-sim:lock")
MEMORY_TTL_SECONDS = int(os.getenv("MEMORY_TTL_SECONDS", "3600"))
REDIS_CHAT_PREFIX = os.getenv("REDIS_CHAT_PREFIX", "interview-sim:chat")

_memory_store: Dict[str, ChatMessageHistory] = {}

r = Redis.from_url(REDIS_URL, decode_responses=True)

def _state_key(session_id: str) -> str:
    return f"{STATE_PREFIX}:{session_id}"

def save_state(session_id: str, state: InterviewState) -> None:
    def enum_converter(obj):
        if isinstance(obj, Enum):
            return obj.value
        raise TypeError(f'Object of type {obj.__class__.__name__} is not JSON serializable')
    
    state_dict = state.model_dump()
    r.setex(_state_key(session_id), STATE_TTL_SECONDS, json.dumps(state_dict, ensure_ascii=False, default=enum_converter))

def load_state(session_id: str) -> Optional[InterviewState]:
    raw = r.get(_state_key(session_id))
    if not raw:
        return None
    
    state_data = json.loads(raw)
    
    return InterviewState(**state_data)

def clear_state(session_id: str) -> None:
    r.delete(_state_key(session_id))

def acquire_lock(session_id: str, ttl: int = 5) -> bool:
    return bool(r.set(f"{LOCK_PREFIX}:{session_id}", "1", nx=True, ex=ttl))

def release_lock(session_id: str) -> None:
    r.delete(f"{LOCK_PREFIX}:{session_id}")

def _use_redis() -> bool:
    return bool(REDIS_URL)

def getMemory(session_id: str) -> ChatMessageHistory:
    if _use_redis():
        return RedisChatMessageHistory(
            session_id=session_id,
            url=REDIS_URL,
            ttl=MEMORY_TTL_SECONDS,
            key_prefix=REDIS_CHAT_PREFIX,
        )

    hist = _memory_store.get(session_id)
    if hist is None:
        hist = ChatMessageHistory()
        _memory_store[session_id] = hist
    return hist


def clearMemory(session_id: str) -> None:
    if _use_redis():
        RedisChatMessageHistory(
            session_id=session_id,
            url=REDIS_URL,
            key_prefix=REDIS_CHAT_PREFIX,
        ).clear()
        return

    _memory_store.pop(session_id, None)

