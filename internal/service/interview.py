from internal.domain.models.interview import HealthCheckResponse, InterviewRequest, RequirementsRequest, RequirementsResponse, ResumeStructured
from internal.shared.exception import InterviewSimulationException
from internal.domain.exception import InterviewSimulationErrorCodes
from internal.adapters.log.logger import logger
from internal.service.interview_graph import InterviewGraph
from internal.adapters.db.redis import redis_client
from internal.service.prompts.bias_prompt import BIAS_PROMPT
from internal.service.prompts.resume_extraction_prompt import RESUME_EXTRACTION_PROMPT
from internal.adapters.llm.loader import loadLLM, getLLMModel
from langchain_core.runnables import Runnable
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_community.document_loaders import PyMuPDFLoader
import json
import tempfile
import asyncio

class InterviewService:
    def __init__(self):
        self.interview_graph = InterviewGraph()
        self.redis_client = redis_client
        self.llm = loadLLM("interview")
        self.llm_model = getLLMModel()
        self.parser = StrOutputParser()
        self.json_parser = JsonOutputParser()
        self.bias_prompt = BIAS_PROMPT
        self.bias_prompt_chain: Runnable = self.bias_prompt | self.llm | self.parser
        self.resume_extraction_prompt = RESUME_EXTRACTION_PROMPT
        self.resume_extraction_chain: Runnable = self.resume_extraction_prompt | self.llm | self.parser

    async def health_check(self):
        logger.info("[Health Check Service Called: ]")
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
        logger.info(f"[Interview Service Called:]")
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
    
    async def requirements(self, request: RequirementsRequest) -> RequirementsResponse:
        logger.info(f"[Requirements Service Called:]")
        
        try:
            with tempfile.NamedTemporaryFile(delete=True, suffix=".pdf") as tmp_file:
                tmp_file.write(request.resume_file)
                tmp_file.flush()
                
                loader = PyMuPDFLoader(file_path=tmp_file.name)
                documents = loader.load()
            
            resume_text = "\n".join([doc.page_content for doc in documents])
            
            if not resume_text.strip():
                logger.warning(f"[Requirements Service]: No resume text found for session {request.session_id}")
                return RequirementsResponse(bias_prompt="", resume_context="")
            
            logger.info(f"[Requirements Service]: Extracted {len(resume_text)} characters from PDF")
            
            bias_response, resume_json_response = await asyncio.gather(
                self.bias_prompt_chain.ainvoke({"resume_text": resume_text}),
                self.resume_extraction_chain.ainvoke({"resume_text": resume_text})
            )
            
            bias_terms = bias_response.strip()
            
            try:
                resume_json = json.loads(resume_json_response)
                
            except json.JSONDecodeError as e:
                logger.error(f"[Requirements Service]: Failed to parse resume JSON: {e}")
                if "```json" in resume_json_response:
                    start = resume_json_response.find("```json") + 7
                    end = resume_json_response.find("```", start)
                    resume_json_response = resume_json_response[start:end].strip()
                    resume_json = json.loads(resume_json_response)
                elif "```" in resume_json_response:
                    start = resume_json_response.find("```") + 3
                    end = resume_json_response.find("```", start)
                    resume_json_response = resume_json_response[start:end].strip()
                    resume_json = json.loads(resume_json_response)
                else:
                    raise
            
            redis_client.save_resume_context(request.session_id, resume_json)
            logger.info(f"[Requirements Service]: Successfully extracted and stored structured resume data in Redis ", resume_json)
            
            resp = RequirementsResponse(
                bias_prompt=bias_terms,
                resume_context=json.dumps(resume_json, ensure_ascii=False),
            )
            return resp

        except (InterviewSimulationException, Exception) as e:
            if not isinstance(e, InterviewSimulationException):
                e = InterviewSimulationException(
                    error_code=InterviewSimulationErrorCodes.INTERNAL_ERROR,
                    description=f"[{type(e).__name__}]: {str(e)}"
                )
            logger.error(f"[Requirements Service Error]: {e}")
            e.raise_HTTPException()
