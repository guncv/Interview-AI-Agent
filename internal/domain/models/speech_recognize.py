from dataclasses import dataclass
from typing import List

@dataclass
class Word:
    word: str
    start: float
    end: float
    confidence: float
    
@dataclass
class SpeechRecognize:
    transcript: str
    words: List[Word]

