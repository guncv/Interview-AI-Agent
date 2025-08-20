from pydantic import BaseModel
from io import BytesIO
from typing import Any, Optional

class HealthCheckResponse(BaseModel):
    message: str

class InterviewRequest(BaseModel):
    session_id: str
    user_input: str
    
class InterviewResponse(BaseModel):
    message: str
    
class RequirementsRequest(BaseModel):
    session_id: str
    resume_file: bytes
    position: str
    company: str
    work_type: str
    job_requirements: str
    interview_type: str
    language: str
    
class RequirementsResponse(BaseModel):
    prompt_info: Any