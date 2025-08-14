from enum import Enum

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