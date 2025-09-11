import string
from pydantic import BaseModel
from typing import List, Optional
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
    
class Criteria(BaseModel):
	criterion_id: str
	criterion_code: str
	criterion_name: str
	criterion_description_md: str
	criterion_weight: str
	criterion_max_score: str

class FeedbackAndScoreRequest(BaseModel):
    user_message: str
    interviewer_message: str
    rubric_name: str
    rubric_description_md: str
    criteria: List[Criteria]

class CriteriaScore(BaseModel):
    criterion_id: str
    criterion_code: str
    criterion_name: str
    criterion_score: int
    criterion_feedback: str
    
class FeedbackAndScoreResponse(BaseModel):
    overall_score: float
    overall_feedback: str
    criteria_scores: List[CriteriaScore]
    
class QueryVectorDBRes(BaseModel):
    message: str
    
class InterviewStep(Enum):
    QUERY_VECTOR_DB = 1
    PROCESS_ANSWER = 2
    STORE_ANSWER = 3
    END_TURN = 4
    ERROR = -1
    
class InterviewNode(Enum):
    ROUTER = "router"
    QUERY_VECTOR_DB = "query_vector_db"
    PROCESS_ANSWER = "process_answer"
    STORE_ANSWER = "store_answer"
    END_TURN = "end_turn"
    ERROR_HANDLER = "error_handler"
    
class InterviewProcessStep(Enum):
    ROUTER = 0
    GREETING = 1
    INTRO = 2
    ASK_EXPERIENCE = 3
    ASK_PROJECT = 4
    TECHNICAL_QUESTION = 5
    BEHAVIORAL_QUESTION = 6
    WRAP_UP = 7
    ERROR_HANDLER = -1
    
class InterviewState(BaseModel):
    session_id: str
    user_input: str
    prompt: str
    message: Optional[str] = None
    error_message: Optional[str] = None
    current_step: InterviewProcessStep

class InterviewServiceResponse(BaseModel):
    message: str = None
    started_at: str = None
    ended_at: str = None
    current_state: str

class InterviewProcessState(BaseModel):
    session_id: str
    user_input: str
    current_step: InterviewProcessStep
    message: Optional[str] = None
    error_message: Optional[str] = None
    go_to_next_step: bool = False

class ProcessPromptResponse(BaseModel):
    message: str
    next_step: str
    go_to_next_step: bool

class InterviewProcessNode(Enum):
    ROUTER = "router"
    GREETING = "greeting"
    INTRO = "intro"
    ASK_EXPERIENCE = "ask_experience"
    ASK_PROJECT = "ask_project"
    TECHNICAL_QUESTION = "technical_question"
    BEHAVIORAL_QUESTION = "behavioral_question"
    WRAP_UP = "wrap_up"
    ERROR_HANDLER = "error_handler"

INTERVIEW_PROCESS_STEP_MAPPING = {
    InterviewProcessStep.GREETING: "Greeting",
    InterviewProcessStep.INTRO: "Intro",
    InterviewProcessStep.ASK_EXPERIENCE: "Experience",
    InterviewProcessStep.ASK_PROJECT: "Project",
    InterviewProcessStep.TECHNICAL_QUESTION: "Technical Question",
    InterviewProcessStep.BEHAVIORAL_QUESTION: "Behavioral Question",
    InterviewProcessStep.WRAP_UP: "Wrap Up",
}

def get_step_display_name(step: InterviewProcessStep) -> str:
    return INTERVIEW_PROCESS_STEP_MAPPING.get(step, "Unknown")