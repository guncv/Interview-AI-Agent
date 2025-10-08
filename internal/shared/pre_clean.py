import re
from internal.adapters.log.logger import logger

def pre_clean_text(text: str) -> str:
    fillers = [
        "um", "uh", "you know", "like",
        "you see", "sort of", "kind of",
    ]

    for filler in fillers:
        pattern = rf"\b{filler}\b"
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    text = re.sub(r"\s+", " ", text)
    
    return text.strip(" .,\n!?")
