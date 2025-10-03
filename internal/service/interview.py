from internal.domain.models.interview import HealthCheckResponse, InterviewRequest, RequirementsRequest, RequirementsResponse
from internal.shared.exception import InterviewSimulationException
from internal.domain.exception import InterviewSimulationErrorCodes
from internal.adapters.log.logger import logger
from internal.service.interview_graph import InterviewGraph
from internal.adapters.db.redis import redis_client
from internal.adapters.vector_db.ingestion_loader import ingest_document
from internal.domain.models.vector import VectorCollections
from internal.adapters.vector_db.factory import get_vector_store
from internal.service.prompts.bias_prompt import BIAS_PROMPT
from internal.adapters.llm.loader import loadLLM, getLLMModel
from langchain_core.runnables import Runnable
from langchain_core.output_parsers import StrOutputParser

class InterviewService:
    def __init__(self):
        self.interview_graph = InterviewGraph()
        self.redis_client = redis_client
        self.llm = loadLLM("interview")
        self.llm_model = getLLMModel()
        self.parser = StrOutputParser()
        self.bias_prompt = BIAS_PROMPT
        self.bias_prompt_chain: Runnable = self.bias_prompt | self.llm | self.parser

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
            metadata = {
                "user_id": request.user_id,
                "resume_id": request.resume_id,
                "session_id": request.session_id,
            }
            ingest_document(VectorCollections.RESUMES, request.resume_file, request.session_id, metadata)
            
            vector_store = get_vector_store(collection_name=VectorCollections.RESUMES)
            results = vector_store.query_by_text(
                text="summary of education, work experience, skills, projects",
                k=100,
                session_id=request.session_id
            )
            
            resume_text = "\n".join(
                item.document for item in results.items if item.document
            )
            
            if not resume_text.strip():
                logger.warning(f"[Requirements Service]: No resume text found for session {request.session_id}")
                return RequirementsResponse(bias_prompt="")
            
            response = await self.bias_prompt_chain.ainvoke({"resume_text": resume_text})
            bias_terms = response.strip()
            
            resp = RequirementsResponse(
                bias_prompt=bias_terms,
                resume_context=resume_text
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
