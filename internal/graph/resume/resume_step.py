from enum import Enum

class ResumeStep(Enum):
    PARSE_RESUME = 2
    EXTRACT_INFO = 3
    ASK_JOB_DETAIL = 4
    ENRICH_CONTEXT = 5
    ERROR = -1
    
class ResumeNode(Enum):
    ROUTER = "router"
    PARSE_RESUME = "parse_resume"
    EXTRACT_INFO = "extract_info"
    ASK_JOB_DETAIL = "ask_job_detail"
    ENRICH_CONTEXT = "enrich_context"
    ERROR_HANDLER = "error_handler"