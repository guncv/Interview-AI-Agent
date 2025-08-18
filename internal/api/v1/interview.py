from fastapi import APIRouter, UploadFile, File, Form
from internal.utils.exception import InterviewSimulationException
from internal.domain.exception import InterviewSimulationErrorCodes
from internal.infra.log.logger import logger
from io import BytesIO
from internal.service.interview_service import InterviewService
from internal.domain.models.interview import InterviewRequest
from internal.domain.models.interview import RequirementsRequest

router = APIRouter()

interview_service = InterviewService()

@router.get("/health")
async def health_check_api():
    logger.info("[Health Check API Called: ]")
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
    logger.info(f"[Interview API Called: ]")
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
    session_id: str = Form(...),
    position: str = Form(...),
    company: str = Form(...),
    work_type: str = Form(...),
    job_requirements: str = Form(...),
    interview_type: str = Form(...),
    language: str = Form(...),
    resume_file: UploadFile = File(...),
):
    logger.info(f"[Requirements API Called: ]")
    try:
        file_bytes = await resume_file.read()

        request = RequirementsRequest(
            session_id=session_id,
            resume_file=file_bytes,
            position=position,
            company=company,
            work_type=work_type,
            job_requirements=job_requirements,
            interview_type=interview_type,
            language=language,
        )

        resp = await interview_service.requirements(request)
        return resp
    except (InterviewSimulationException, Exception) as e:
        if not isinstance(e, InterviewSimulationException):
            e = InterviewSimulationException(
                error_code=InterviewSimulationErrorCodes.INTERNAL_ERROR,
                description=f"[{type(e).__name__}]: {str(e)}"
            )
        logger.error(f"[Requirements API Error]: {e}")
        e.raise_HTTPException()

