from pydantic import BaseModel
from internal.graph.resume.resume_state import PromptInfo

class HealthCheckResponse(BaseModel):
    message: str

class InterviewRequest(BaseModel):
    session_id: str
    user_input: str
    
class InterviewResponse(BaseModel):
    message: str
    
class RequirementsRequest(BaseModel):
    session_id: str
    resume_file: bytes
    position: str
    company: str
    work_type: str
    job_requirements: str
    interview_type: str
    language: str
    
class RequirementsResponse(BaseModel):
    parsed_json: PromptInfo