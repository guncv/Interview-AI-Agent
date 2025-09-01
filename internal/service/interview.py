from internal.domain.models.interview import HealthCheckResponse, InterviewRequest, RequirementsRequest, RequirementsResponse
from internal.utils.exception import InterviewSimulationException
from internal.domain.exception import InterviewSimulationErrorCodes
from internal.infra.log.logger import logger
from internal.graph.interview.interview_graph import InterviewGraph
from internal.llm.loader import llm
from internal.graph.resume.resume_graph import ResumeGraph
from internal.infra.db.redis import redis_client

class InterviewService:
    def __init__(self):
        self.interview_graph = InterviewGraph(llm)
        self.resume_graph = ResumeGraph(llm)
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
            
            logger.info(f"[Requirements Service Response]: {result}")
            
            bias_prompt = []
            if resp.prompt_info.first_name:
                bias_prompt.append(resp.prompt_info.first_name)
            if resp.prompt_info.last_name:
                bias_prompt.append(resp.prompt_info.last_name)
            if resp.prompt_info.experience:
                logger.info(f"[Requirements Service Experience]: {resp.prompt_info.experience}")
                for experience in resp.prompt_info.experience:
                    bias_prompt.append(experience.company)
                    bias_prompt.append(experience.position)
                    bias_prompt.append(experience.job_type)
            if resp.prompt_info.education:
                logger.info(f"[Requirements Service Education]: {resp.prompt_info.education}")
                for education in resp.prompt_info.education:
                    bias_prompt.append(education.school)
                    bias_prompt.append(education.degree)
                    bias_prompt.append(education.field_of_study)
            if resp.prompt_info.skills:
                logger.info(f"[Requirements Service Skills]: {resp.prompt_info.skills}")
                for skill in resp.prompt_info.skills:
                    bias_prompt.append(skill)
            if resp.prompt_info.certifications:
                logger.info(f"[Requirements Service Certifications]: {resp.prompt_info.certifications}")
                for certification in resp.prompt_info.certifications:
                    bias_prompt.append(certification)
            if resp.prompt_info.languages:
                logger.info(f"[Requirements Service Languages]: {resp.prompt_info.languages}")
                for language in resp.prompt_info.languages:
                    bias_prompt.append(language)
            
            logger.info(f"[Requirements Service Bias Prompt]: {bias_prompt}")
            self.redis_client.save_session_bias_prompt(request.session_id, bias_prompt, ttl_seconds=60 * 60)

            return result
        
        except (InterviewSimulationException, Exception) as e:
            if not isinstance(e, InterviewSimulationException):
                e = InterviewSimulationException(
                    error_code=InterviewSimulationErrorCodes.INTERNAL_ERROR,
                    description=f"[{type(e).__name__}]: {str(e)}"
                )
            logger.error(f"[Requirements Service Error]: {e}")
            e.raise_HTTPException()