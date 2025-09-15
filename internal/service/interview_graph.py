from internal.adapters.log.logger import logger
from internal.domain.models.interview import InterviewNode, InterviewState, InterviewProcessStep
from langgraph.graph import StateGraph, END
from internal.domain.models.vector import VectorCollections
from internal.adapters.vector_db.factory import get_vector_store
from internal.service.process_graph import InterviewProcessingGraph
from datetime import datetime, timezone
from internal.domain.models.interview import InterviewProcessNode
from internal.adapters.llm.state_store import acquire_lock, load_state, save_state, release_lock, clear_state
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
        
        if not state.user_input or not state.user_input.strip():
            logger.info("[QUERY VECTOR DB]: Skipping vector DB query due to empty user input")
            return state.model_copy(update={
                "prompt": "No user input provided for vector search"
            })
        
        try:
            vector_resume_store = get_vector_store(collection_name=VectorCollections.RESUMES)
            results = vector_resume_store.query_by_text(text=state.user_input.strip())
            resume_text = "\n".join(
                item.document for item in results.items[:3] if item.document
            )
            
            vector_chat_history_store = get_vector_store(collection_name=VectorCollections.CHAT_HISTORY)
            results = vector_chat_history_store.query_by_text(text=state.user_input.strip())

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
        
        answer = await self.process_graph.invoke(state)
        try:
            return answer
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
        
        locked = acquire_lock(session_id)
        try:
            prev_state = load_state(session_id)

            if prev_state:
                initial_state = prev_state.model_copy(
                    update={
                        "user_input": user_input,
                        "prompt": "",
                        "message": "",
                    }
                )
            else:
                initial_state = InterviewState(
                    session_id=session_id,
                    user_input=user_input,
                    prompt="",
                    message="",
                    current_storing_node=InterviewProcessNode.GREETING,
                    start_at=datetime.now(timezone.utc).isoformat(),
                    end_at=datetime.now(timezone.utc).isoformat(),
                    go_to_next_step=False,
                    error_message=None,
                    current_step=InterviewProcessStep.GREETING,
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

            if normalized.current_step == InterviewProcessStep.ERROR_HANDLER:
                clear_state(session_id)
            else:
                save_state(session_id, normalized)
                return normalized

        except Exception as e:
            logger.exception("[InterviewGraph.invoke] exception")
            err = InterviewState(
                session_id=session_id,
                user_input=user_input,
                prompt="",
                message="",
                current_storing_node=InterviewProcessNode.GREETING,
                start_at=datetime.now(timezone.utc).isoformat(),
                end_at=datetime.now(timezone.utc).isoformat(),
                go_to_next_step=False,
                error_message=str(e),
                current_step=InterviewProcessStep.ERROR_HANDLER,
            )
            save_state(session_id, err)
            return err
        finally:
            if locked:
                release_lock(session_id)