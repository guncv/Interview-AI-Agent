from pydantic import BaseModel
from io import BytesIO
from typing import Any, Optional, Dict, List

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

class ParsedResumeInfo(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    experience: Optional[List[str]] = None
    education: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    certifications: Optional[List[str]] = None
    languages: Optional[str] = None
    
class ParedResumeResp(BaseModel):
    parsed_json: ParsedResumeInfo
    raw_text: Optional[str] = None
    summary_text: Optional[str] = None