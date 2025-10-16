from fastapi import APIRouter, UploadFile, File, Form
from core.utils.exception import InterviewSimulationException
from domain.enums.exception import InterviewSimulationErrorCodes
from core.log.logger import logger
from services.interview import InterviewService
from domain.models.interview import InterviewRequest
from domain.models.interview import RequirementsRequest

router = APIRouter()

interview_service = InterviewService()

@router.get("/health")
async def health_check_api():
    try:
        resp = await interview_service.health_check()
        return resp
    except (InterviewSimulationException, Exception) as e:
        if type(e) != InterviewSimulationException:
            e = InterviewSimulationException(error_code=InterviewSimulationErrorCodes.INTERNAL_ERROR, description=f"[{type(e).__name__}]: {str(e)}")
        logger.error(f"[Health Check API Error]: {e}")
        e.raise_HTTPException()

@router.post("/interview")
async def interview_api(request: InterviewRequest):
    try:
        resp = await interview_service.interview(request)
        return resp
    except (InterviewSimulationException, Exception) as e:
        if type(e) != InterviewSimulationException:
            e = InterviewSimulationException(error_code=InterviewSimulationErrorCodes.INTERNAL_ERROR, description=f"[{type(e).__name__}]: {str(e)}")
        logger.error(f"[Interview API Error]: {e}")
        e.raise_HTTPException()

@router.post("/requirements")
async def requirements_api(
    user_id: str = Form(...),
    resume_id: str= Form(...),
    session_id: str= Form(...),
    resume_file: UploadFile = File(...),
):
    try:
        file_bytes = await resume_file.read()

        request = RequirementsRequest(
            user_id=user_id,
            resume_id=resume_id,
            resume_file=file_bytes,
            session_id=session_id,
        )

        await interview_service.requirements(request)

    except (InterviewSimulationException, Exception) as e:
        if not isinstance(e, InterviewSimulationException):
            e = InterviewSimulationException(
                error_code=InterviewSimulationErrorCodes.INTERNAL_ERROR,
                description=f"[{type(e).__name__}]: {str(e)}"
            )
        logger.error(f"[Requirements API Error]: {e}")
        e.raise_HTTPException()

