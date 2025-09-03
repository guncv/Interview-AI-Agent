import language_tool_python
import time
from internal.infra.log.logger import logger

try:
    logger.info("[format] Initializing local LanguageTool server...")
    tool = language_tool_python.LanguageTool('en-US')
    logger.info("[format] Local LanguageTool server initialized successfully")
except Exception as e:
    logger.warning(f"[format] Failed to initialize local LanguageTool server: {e}")
    logger.info("[format] Falling back to LanguageTool Public API...")
    try:
        tool = language_tool_python.LanguageToolPublicAPI('en-US')
        logger.info("[format] LanguageTool Public API initialized successfully")
    except Exception as e2:
        logger.error(f"[format] Failed to initialize LanguageTool Public API: {e2}")
        logger.warning("[format] Using basic text correction as fallback")
        tool = None

def correct_text(text: str) -> str:
    start_time = time.time()

    try:
        if tool is not None:
            corrected = tool.correct(text)
            logger.info(f"[correct_text] LanguageTool correction completed in {time.time() - start_time:.2f} seconds")
            return corrected
        else:
            import re
            corrected = text.strip()
            corrected = re.sub(r'\s+', ' ', corrected)
            logger.info(f"[correct_text] Basic correction completed in {time.time() - start_time:.2f} seconds")
            return corrected
    except Exception as e:
        logger.error(f"[correct_text] Error during text correction: {e}")
        return text