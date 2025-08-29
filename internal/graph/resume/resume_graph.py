from internal.infra.log.logger import logger
from internal.graph.resume.resume_step import ResumeStep, ResumeNode
from internal.graph.resume.resume_prompt import EXTRACT_INFO_PROMPT
from langgraph.graph import StateGraph, END
from internal.infra.db.redis import redis_client
from internal.llm.state_store import clearMemory
from langchain_core.runnables import RunnableLambda
from internal.graph.resume.resume_state import ResumeState, PromptInfo
from internal.domain.models.interview import RequirementsRequest
import fitz
from io import BytesIO

class ResumeGraph:
    def __init__(self, llm):
        self.llm = llm
        self.graph = self._build_graph()
    
    def _build_graph(self):
        wf = StateGraph(ResumeState)

        wf.add_node(ResumeNode.ROUTER.value, self._router_node)
        wf.add_node(ResumeNode.PARSE_RESUME.value, self._parse_resume_node)
        wf.add_node(ResumeNode.EXTRACT_INFO.value, self._extract_info_node)
        wf.add_node(ResumeNode.TIMEOUT_RETRY.value, self._timeout_retry_node)
        wf.add_node(ResumeNode.INCOMPLETE.value, self._incomplete_node)
        wf.add_node(ResumeNode.ERROR_HANDLER.value, self._error_handler_node)

        wf.set_entry_point(ResumeNode.ROUTER.value)

        wf.add_conditional_edges(
            ResumeNode.ROUTER.value,
            self._route_from_state,
            {
                ResumeNode.PARSE_RESUME.value: ResumeNode.PARSE_RESUME.value,
                ResumeNode.EXTRACT_INFO.value: ResumeNode.EXTRACT_INFO.value,
                ResumeNode.TIMEOUT_RETRY.value: ResumeNode.EXTRACT_INFO.value,
                ResumeNode.INCOMPLETE.value: ResumeNode.INCOMPLETE.value,
                ResumeNode.ERROR_HANDLER.value: ResumeNode.ERROR_HANDLER.value,
            },
        )

        for node in [
            ResumeNode.PARSE_RESUME.value,
            ResumeNode.EXTRACT_INFO.value,
            ResumeNode.TIMEOUT_RETRY.value,
            ResumeNode.INCOMPLETE.value,
            ResumeNode.ERROR_HANDLER.value,
        ]:
            wf.add_conditional_edges(
                node,
                self._after_node_continue_or_pause,
                {
                    "continue": ResumeNode.ROUTER.value,
                    "pause": END,
                },
            )

        wf.add_edge(ResumeNode.INCOMPLETE.value, END)
        wf.add_edge(ResumeNode.ERROR_HANDLER.value, END)
        wf.add_edge(ResumeNode.TIMEOUT_RETRY.value, END)
        return wf.compile()

    def _router_node(self, state: ResumeState) -> ResumeState:
        return state

    def _route_from_state(self, state: ResumeState) -> str:
        step_to_node = {
            ResumeStep.PARSE_RESUME: ResumeNode.PARSE_RESUME.value,
            ResumeStep.EXTRACT_INFO: ResumeNode.EXTRACT_INFO.value,
            ResumeStep.TIMEOUT_RETRY: ResumeNode.TIMEOUT_RETRY.value,
            ResumeStep.INCOMPLETE: ResumeNode.INCOMPLETE.value,
            ResumeStep.ERROR: ResumeNode.ERROR_HANDLER.value,
        }
        return step_to_node.get(state.current_step, ResumeNode.ERROR_HANDLER.value)

    def _parse_resume_node(self, state: ResumeState) -> ResumeState:
        try:
            text = ""
            file_input = BytesIO(state.file_input)
            if file_input:
                with fitz.open(stream=file_input, filetype="pdf") as pdf:
                    for page in pdf:
                        text += page.get_text()

            logger.info(f"[PARSE_RESUME] Extracted {len(text)} characters from resume")
            
            return state.model_copy(update={
                "resume_text": text.strip(),
                "current_step": ResumeStep.EXTRACT_INFO,
            })

        except Exception as e:
            logger.error(f"[PARSE_RESUME] Error parsing PDF: {e}")
            return state.model_copy(update={
                "current_step": ResumeStep.ERROR,
                "error_message": f"Failed to parse PDF: {str(e)}"
            })

    def _extract_info_node(self, state: ResumeState) -> ResumeState:
        try:
            prompt_info = self._invoke_node(EXTRACT_INFO_PROMPT, PromptInfo, state.session_id, state.resume_text)
                
            return state.model_copy(update={
                "current_step": ResumeStep.INCOMPLETE,
                "should_pause": False,
                "prompt_info": prompt_info,
                "resume_text": state.resume_text,
            })
                
        except Exception as e:
            logger.error(f"[EXTRACT_INFO] Error in extract_info_node: {e}")
            return state.model_copy(update={
                "current_step": ResumeStep.ERROR,
                "error_message": f"Failed to extract info: {str(e)}",
                "should_pause": True,
            })

    def _timeout_retry_node(self, state: ResumeState) -> ResumeState:
        logger.info(f"[TIMEOUT_RETRY] Handling timeout for session {state.session_id}")
        
        return state.model_copy(update={
            "current_step": ResumeStep.EXTRACT_INFO,
            "should_pause": False,
        })

    def _incomplete_node(self, state: ResumeState) -> ResumeState:
        logger.info(f"[INCOMPLETE] Processing incomplete for session {state.session_id}")
        
        if state.prompt_info:
            logger.info(f"[INCOMPLETE] Resume processing completed successfully")
            return state.model_copy(update={
                "current_step": ResumeStep.INCOMPLETE,
                "should_pause": True,
            })
        else:
            logger.warning(f"[INCOMPLETE] No parsed info found, moving to error")
            return state.model_copy(update={
                "current_step": ResumeStep.ERROR,
                "error_message": "Processing incomplete - no parsed information available",
                "should_pause": True,
            })

    def _error_handler_node(self, state: ResumeState) -> ResumeState:
        logger.error(f"[ERROR_HANDLER] Handling error for session {state.session_id}: {state.error_message}")
        return state.model_copy(update={
            "current_step": ResumeStep.ERROR,
            "should_pause": True,
        })
    
    def _after_node_continue_or_pause(self, state: ResumeState) -> str:
        return "pause" if state.should_pause else "continue"

    def _invoke_node(self, prompt, schema, session_id: str, resume_text: str):
        prompt_info = prompt | self.llm.with_structured_output(schema)
        
        def to_both(x):
            d = x.model_dump() if hasattr(x, "model_dump") else x
            msg = d.get("message")
            if not isinstance(msg, str):
                import json
                msg = json.dumps(d, ensure_ascii=False)
            return {"raw": d, "output": msg}

        runnable_both = prompt_info | RunnableLambda(to_both)

        data = runnable_both.invoke(
            {"resume_text": resume_text},
            config={"configurable": {"session_id": session_id}},
        )
        
        return schema(**data["raw"])

    def invoke(self, request: RequirementsRequest) -> ResumeState:
        locked = redis_client.acquire_lock(request.session_id)
        try:
            prev_state = redis_client.load_resume_state(request.session_id)

            if prev_state:
                initial_state = prev_state.model_copy(update={
                    "file_input": request.resume_file,
                    "job_requirements": request.job_requirements,
                    "position": request.position,
                    "company": request.company,
                    "work_type": request.work_type,
                    "interview_type": request.interview_type,
                })
            else:
                initial_state = ResumeState(
                    session_id=request.session_id,
                    file_input=request.resume_file,
                    job_requirements=request.job_requirements,
                    position=request.position,
                    company=request.company,
                    work_type=request.work_type,
                    interview_type=request.interview_type,
                    language=request.language,
                    current_step=ResumeStep.PARSE_RESUME,
                )

            logger.info(f"[INVOKE] Starting resume processing for session {request.session_id}")
            logger.info(f"[INVOKE] Job: {request.position} at {request.company}")

            result = self.graph.invoke(
                initial_state,
                config={"configurable": {
                    "session_id": request.session_id,
                    "thread_id": request.session_id,
                }}
            )
            
            normalized = ResumeState(**result) if isinstance(result, dict) else result
            logger.info(f"[INVOKE] Processing completed with step: {normalized.current_step}")

            redis_client.save_resume_state(request.session_id, normalized)

            if normalized.current_step in (
                ResumeStep.INCOMPLETE,
                ResumeStep.ERROR,
            ):
                redis_client.clear_state(request.session_id)
                clearMemory(request.session_id)

            return normalized

        except Exception as e:
            logger.exception("[ResumeGraph.invoke] exception")
            err = ResumeState(
                session_id=request.session_id,
                file_input=request.resume_file,
                current_step=ResumeStep.ERROR,
                match_score=0,
                error_message=str(e),
            )
            redis_client.save_resume_state(request.session_id, err)
            return err
        finally:
            if locked:
                redis_client.release_lock(request.session_id)
