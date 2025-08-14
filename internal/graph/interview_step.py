from enum import Enum

class InterviewStep(Enum):
    ROLE_SELECTION = 1
    ASK_QUESTION = 2
    PARSE_ANSWER = 3
    GIVE_FEEDBACK = 4
    END_INTERVIEW = 5
    ERROR = -1
