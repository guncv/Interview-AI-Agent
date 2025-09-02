from typing import Optional, Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from internal.infra.log.logger import logger
from internal.llm.loader import loadLLM
from internal.config.config import nested_config as config
import time


class TranscriptCorrector:

    def __init__(self):
        self.type = "transcribe"
        self.model = config[self.type]["model"]
        self.provider = config[self.type]["api_provider"]
        self.temperature = config[self.type]["temperature"]
        
        self.base_template = """
        You are an expert transcript corrector that improves speech-to-text accuracy.

        CORE TASK: Correct grammar, fix transcription errors, and enhance clarity while preserving the original meaning and intent.

        RULES:
        - Fix common speech-to-text errors (homophones, misspellings)
        - Improve sentence structure and grammar
        - Maintain original speaker's voice and intent
        - Keep technical terms and proper nouns intact
        - Remove filler words only if they don't affect meaning
        - Preserve question marks and exclamation points appropriately
        - Don't upcase the first letter of the transcript except for there is upper case in the original transcript        
        - Don't return " in the transcript

        {bias_instructions}

        Original transcript: "{transcript}"

        Provide only the corrected transcript without any additional commentary:
        """

        self.prompt = ChatPromptTemplate.from_template(self.base_template)
        self.chain = self._build_chain()

    def _build_chain(self):
        return (
            RunnablePassthrough.assign(
                bias_instructions=lambda x: x.get("bias_instructions", "")
            )
            | self.prompt
            | loadLLM(type=self.type)
            | StrOutputParser()
        )

    def correct_transcript(
        self,
        raw_text: str,
        bias_prompt: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        if not raw_text or not isinstance(raw_text, str):
            raise ValueError("Raw text must be a non-empty string")

        try:
            bias_instructions = ""
            if bias_prompt:
                bias_instructions = f"""
                ADDITIONAL BIAS INSTRUCTIONS:
                {bias_prompt}

                Apply these bias instructions while maintaining natural language flow.
                """

            chain_input = {
                "transcript": raw_text.strip(),
                "bias_instructions": bias_instructions
            }

            if context:
                chain_input.update(context)

            if bias_prompt:
                logger.debug(f"[correct_transcript] Using bias prompt: {bias_prompt[:100]}...")

            _start_time = time.time()
            result = self.chain.invoke(chain_input)

            corrected = result.strip()
            _end_time = time.time()
            logger.info(f"[correct_transcript] Time taken: {_end_time - _start_time} seconds")
            return corrected

        except Exception as e:
            logger.error(f"[correct_transcript] Error processing transcript: {str(e)}")
            raise Exception(f"Failed to correct transcript: {str(e)}")


_corrector = TranscriptCorrector()

def correct_transcript(
    raw_text: str,
    bias_prompt: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> str:
    logger.info(f"[correct_transcript] Before correction: {raw_text}")
    result = _corrector.correct_transcript(raw_text, bias_prompt, context)
    logger.info(f"[correct_transcript] Result: {result}")
    return result