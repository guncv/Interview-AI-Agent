from fastapi import APIRouter, Response
from fastapi import status
from internal.shared.exception import InterviewSimulationException
from internal.domain.exception import InterviewSimulationErrorCodes
from internal.adapters.log.logger import logger
from internal.service.feedback_and_score import FeedbackAndScoreService
from internal.domain.models.interview import FeedbackAndScoreRequest

router = APIRouter()

feedback_and_score_service = FeedbackAndScoreService()

@router.post("")
async def feedback_and_score_api(request: FeedbackAndScoreRequest):
    logger.info(f"[Feedback and Score API Called: ]")
    try:
        resp = await feedback_and_score_service.feedback_and_score(request)
        return resp
    except (InterviewSimulationException, Exception) as e:
        if type(e) != InterviewSimulationException:
            e = InterviewSimulationException(error_code=InterviewSimulationErrorCodes.INTERNAL_ERROR, description=f"[{type(e).__name__}]: {str(e)}")
        logger.error(f"[Feedback and Score API Error]: {e}")
        e.raise_HTTPException()