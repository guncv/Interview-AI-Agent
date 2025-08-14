from pydantic import BaseModel
from typing import Optional
from internal.graph.resume.resume_step import ResumeStep
from io import BytesIO
    
class ResumeState(BaseModel):
    session_id: str
    file_input: Optional[BytesIO] = None
    current_step: ResumeStep

    resume_text: Optional[str] = None
    parsed_info: Optional[dict] = None
    job_detail: Optional[str] = None
    enriched_context: Optional[str] = None

    message: Optional[str] = None
    match_score: Optional[int] = 0
    error_message: Optional[str] = None

    should_pause: Optional[bool] = False