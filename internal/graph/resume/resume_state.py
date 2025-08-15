from pydantic import BaseModel
from typing import Optional
from internal.graph.resume.resume_step import ResumeStep
    
class ResumeState(BaseModel):
    session_id: str
    file_input: Optional[bytes] = None
    job_requirements: Optional[str] = None
    position: Optional[str] = None
    company: Optional[str] = None
    work_type: Optional[str] = None
    interview_type: Optional[str] = None
    language: Optional[str] = None
    current_step: ResumeStep

    resume_text: Optional[str] = None
    parsed_info: Optional[dict] = None
    job_detail: Optional[str] = None
    enriched_context: Optional[str] = None
    error_message: Optional[str] = None
    should_pause: Optional[bool] = False
    match_score: Optional[int] = 0