import string
from pydantic import BaseModel
from typing import List, Optional
from enum import Enum
from typing import List, Optional

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
    
class RequirementsResponse(BaseModel):
    bias_prompt: str
    
class GetOverallSummaryRequest(BaseModel):
    summary_md: List[str]
    
class GetOverallSummaryResponse(BaseModel):
    overall_summary_md: str

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
    improvement_sentence: str
    llm_model: str
    
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
    
class InterviewProcessNode(Enum):
    ROUTER = "Router"
    GREETING = "Greeting"
    INTRO = "Intro"
    ASK_EXPERIENCE = "Experience"
    ASK_PROJECT = "Project"
    TECHNICAL_QUESTION = "Technical Question"
    BEHAVIORAL_QUESTION = "Behavioral Question"
    WRAP_UP = "Wrap Up"
    ERROR_HANDLER = "Unknown"

class InterviewState(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    
    session_id: str
    user_input: str
    context_prompt: str
    message: str
    current_storing_node: InterviewProcessNode
    start_at: str
    end_at: str
    go_to_next_step: bool = False
    error_message: Optional[str] = None
    current_step: InterviewProcessStep
    
class ProcessPromptResponse(BaseModel):
    message: str
    next_step: str
    go_to_next_step: bool
    
class PreProcessedCriteria(BaseModel):
	criteria_id:       str
	criteria_name:     str
	criteria_avg_score: float
	criteria_comment:  List[str]

class PreProcessedCriteriaResp(BaseModel):
	criteria: List[PreProcessedCriteria]

class PostProcessedCriteria(BaseModel):
	criteria_id:       str
	criteria_name:     str
	criteria_avg_score: float
	criteria_comment:  str

class PostProcessedCriteriaResp(BaseModel):
	criteria: List[PostProcessedCriteria]



