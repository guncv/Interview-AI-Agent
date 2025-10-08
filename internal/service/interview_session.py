from typing import Optional
from internal.shared.exception import InterviewSimulationException
from internal.domain.exception import InterviewSimulationErrorCodes
from internal.adapters.log.logger import logger
from internal.adapters.db.postgres import postgres_client
from internal.adapters.db.redis import redis_client


class InterviewSessionService:
    def __init__(self):
        self.db_client = postgres_client
        self.cache_client = redis_client
    
    async def get_resume_context(self, session_id: str) -> Optional[dict]:
        try:
            resume_context = await self.cache_client.load_resume_context(session_id)
            if resume_context:
                return resume_context
            
        except Exception as cache_error:
            logger.warning(f"[InterviewSessionService] Cache error, falling back to database: {cache_error}")
        
        try:
            resume_context = await self.db_client.get_resume_context_by_session_id(session_id)
            
            if not resume_context:
                logger.warning(f"[InterviewSessionService] No resume_context found for session_id: {session_id}")
                return None
            
            try:
                await self.cache_client.save_resume_context(session_id, resume_context)
            except Exception as cache_save_error:
                logger.warning(f"[InterviewSessionService] Failed to cache resume_context: {cache_save_error}")
            
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

