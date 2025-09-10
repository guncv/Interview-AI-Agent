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
    overall_score: int
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
    
class InterviewState(BaseModel):
    session_id: str
    user_input: str
    prompt: str
    message: Optional[str] = None
    error_message: Optional[str] = None

class InterviewServiceResponse(BaseModel):
    message: str = None
    started_at: str = None
    ended_at: str = None

class InterviewProcessStep(Enum):
    ROUTER = 1
    INTRO = 2
    ASK_EXPERIENCE = 3
    ASK_PROJECT = 4
    TECHNICAL_QUESTION = 5
    BEHAVIORAL_QUESTION = 6
    CANDIDATE_QUESTIONS = 7
    WRAP_UP = 8
    ERROR_HANDLER = 9

class InterviewProcessState(BaseModel):
    session_id: str
    user_input: str
    current_step: InterviewProcessStep
    message: Optional[str] = None
    context: Optional[str] = None
    error_message: Optional[str] = None

class IntroResponse(BaseModel):
    message: str
    next_step: str

class InterviewProcessNode(Enum):
    ROUTER = "router"
    INTRO = "intro"
    ASK_EXPERIENCE = "ask_experience"
    ASK_PROJECT = "ask_project"
    TECHNICAL_QUESTION = "technical_question"
    BEHAVIORAL_QUESTION = "behavioral_question"
    CANDIDATE_QUESTIONS = "candidate_questions"
    WRAP_UP = "wrap_up"
    ERROR_HANDLER = "error_handler"