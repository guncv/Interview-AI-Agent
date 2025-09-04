import sys

from enum import Enum
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from internal.domain.exception import InterviewSimulationErrorCodes

class InterviewSimulationExceptionBase(Exception):
    def __init__(self, error_code: Enum , description: str, *args, **kwargs):
        self.error_code = error_code
        self.ins_code = error_code.value['INS_CODE']
        self.ins_message = error_code.name
        self.description = description
        self.detail = {'error_code': self.ins_code, 'error_message': self.ins_message, 'description': self.description}
        self.traceback = sys.exc_info()

        msg = '[INS-{0}] {1}: {2}'.format(error_code.value['INS_CODE'], error_code.name, description)
        super().__init__(msg)
    
    def get_detail(self) -> dict:
        return self.detail

class InterviewSimulationException(InterviewSimulationExceptionBase):
    def __init__(self, error_code: InterviewSimulationErrorCodes, description: str, *args, **kwargs):
        self.error_code_http = error_code.value['HTTP_CODE']
        super().__init__(error_code, description)

    def raise_HTTPException(self):
        raise HTTPException(status_code=self.error_code_http, detail=self.detail)
    
    def convert_to_JSONResponse(self, resp_uuid: str = None) -> JSONResponse:
        content = {"detail": self.detail}
        if resp_uuid:
            content["resp_uuid"] = resp_uuid
        return JSONResponse(status_code=self.error_code_http, content=content)

def convert_to_InterviewSimulationException(error_code_http: int, detail: dict) -> InterviewSimulationException:
    """
    detail = {
        'error_code': self.ins_code,
        'error_message': self.ins_message,
        'description': self.description
    }
    """
    enum_name = detail["error_message"]
    enum_value = {'INS_CODE': detail["ins_code"], 'HTTP_CODE': error_code_http}
    _InterviewSimulationErrorCodes = Enum("_InterviewSimulationErrorCodes", {enum_name: enum_value})
    
    error_code = getattr(_InterviewSimulationErrorCodes, enum_name)
    description = detail["description"]

    return InterviewSimulationException(error_code=error_code, description=description)