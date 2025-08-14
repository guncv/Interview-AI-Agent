from internal.domain.models.interview import HealthCheckResponse, InterviewRequest, InterviewResponse
from internal.utils.exception import InterviewSimulationException
from internal.domain.exception import InterviewSimulationErrorCodes
from internal.infra.log.logger import logger
from internal.graph.interview_graph import InterviewGraph
from internal.llm.loader import llm

class InterviewService:
    def __init__(self):
        self.graph = InterviewGraph(llm)

    async def health_check(self):
        logger.info("[Health Check Service Called]")
        try:
            resp = HealthCheckResponse(message="OK")
            return resp
        except (InterviewSimulationException, Exception) as e:
            if type(e) != InterviewSimulationException:
                e = InterviewSimulationException(error_code=InterviewSimulationErrorCodes.INTERNAL_ERROR, description=f"[{type(e).__name__}]: {str(e)}")
            logger.error(f"[Health Check Service Error]: {e}")
            e.raise_HTTPException()
            
    async def interview(self, request: InterviewRequest):
        logger.info("[Interview Service Called]")
        try:
            resp = self.graph.invoke(request.session_id, request.user_input)
            return resp
        except (InterviewSimulationException, Exception) as e:
            if type(e) != InterviewSimulationException:
                e = InterviewSimulationException(error_code=InterviewSimulationErrorCodes.INTERNAL_ERROR, description=f"[{type(e).__name__}]: {str(e)}")
            logger.error(f"[Interview Service Error]: {e}")
            e.raise_HTTPException()