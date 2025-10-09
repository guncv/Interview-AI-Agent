import json
from typing import Optional, Dict, Any, Type, TypeVar, Callable, List
from redis import Redis
from internal.domain.models.interview import InterviewState
from enum import Enum
from internal.config.config import nested_config as config
from internal.domain.models.speech_recognize import SpeechRecognize, Word
import dataclasses
from internal.domain.models.redis import RedisKeys
T = TypeVar('T')

STATE_TTL_SECONDS = RedisKeys.STATE_TTL_SECONDS.value
STATE_PREFIX = RedisKeys.STATE_PREFIX.value
LOCK_PREFIX = RedisKeys.LOCK_PREFIX.value
SEGMENT_AUDIO_PREFIX = RedisKeys.SEGMENT_AUDIO_PREFIX.value
RESUME_CONTEXT_PREFIX = RedisKeys.RESUME_CONTEXT_PREFIX.value
BIAS_PROMPT_PREFIX = RedisKeys.BIAS_PROMPT_PREFIX.value

class RedisClient:
    def __init__(self):
        self.redis_url = config["redis"]["url"]
        self._redis = None

    @property
    def redis(self):
        if self._redis is None:
            self._redis = Redis.from_url(self.redis_url, decode_responses=False)
        return self._redis

    def _segment_audio_key(self, session_id: str, segment_id: str) -> str:
        return f"{SEGMENT_AUDIO_PREFIX}:{session_id}:{segment_id}"

    def _state_key(self, session_id: str) -> str:
        return f"{STATE_PREFIX}:{session_id}"
    
    def _resume_context_key(self, session_id: str) -> str:
        return f"{RESUME_CONTEXT_PREFIX}:{session_id}"
    
    def _bias_prompt_key(self, session_id: str) -> str:
        return f"{BIAS_PROMPT_PREFIX}:{session_id}"
    
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
    
    def save_interview_state(self, session_id: str, state: InterviewState) -> None:
        self._save_model_state(session_id, state)

    def load_interview_state(self, session_id: str) -> Optional[InterviewState]:
        return self._load_model_state(session_id, InterviewState) 
    
    def save_segment_audio(self, session_id: str, segment_id: str, audio: bytes) -> None:
        key = self._segment_audio_key(session_id, segment_id)
        self.redis.set(key, audio)

    def get_segment_audio(self, session_id: str, segment_id: str) -> Optional[bytes]:
        key = self._segment_audio_key(session_id, segment_id)
        audio_data = self.redis.get(key)
        return audio_data if audio_data else None

    def clear_segment_audio(self, session_id: str, segment_id: str) -> None:
        key = self._segment_audio_key(session_id, segment_id)
        self.redis.delete(key)

    def clear_state(self, session_id: str) -> None:
        self.redis.delete(self._state_key(session_id))

    def acquire_lock(self, session_id: str, ttl: int = 5) -> bool:
        return bool(self.redis.set(f"{LOCK_PREFIX}:{session_id}", "1", nx=True, ex=ttl))

    def release_lock(self, session_id: str) -> None:
        self.redis.delete(f"{LOCK_PREFIX}:{session_id}")
    
    def save_interview_bias_prompt(self, session_id: str, bias_prompt: str, ttl_seconds: int) -> None:
        key = self._bias_prompt_key(session_id)
        self.redis.setex(key, ttl_seconds, bias_prompt)
    
    def load_interview_bias_prompt(self, session_id: str) -> Optional[str]:
        key = self._bias_prompt_key(session_id)
        resp = self.redis.get(key)
        return resp
    
    def save_resume_context(self, session_id: str, resume_context: Dict[str, Any], ttl_seconds: int) -> None:
        key = self._resume_context_key(session_id)
        ttl = ttl_seconds
        self.redis.setex(key, ttl, json.dumps(resume_context, ensure_ascii=False, default=self._default_json_converter))
    
    def load_resume_context(self, session_id: str) -> Dict[str, Any]:
        key = self._resume_context_key(session_id)
        raw = self.redis.get(key)
        if not raw:
            return {}
        return json.loads(raw)

    def close(self):
        if self._redis:
            self._redis.close()
            self._redis = None


redis_client = RedisClient()