from difflib import SequenceMatcher
from internal.infra.log.logger import logger
from internal.domain.models.speech_recognize import SpeechRecognize
from typing import Tuple
from internal.infra.db.redis import redis_client

def merge_and_split_transcripts(
    prev_recognize: SpeechRecognize,
    merged_recognize: SpeechRecognize,
    fuzzy_threshold: float = 0.7,
    session_id: str = None
) -> Tuple[SpeechRecognize, SpeechRecognize]:
    improved_words = []
    i = 0
    if session_id:
        bias_prompt = redis_client.get_session_bias_prompt(session_id)
    else:
        bias_prompt = None
    merged_words = merged_recognize.words

    best_idx = 0
    for pw in prev_recognize.words:
        if i >= len(merged_words):
            break

        best_match = None
        best_ratio = 0.0
        for j in range(i, len(merged_words)):
            mw = merged_words[j]
            if mw.word and pw.word:
                ratio = SequenceMatcher(None, pw.word.lower(), mw.word.lower()).ratio()
            else:
                ratio = 0.0
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = mw
                best_idx = j

        if best_match and best_ratio > fuzzy_threshold:
            improved_words.append(best_match if (best_match.confidence and pw.confidence and best_match.confidence > pw.confidence) else pw)
            i = best_idx + 1
        elif best_match and best_match.confidence and pw.confidence and best_match.confidence > pw.confidence:
            improved_words.append(best_match)
            i = best_idx + 1
        elif bias_prompt and best_match and best_match.word and best_match.word.lower() in [bp.lower() for bp in bias_prompt]:
            improved_words.append(best_match)
            i = best_idx + 1
        else:
            improved_words.append(pw)

    improved_transcript = " ".join([w.word for w in improved_words if w.word])
    improved_prev = SpeechRecognize(transcript=improved_transcript, words=improved_words)

    curr_words = merged_words[best_idx + 1:]
    curr_transcript = " ".join([w.word for w in curr_words if w.word])
    curr_only = SpeechRecognize(transcript=curr_transcript, words=curr_words)

    return improved_prev, curr_only
