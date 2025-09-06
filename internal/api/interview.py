from fastapi import APIRouter, Response, UploadFile, File, Form
from fastapi import status
from internal.shared.exception import InterviewSimulationException
from internal.domain.exception import InterviewSimulationErrorCodes
from internal.adapters.log.logger import logger
from internal.service.interview import InterviewService
from internal.domain.models.interview import InterviewRequest
from internal.domain.models.interview import RequirementsRequest

router = APIRouter()

interview_service = InterviewService()

@router.get("/health")
async def health_check_api():
    logger.info("[Health Check API Called: ]")
    try:
        resp = await interview_service.health_check()
        return Response(
            status_code=status.HTTP_200_OK,
            content=resp.model_dump()
        )
    except (InterviewSimulationException, Exception) as e:
        if type(e) != InterviewSimulationException:
            e = InterviewSimulationException(error_code=InterviewSimulationErrorCodes.INTERNAL_ERROR, description=f"[{type(e).__name__}]: {str(e)}")
        logger.error(f"[Health Check API Error]: {e}")
        e.raise_HTTPException()

@router.post("/interview")
async def interview_api(request: InterviewRequest):
    logger.info(f"[Interview API Called: ]")
    try:
        resp = await interview_service.interview(request)
        return Response(
            status_code=status.HTTP_200_OK,
            content=resp.model_dump()
        )
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
    logger.info(f"[Requirements API Called: ]")
    try:
        file_bytes = await resume_file.read()

        request = RequirementsRequest(
            user_id=user_id,
            resume_id=resume_id,
            resume_file=file_bytes,
            session_id=session_id,
        )

        resp = await interview_service.requirements(request)
        return Response(
            status_code=status.HTTP_204_NO_CONTENT
            )
    except (InterviewSimulationException, Exception) as e:
        if not isinstance(e, InterviewSimulationException):
            e = InterviewSimulationException(
                error_code=InterviewSimulationErrorCodes.INTERNAL_ERROR,
                description=f"[{type(e).__name__}]: {str(e)}"
            )
        logger.error(f"[Requirements API Error]: {e}")
        e.raise_HTTPException()

