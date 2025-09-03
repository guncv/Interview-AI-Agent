from internal.domain.models.interview import HealthCheckResponse, InterviewRequest, RequirementsRequest, RequirementsResponse
from internal.utils.exception import InterviewSimulationException
from internal.domain.exception import InterviewSimulationErrorCodes
from internal.infra.log.logger import logger
from internal.graph.interview.interview_graph import InterviewGraph
from internal.graph.resume.resume_graph import ResumeGraph
from internal.infra.db.redis import redis_client
from typing import Optional

class InterviewService:
    def __init__(self):
        self.interview_graph = InterviewGraph()
        self.resume_graph = ResumeGraph()
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
        logger.info(f"[Requirements Service Called:]")
        
        try:
            resp = self.resume_graph.invoke(request)

            result = RequirementsResponse(
                parsed_json=resp.prompt_info
            )
            
            logger.info(f"[Requirements Service Response]: {result}")

            bias_prompt = []

            def extend_split(value: Optional[str]):
                if isinstance(value, str) and value.strip():
                    bias_prompt.extend(value.strip().split(" "))

            if resp.prompt_info.first_name:
                extend_split(resp.prompt_info.first_name)

            if resp.prompt_info.last_name:
                extend_split(resp.prompt_info.last_name)

            if resp.prompt_info.experience:
                logger.info(f"[Requirements Service Experience]: {resp.prompt_info.experience}")
                for experience in resp.prompt_info.experience:
                    extend_split(experience.company)
                    extend_split(experience.position)
                    extend_split(experience.job_type)

            if resp.prompt_info.education:
                logger.info(f"[Requirements Service Education]: {resp.prompt_info.education}")
                for education in resp.prompt_info.education:
                    extend_split(education.school)
                    extend_split(education.degree)
                    extend_split(education.field_of_study)

            if resp.prompt_info.skills:
                logger.info(f"[Requirements Service Skills]: {resp.prompt_info.skills}")
                for skill in resp.prompt_info.skills:
                    extend_split(skill)

            if resp.prompt_info.certifications:
                logger.info(f"[Requirements Service Certifications]: {resp.prompt_info.certifications}")
                for certification in resp.prompt_info.certifications:
                    extend_split(certification)

            if resp.prompt_info.languages:
                logger.info(f"[Requirements Service Languages]: {resp.prompt_info.languages}")
                for language in resp.prompt_info.languages:
                    extend_split(language)

            logger.info(f"[Requirements Service Bias Prompt]: {bias_prompt}")

            self.redis_client.save_session_bias_prompt(
                request.session_id,
                bias_prompt,
                ttl_seconds=60 * 60
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
