from internal.domain.models.interview import HealthCheckResponse, InterviewRequest, RequirementsRequest, RequirementsResponse
from internal.utils.exception import InterviewSimulationException
from internal.domain.exception import InterviewSimulationErrorCodes
from internal.infra.log.logger import logger
from internal.graph.interview.interview_graph import InterviewGraph
from internal.llm.loader import llm
from internal.graph.resume.resume_graph import ResumeGraph

class InterviewService:
    def __init__(self):
        self.interview_graph = InterviewGraph(llm)
        self.resume_graph = ResumeGraph(llm)

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
            return resp
        except (InterviewSimulationException, Exception) as e:
            if type(e) != InterviewSimulationException:
                e = InterviewSimulationException(error_code=InterviewSimulationErrorCodes.INTERNAL_ERROR, description=f"[{type(e).__name__}]: {str(e)}")
            logger.error(f"[Interview Service Error]: {e}")
            e.raise_HTTPException()
    
    async def requirements(self, request: RequirementsRequest):
        logger.info(f"[Requirements Service Called: ]")
        try:
            resp = self.resume_graph.invoke(request)
        
            result = RequirementsResponse(
                parsed_json=resp.prompt_info
            )

            return result
        except (InterviewSimulationException, Exception) as e:
            if not isinstance(e, InterviewSimulationException):
                e = InterviewSimulationException(
                    error_code=InterviewSimulationErrorCodes.INTERNAL_ERROR,
                    description=f"[{type(e).__name__}]: {str(e)}"
                )
            logger.error(f"[Requirements Service Error]: {e}")
            e.raise_HTTPException()