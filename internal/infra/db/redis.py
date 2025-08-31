import os, json
from typing import Optional, Dict, Any, Type, TypeVar, Callable, List
from redis import Redis
from internal.graph.interview.interview_state import InterviewState
from enum import Enum
from internal.graph.resume.resume_state import ResumeState
from internal.config.config import nested_config as config

T = TypeVar('T')

STATE_TTL_SECONDS = int(os.getenv("STATE_TTL_SECONDS", "900"))
STATE_PREFIX = os.getenv("REDIS_STATE_PREFIX", "interview-sim:state")
LOCK_PREFIX = os.getenv("REDIS_LOCK_PREFIX", "interview-sim:lock")
SEGMENT_STT_PREFIX = os.getenv("REDIS_SEGMENT_STT_PREFIX", "interview-sim:segment_stt")
PREV_SEGMENT_PREFIX = os.getenv("REDIS_PREV_SEGMENT_PREFIX", "interview-sim:prev_segment")

class RedisClient:
    def __init__(self):
        self.redis_url = config["redis"]["url"]
        self._redis = None

    @property
    def redis(self):
        if self._redis is None:
            self._redis = Redis.from_url(self.redis_url, decode_responses=False)
        return self._redis

    def _segment_stt_key(self, session_id: str, segment_id: str) -> str:
        return f"{SEGMENT_STT_PREFIX}:{session_id}:{segment_id}"

    def _prev_segment_key(self, session_id: str, segment_id: str) -> str:
        return f"{PREV_SEGMENT_PREFIX}:{session_id}:{segment_id}"

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

    def _save_model_state(self, session_id: str, state: T, ttl_seconds: Optional[int] = None, custom_converter: Optional[Callable] = None) -> None:

        state_dict = state.model_dump()
        self.save_state(session_id, state_dict, ttl_seconds, custom_converter)

    def _load_model_state(self, session_id: str, model_class: Type[T]) -> Optional[T]:

        data = self.load_state(session_id)
        if not data:
            return None
        return model_class(**data)

    def save_resume_state(self, session_id: str, state: ResumeState) -> None:
        self._save_model_state(session_id, state)

    def load_resume_state(self, session_id: str) -> Optional[ResumeState]:
        return self._load_model_state(session_id, ResumeState)
    
    def save_interview_state(self, session_id: str, state: InterviewState) -> None:
        self._save_model_state(session_id, state)

    def load_interview_state(self, session_id: str) -> Optional[InterviewState]:
        return self._load_model_state(session_id, InterviewState)
    
    def save_prev_segment_chunk(self, session_id: str, segment_id: str, chunk: bytes) -> None:
        key = self._prev_segment_key(session_id, segment_id)
        self.redis.set(key, chunk)
    
    def get_prev_segment_chunk(self, session_id: str, segment_id: str) -> bytes:
        key = self._prev_segment_key(session_id, segment_id)
        prev_segment = self.redis.get(key)
        return prev_segment if prev_segment else None
        
    def save_segment_stt(self, session_id: str, segment_id: str, stt: str) -> None:
        key = self._segment_stt_key(session_id, segment_id)

        segment_data = self.redis.get(key)
        if segment_data:
            segment_data = json.loads(segment_data)
        else:
            segment_data = []

        segment_data.append(stt)

        self.redis.set(key, json.dumps(segment_data))

    def get_segment_stt(self, session_id: str, segment_id: str) -> Optional[List[str]]:
        key = self._segment_stt_key(session_id, segment_id)
        segment_data = self.redis.get(key)
        if segment_data:
            return json.loads(segment_data)
        return None

    def clear_segment_stt(self, session_id: str, segment_id: str) -> None:
        key = self._segment_stt_key(session_id, segment_id)
        self.redis.delete(key)

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