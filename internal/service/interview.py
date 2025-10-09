from typing import Dict, Any
from internal.domain.models.interview import HealthCheckResponse, InterviewRequest, ProcessResumeTextResponse, RequirementsRequest, RequirementsResponse, ResumeStructured
from internal.shared.exception import InterviewSimulationException
from internal.domain.exception import InterviewSimulationErrorCodes
from internal.adapters.log.logger import logger
from internal.service.interview_graph import InterviewGraph
from internal.adapters.db.redis import redis_client
from internal.adapters.db.postgres import postgres_client
from internal.service.prompts.bias_prompt import BIAS_PROMPT
from internal.service.prompts.resume_extraction_prompt import RESUME_EXTRACTION_PROMPT
from internal.adapters.llm.loader import loadLLM, getLLMModel
from langchain_core.runnables import Runnable
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_community.document_loaders import PyMuPDFLoader
import json
import tempfile
import asyncio
from internal.domain.enum import QueueName
from internal.domain.models.interview import InterviewTaskType
from internal.adapters.queue.publisher import TaskPublisher
from internal.domain.models.redis import RedisKeys

class InterviewService:
    def __init__(self):
        self.interview_graph = InterviewGraph()
        self.redis_client = redis_client
        self.db_client = postgres_client
        self.llm = loadLLM("interview")
        self.llm_model = getLLMModel()
        self.parser = StrOutputParser()
        self.json_parser = JsonOutputParser()
        self.bias_prompt = BIAS_PROMPT
        self.bias_prompt_chain: Runnable = self.bias_prompt | self.llm | self.parser
        self.resume_extraction_prompt = RESUME_EXTRACTION_PROMPT
        self.resume_extraction_chain: Runnable = self.resume_extraction_prompt | self.llm | self.parser
        self.task_publisher = TaskPublisher()
        
    async def health_check(self):
        try:
            resp = HealthCheckResponse(message="OK")
            return resp
        except (InterviewSimulationException, Exception) as e:
            if type(e) != InterviewSimulationException:
                e = InterviewSimulationException(
                    error_code=InterviewSimulationErrorCodes.INTERNAL_ERROR,
                    description=f"[{type(e).__name__}]: {str(e)}")
            logger.error(f"[Health Check Service Error]: {e}")
            e.raise_HTTPException()

    async def interview(self, request: InterviewRequest):
        try:
            resp = self.interview_graph.invoke(request.session_id, request.user_input)
            redis_client.save_interview_state(request.session_id, resp)

            return resp
        
        except (InterviewSimulationException, Exception) as e:
            if type(e) != InterviewSimulationException:
                e = InterviewSimulationException(
                    error_code=InterviewSimulationErrorCodes.INTERNAL_ERROR,
                    description=f"[{type(e).__name__}]: {str(e)}")
            logger.error(f"[Interview Service Error]: {e}")
            e.raise_HTTPException()
            

    async def generate_bias_prompt_and_context(self, payload: dict) -> None:
        try:
            session_id = payload.get("session_id")
            resume_text = payload.get("resume_text")
            
            if not session_id:
                logger.error("[Generate Bias Prompt and Context]: Missing session_id in payload")
                return
            
            if not resume_text:
                logger.error(f"[Generate Bias Prompt and Context]: Missing resume_text for session {session_id}")
                return
            
            result = await self.process_resume_text(session_id, resume_text)
            bias_terms = result.bias_terms
            resume_json = result.resume_json
            
            await redis_client.save_resume_context(session_id, resume_json, RedisKeys.RESUME_CONTEXT_TTL_SECONDS.value)
            await redis_client.save_interview_bias_prompt(session_id, bias_terms, RedisKeys.BIAS_PROMPT_TTL_SECONDS.value)
            await postgres_client.update_session_bias_and_context(
                session_id=session_id,
                bias_prompt=bias_terms,
                resume_context=resume_json
            )
            
            
        except Exception as e:
            logger.error(f"[Generate Bias Prompt and Context]: Error processing resume: {e}")
            raise
    
    async def process_resume_text(self, session_id: str, resume_text: str) -> ProcessResumeTextResponse:
        if not resume_text.strip():
            logger.warning(f"[Process Resume]: No resume text found for session {session_id}")
            return ProcessResumeTextResponse(bias_terms="", resume_json={})
        
        bias_response, resume_json_response = await asyncio.gather(
            self.bias_prompt_chain.ainvoke({"resume_text": resume_text}),
            self.resume_extraction_chain.ainvoke({"resume_text": resume_text})
        )
        
        bias_terms = bias_response.strip()
        
        try:
            resume_json = json.loads(resume_json_response) if isinstance(resume_json_response, str) else resume_json_response
        except Exception as e:
            logger.error(f"[Process Resume]: Failed to parse resume JSON: {e}")
            resume_json = {}

        resp = ProcessResumeTextResponse(
            bias_terms=bias_terms,
            resume_json=resume_json
        )
        return resp
    
    async def requirements(self, request: RequirementsRequest) -> None:
        
        try:
            with tempfile.NamedTemporaryFile(delete=True, suffix=".pdf") as tmp_file:
                tmp_file.write(request.resume_file)
                tmp_file.flush()
                
                loader = PyMuPDFLoader(file_path=tmp_file.name)
                documents = loader.load()
            
            resume_text = "\n".join([doc.page_content for doc in documents])
            await self.task_publisher.publish(QueueName.AI_AGENT, InterviewTaskType.EXTRACT_BIAS_PROMPT_AND_RESUME_CONTEXT, {
                "session_id": request.session_id,
                "resume_text": resume_text
            })

        except (InterviewSimulationException, Exception) as e:
            if not isinstance(e, InterviewSimulationException):
                e = InterviewSimulationException(
                    error_code=InterviewSimulationErrorCodes.INTERNAL_ERROR,
                    description=f"[{type(e).__name__}]: {str(e)}"
                )
            logger.error(f"[Requirements Service Error]: {e}")
            e.raise_HTTPException()