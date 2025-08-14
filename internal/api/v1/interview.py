from fastapi import APIRouter

from internal.utils.exception import InterviewSimulationException
from internal.domain.exception import InterviewSimulationErrorCodes
from internal.infra.log.logger import logger
from internal.service.interview_service import InterviewService

router = APIRouter()

interview_service = InterviewService()

@router.get("/health")
async def health_check_api():
    logger.info("[Health Check API Called]")
    try:
        resp = await interview_service.health_check()
        return resp
    except (InterviewSimulationException, Exception) as e:
        if type(e) != InterviewSimulationException:
            e = InterviewSimulationException(error_code=InterviewSimulationErrorCodes.INTERNAL_ERROR, description=f"[{type(e).__name__}]: {str(e)}")
        logger.error(f"[Health Check API Error]: {e}")
        e.raise_HTTPException()