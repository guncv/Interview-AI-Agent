from difflib import SequenceMatcher
from internal.infra.log.logger import logger

def remove_fuzzy_overlap(prev: str, full: str) -> str:
    logger.info(f"[remove_fuzzy_overlap] Called: prev: {prev}, full: {full}")
    matcher = SequenceMatcher(None, prev, full)
    match = matcher.find_longest_match(0, len(prev), 0, len(full))
    logger.info(f"[remove_fuzzy_overlap] Match: {match}")
    if match.size == 0:
        logger.info(f"[remove_fuzzy_overlap] No match found, returning full")
        return full

    logger.info(f"[remove_fuzzy_overlap] Returning: {full[match.b + match.size:]}")
    return full[match.b + match.size:]
