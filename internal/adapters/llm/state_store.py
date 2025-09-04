from __future__ import annotations
import os
from typing import Dict

from langchain_community.chat_message_histories import (
    ChatMessageHistory,
    RedisChatMessageHistory,
)

REDIS_URL: str | None = os.getenv("REDIS_URL")
MEMORY_TTL_SECONDS: int = int(os.getenv("MEMORY_TTL_SECONDS", "3600"))
REDIS_CHAT_PREFIX: str = os.getenv("REDIS_CHAT_PREFIX", "cpr:chat")

_memory_store: Dict[str, ChatMessageHistory] = {}

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
