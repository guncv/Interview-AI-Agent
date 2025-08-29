import os, json
from typing import Optional, Dict, Any, Type, TypeVar, Callable
from redis import Redis
from internal.graph.interview.interview_state import InterviewState
from enum import Enum
from internal.graph.resume.resume_state import ResumeState

T = TypeVar('T')

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
STATE_TTL_SECONDS = int(os.getenv("STATE_TTL_SECONDS", "900"))
STATE_PREFIX = os.getenv("REDIS_STATE_PREFIX", "cpr:state")
LOCK_PREFIX = os.getenv("REDIS_LOCK_PREFIX", "cpr:lock")

class RedisClient:

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or REDIS_URL
        self._redis = None

    @property
    def redis(self):
        if self._redis is None:
            self._redis = Redis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    def _state_key(self, session_id: str) -> str:
        return f"{STATE_PREFIX}:{session_id}"

    def _default_json_converter(self, obj):
        if isinstance(obj, Enum):
            return obj.value
        if isinstance(obj, bytes):
            return obj.decode('utf-8', errors='ignore')
        raise TypeError(f'Object of type {obj.__class__.__name__} is not JSON serializable')

    def save_state(self, session_id: str, data: Dict[str, Any], ttl_seconds: Optional[int] = None, custom_converter: Optional[Callable] = None) -> None:

        converter = custom_converter or self._default_json_converter
        ttl = ttl_seconds or STATE_TTL_SECONDS
        self.redis.setex(self._state_key(session_id), ttl, json.dumps(data, ensure_ascii=False, default=converter))

    def load_state(self, session_id: str) -> Optional[Dict[str, Any]]:

        raw = self.redis.get(self._state_key(session_id))
        if not raw:
            return None
        return json.loads(raw)

    def save_model_state(self, session_id: str, state: T, ttl_seconds: Optional[int] = None, custom_converter: Optional[Callable] = None) -> None:

        state_dict = state.model_dump()
        self.save_state(session_id, state_dict, ttl_seconds, custom_converter)

    def load_model_state(self, session_id: str, model_class: Type[T]) -> Optional[T]:

        data = self.load_state(session_id)
        if not data:
            return None
        return model_class(**data)

    # Legacy functions for backward compatibility
    def save_interview_state(self, session_id: str, state: InterviewState) -> None:
        self.save_model_state(session_id, state)

    def load_interview_state(self, session_id: str) -> Optional[InterviewState]:
        return self.load_model_state(session_id, InterviewState)

    def save_resume_state(self, session_id: str, state: ResumeState) -> None:
        self.save_model_state(session_id, state)

    def load_resume_state(self, session_id: str) -> Optional[ResumeState]:
        return self.load_model_state(session_id, ResumeState)

    def clear_state(self, session_id: str) -> None:
        self.redis.delete(self._state_key(session_id))

    def acquire_lock(self, session_id: str, ttl: int = 5) -> bool:
        return bool(self.redis.set(f"{LOCK_PREFIX}:{session_id}", "1", nx=True, ex=ttl))

    def release_lock(self, session_id: str) -> None:
        self.redis.delete(f"{LOCK_PREFIX}:{session_id}")

    def close(self):
        if self._redis:
            self._redis.close()
            self._redis = None


redis_client = RedisClient()