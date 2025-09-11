from internal.adapters.log.logger import logger
from internal.domain.models.interview import InterviewNode, InterviewState, InterviewProcessState, InterviewProcessStep
from langgraph.graph import StateGraph, END
from internal.domain.models.vector import VectorCollections
from internal.adapters.vector_db.factory import get_vector_store
from internal.shared.exception import InterviewSimulationException, InterviewSimulationErrorCodes
from internal.service.process_graph import InterviewProcessingGraph

class InterviewGraph:
    def __init__(self):
        self.graph = self._build_graph()
        self.process_graph = InterviewProcessingGraph()

    def _ok_or_error(self, state: InterviewState) -> str:
        return "error" if state.error_message else "ok"

    def _build_graph(self):
        wf = StateGraph(InterviewState)

        wf.add_node(InterviewNode.QUERY_VECTOR_DB.value, self._query_vector_db_node)
        wf.add_node(InterviewNode.PROCESS_ANSWER.value, self._process_answer_node)
        wf.add_node(InterviewNode.STORE_ANSWER.value, self._store_answer_node)

        wf.set_entry_point(InterviewNode.QUERY_VECTOR_DB.value)

        wf.add_conditional_edges(InterviewNode.QUERY_VECTOR_DB.value, self._ok_or_error, {
            "ok": InterviewNode.PROCESS_ANSWER.value,
            "error": END,
        })

        wf.add_conditional_edges(InterviewNode.PROCESS_ANSWER.value, self._ok_or_error, {
            "ok": InterviewNode.STORE_ANSWER.value,
            "error": END,
        })

        wf.add_conditional_edges(InterviewNode.STORE_ANSWER.value, self._ok_or_error, {
            "ok": END,
            "error": END,
        })

        return wf.compile()

    def _query_vector_db_node(self, state: InterviewState) -> InterviewState:
        logger.info(f"[QUERY VECTOR DB]: input={state.user_input}")
        
        try:
            vector_resume_store = get_vector_store(collection_name=VectorCollections.RESUMES)
            results = vector_resume_store.query_by_text(text=state.user_input)
            resume_text = "\n".join(
                item.document for item in results.items[:3] if item.document
            )
            
            vector_chat_history_store = get_vector_store(collection_name=VectorCollections.CHAT_HISTORY)
            results = vector_chat_history_store.query_by_text(text=state.user_input)

            chat_text = "\n".join(
                item.document for item in results.items[:3] if item.document
            )

            context = f"Resume Info:\n{resume_text}\n\nChat History:\n{chat_text}"
            logger.info(f"[QUERY VECTOR DB] context = {context}")
            if context:
                prompt = context
            else:
                prompt = ""
            return state.model_copy(update={
                "prompt": prompt,
            })
            
        except Exception as e:
            logger.exception("[QUERY VECTOR DB] error")
            return state.model_copy(update={
                "error_message": str(e),
            })

    async def _process_answer_node(self, state: InterviewState) -> InterviewState:
        logger.info(f"[PROCESS ANSWER]: state={state}")
        
        answer = await self.process_graph.invoke(
            state.session_id,
            state.user_input,
            )
        try:
            return state.model_copy(update={
                "message": answer.interview_process_messages or [],
                "current_step": answer.current_step,
            })
        except Exception as e:
            logger.exception("[PROCESS ANSWER] error")
            return state.model_copy(update={
                "error_message": str(e),
            })

    async def _store_answer_node(self, state: InterviewState) -> InterviewState:
        logger.info(f"[STORE ANSWER]: state={state}")

        try:
            return state
        except Exception as e:
            logger.exception("[STORE ANSWER] error")
            return state.model_copy(update={
                "error_message": str(e),
            })

    async def invoke(self, session_id: str, user_input: str) -> InterviewState:
        logger.info(f"[InterviewGraph.invoke]: session_id={session_id}, user_input={user_input}")
        try:
            initial_state = InterviewState(
                session_id=session_id,
                user_input=user_input,
                prompt="",
                message=[],
                error_message=None,
                current_step=InterviewProcessStep.GREETING
            )

            result = await self.graph.ainvoke(
                initial_state,
                config={"configurable": {
                    "session_id": session_id,
                    "thread_id": session_id,
                }}
            )

            normalized = InterviewState(**result) if isinstance(result, dict) else result

            logger.info(f"[InterviewGraph.invoke]: message={normalized.message}")

            if normalized.error_message:
                logger.error(f"[InterviewGraph.invoke] error: {normalized.error_message}")
                raise InterviewSimulationException(
                    error_code=InterviewSimulationErrorCodes.INTERNAL_ERROR,
                    description=f"[GRAPH_ERROR]: {normalized.error_message}"
                )
            
            return normalized

        except Exception as e:
            logger.exception("[InterviewGraph.invoke] error")
            raise InterviewSimulationException(
                error_code=InterviewSimulationErrorCodes.INTERNAL_ERROR,
                description=f"[{type(e).__name__}]: {str(e)}"
            )
