from enum import Enum

class ResumeStep(Enum):
    PARSE_RESUME = 2
    EXTRACT_INFO = 3
    ERROR = -1
    TIMEOUT_RETRY = -2
    INCOMPLETE = -3
    
class ResumeNode(Enum):
    ROUTER = "router"
    PARSE_RESUME = "parse_resume"
    EXTRACT_INFO = "extract_info"
    TIMEOUT_RETRY = "timeout_retry"
    INCOMPLETE = "incomplete"
    ERROR_HANDLER = "error_handler"