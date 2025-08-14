from pydantic import BaseModel
from typing import Optional
from internal.graph.interview_step import InterviewStep

class InterviewState(BaseModel):
    session_id: str
    user_input: str
    current_step: InterviewStep
    role: Optional[str] = None
    question: Optional[str] = None
    feedback: Optional[str] = None
    score: Optional[float] = None
    is_finished: bool = False
    error_message: Optional[str] = None

class AskQuestionRes(BaseModel):
    message: str