from pydantic import BaseModel
from typing import Optional
from enum import Enum

class HealthCheckResponse(BaseModel):
    message: str

class InterviewRequest(BaseModel):
    session_id: str
    user_input: str
    
class InterviewResponse(BaseModel):
    message: str
    
class RequirementsRequest(BaseModel):
    user_id: str
    resume_id: str
    resume_file: bytes
    session_id: str

class InterviewStep(Enum):
    ROLE_SELECTION = 1
    ASK_QUESTION = 2
    PARSE_ANSWER = 3
    GIVE_FEEDBACK = 4
    END_INTERVIEW = 5
    ERROR = -1
    
class InterviewNode(Enum):
    ROUTER = "router"
    ASK_QUESTION = "ask_question"
    PARSE_ANSWER = "parse_answer"
    GIVE_FEEDBACK = "give_feedback"
    END_INTERVIEW = "end_interview"
    ERROR_HANDLER = "error_handler"
    
class AskQuestionRes(BaseModel):
    message: str
    
class InterviewState(BaseModel):
    session_id: str
    user_input: str
    current_step: InterviewStep
    message: Optional[str] = None
    role: Optional[str] = None
    question: Optional[str] = None
    feedback: Optional[str] = None
    score: Optional[float] = None
    match_score: Optional[float] = None
    is_finished: bool = False
    should_pause: bool = True
    error_message: Optional[str] = None
