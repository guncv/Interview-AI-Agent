from pydantic import BaseModel
from typing import Optional
from internal.domain.models.resume_step import ResumeStep
    
class ResumeState(BaseModel):
    session_id: str
    file_input: bytes = None
    job_requirements: str = None
    position: str = None
    company: str = None
    work_type: str = None
    interview_type: str = None
    language: str = None
    current_step: ResumeStep

    resume_text: Optional[str] = None
    prompt_info: Optional['PromptInfo'] = None
    error_message: Optional[str] = None
    should_pause: Optional[bool] = False
    match_score: Optional[int] = 0

class Experience(BaseModel):
    company: Optional[str] = None
    position: Optional[str] = None
    job_type: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None

class Education(BaseModel):
    school: Optional[str] = None
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None

class PromptInfo(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    experience: Optional[list[Experience]] = None
    education: Optional[list[Education]] = None
    skills: Optional[list[str]] = None
    certifications: Optional[list[str]] = None
    languages: Optional[str] = None
