from internal.domain.models.interview import HealthCheckResponse, InterviewRequest, RequirementsRequest
from internal.shared.exception import InterviewSimulationException
from internal.domain.exception import InterviewSimulationErrorCodes
from internal.adapters.log.logger import logger
from internal.service.interview_graph import InterviewGraph
from internal.adapters.db.redis import redis_client
from internal.adapters.vector_db.ingestion_loader import ingest_document
from internal.domain.models.vector import VectorCollections
from internal.domain.models.interview import FeedbackAndScoreRequest, FeedbackAndScoreResponse

class InterviewService:
    def __init__(self):
        self.interview_graph = InterviewGraph()
        self.redis_client = redis_client

    async def health_check(self):
        logger.info("[Health Check Service Called: ]")
        try:
            resp = HealthCheckResponse(message="OK")
            return resp
        except (InterviewSimulationException, Exception) as e:
            if type(e) != InterviewSimulationException:
                e = InterviewSimulationException(error_code=InterviewSimulationErrorCodes.INTERNAL_ERROR, description=f"[{type(e).__name__}]: {str(e)}")
            logger.error(f"[Health Check Service Error]: {e}")
            e.raise_HTTPException()
            
    async def interview(self, request: InterviewRequest):
        logger.info(f"[Interview Service Called: ]")
        try:
            resp = self.interview_graph.invoke(request.session_id, request.user_input)
            redis_client.save_interview_state(request.session_id, resp)
            
            return resp
        
        except (InterviewSimulationException, Exception) as e:
            if type(e) != InterviewSimulationException:
                e = InterviewSimulationException(error_code=InterviewSimulationErrorCodes.INTERNAL_ERROR, description=f"[{type(e).__name__}]: {str(e)}")
            logger.error(f"[Interview Service Error]: {e}")
            e.raise_HTTPException()
    
    async def requirements(self, request: RequirementsRequest) -> None:
        logger.info(f"[Requirements Service Called:]")
        
        try:
            metadata = {
                "user_id": request.user_id,
                "resume_id": request.resume_id,
            }
            ingest_document(VectorCollections.RESUMES, request.resume_file, request.session_id, metadata)
            return None

        except (InterviewSimulationException, Exception) as e:
            if not isinstance(e, InterviewSimulationException):
                e = InterviewSimulationException(
                    error_code=InterviewSimulationErrorCodes.INTERNAL_ERROR,
                    description=f"[{type(e).__name__}]: {str(e)}"
                )
            logger.error(f"[Requirements Service Error]: {e}")
            e.raise_HTTPException()
