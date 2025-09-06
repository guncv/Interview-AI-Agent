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
    
class QueryVectorDBRes(BaseModel):
    message: str
    
class InterviewState(BaseModel):
    session_id: str
    user_input: str
    prompt: str
    message: Optional[str] = None
    error_message: Optional[str] = None
