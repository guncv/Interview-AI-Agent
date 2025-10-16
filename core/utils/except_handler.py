from fastapi import Request
from fastapi.exceptions import RequestValidationError, ResponseValidationError

from domain.enums.exception import InterviewSimulationErrorCodes
from core.utils.exception import InterviewSimulationException

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    try:
        detail = exc.errors()
        description = f'{detail[0]["type"]}: {str(detail[0]["loc"])}'

        e = InterviewSimulationException(error_code=InterviewSimulationErrorCodes.INCORRECT_REQUEST_FORMAT, description=description)
        return e.convert_to_JSONResponse()
    
    except (InterviewSimulationException, Exception) as e:
        if type(e) != InterviewSimulationException:
            e = InterviewSimulationException(error_code=InterviewSimulationErrorCodes.INTERNAL_ERROR, description=f"[{type(e).__name__}]: {str(e)}")
        return e.convert_to_JSONResponse()

async def response_validation_exception_handler(request: Request, exc: ResponseValidationError):
    try:
        e = InterviewSimulationException(error_code=InterviewSimulationErrorCodes.INTERNAL_ERROR, description=exc.errors())
        return e.convert_to_JSONResponse()
    
    except (InterviewSimulationException, Exception) as e:
        if type(e) != InterviewSimulationException:
            e = InterviewSimulationException(error_code=InterviewSimulationErrorCodes.INTERNAL_ERROR, description=f"[{type(e).__name__}]: {str(e)}")
        return e.convert_to_JSONResponse()