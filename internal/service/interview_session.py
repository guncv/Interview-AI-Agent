from typing import Optional
from internal.shared.exception import InterviewSimulationException
from internal.domain.exception import InterviewSimulationErrorCodes
from internal.adapters.log.logger import logger
from internal.adapters.db.postgres import postgres_client


class InterviewSessionService:
    def __init__(self):
        self.db_client = postgres_client
    
    async def get_resume_context(self, session_id: str) -> Optional[dict]:
        logger.info(f"[InterviewSessionService] Getting resume_context for session_id: {session_id}")
        
        try:
            resume_context = self.db_client.get_resume_context_by_session_id(session_id)
            
            if not resume_context:
                logger.warning(f"[InterviewSessionService] No resume_context found for session_id: {session_id}")
                return None
            
            logger.info(f"[InterviewSessionService] Successfully retrieved resume_context for session_id: {session_id}")
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


# Singleton instance
interview_session_service = InterviewSessionService()

