from typing import Optional, Dict, Any
from core.utils.exception import InterviewSimulationException
from domain.enums.exception import InterviewSimulationErrorCodes
from core.log.logger import logger
from infrastructure.db.postgres import postgres_client
from infrastructure.redis.redis import redis_client
from domain.models.redis import RedisKeys


class InterviewSessionService:
    def __init__(self):
        self.db_client = postgres_client
        self.cache_client = redis_client
        
    async def get_bias_prompt(self, session_id: str) -> str:
        try:
            bias_prompt = self.cache_client.load_interview_bias_prompt(session_id)
            if bias_prompt:
                return bias_prompt
        except Exception as e:
            logger.error(f"[Get Bias Prompt]: Error getting bias prompt: {e}")
            raise
        
        try:
            bias_prompt = await self.db_client.get_bias_prompt_by_session_id(session_id)
            if bias_prompt:
                self.cache_client.save_interview_bias_prompt(session_id, bias_prompt, RedisKeys.BIAS_PROMPT_TTL_SECONDS.value)
                return bias_prompt
            else:
                return ""
        except Exception as e:
            logger.error(f"[Get Bias Prompt]: Error getting bias prompt: {e}")
            raise
    
    async def get_resume_context(self, session_id: str) -> Dict[str, Any]:
        try:
            resume_context = self.cache_client.load_resume_context(session_id)
            if resume_context:
                return resume_context
            
        except Exception as cache_error:
            logger.warning(f"[InterviewSessionService] Cache error, falling back to database: {cache_error}")
        
        try:
            resume_context = await self.db_client.get_resume_context_by_session_id(session_id)
            
            if resume_context:
                try:
                    self.cache_client.save_resume_context(session_id, resume_context, RedisKeys.RESUME_CONTEXT_TTL_SECONDS.value)
                except Exception as cache_save_error:
                    logger.warning(f"[InterviewSessionService] Failed to cache resume_context: {cache_save_error}")
            else:
                logger.warning(f"[InterviewSessionService] No resume_context found for session_id: {session_id}")
            
            return resume_context
        
        except (InterviewSimulationException, Exception) as e:
            if type(e) != InterviewSimulationException:
                e = InterviewSimulationException(
                    error_code=InterviewSimulationErrorCodes.INTERNAL_ERROR,
                    description=f"[{type(e).__name__}]: {str(e)}"
                )
            logger.error(f"[InterviewSessionService] Error getting resume_context: {e}")
            e.raise_HTTPException()
    
    def close(self):
        self.db_client.close()


interview_session_service = InterviewSessionService()

