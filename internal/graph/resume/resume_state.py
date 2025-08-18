from pydantic import BaseModel
from typing import Optional
from internal.graph.resume.resume_step import ResumeStep
    
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
    summary_text: Optional[str] = None
    error_message: Optional[str] = None
    should_pause: Optional[bool] = False
    match_score: Optional[int] = 0
    
class PromptInfo(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    experience: Optional[list[str]] = None
    education: Optional[list[str]] = None
    skills: Optional[list[str]] = None
    certifications: Optional[list[str]] = None
    languages: Optional[str] = None