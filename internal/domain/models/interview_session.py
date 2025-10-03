from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class InterviewSession(BaseModel):
    id: str
    user_id: str
    resume_id: str
    position: str
    modality: str
    status: str
    is_consent: bool
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    overall_score: Optional[float] = None
    summary_md: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    soft_delete: bool = False
    is_started_conversation: bool = False
    resume_file_name: Optional[str] = None
    current_state: Optional[str] = None
    current_state_id: Optional[str] = None
    finalize_status: Optional[str] = None
    is_timed_out: bool = False
    bias_prompt: Optional[str] = None
    resume_context: Optional[Dict[str, Any]] = None


class GetInterviewSessionRequest(BaseModel):
    session_id: str


class GetInterviewSessionResponse(BaseModel):
    session: Optional[InterviewSession] = None
    resume_context: Optional[Dict[str, Any]] = None

