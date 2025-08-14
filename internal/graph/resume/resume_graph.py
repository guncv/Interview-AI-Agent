from internal.infra.log.logger import logger
from internal.graph.resume.resume_step import ResumeStep, ResumeNode
from internal.llm.prompt_builder import ASK_QUESTION_PROMPT
from langgraph.graph import StateGraph, END
from internal.llm.loader import getChatHistory
from langchain_core.runnables import RunnableWithMessageHistory
from internal.infra.db.redis import save_state, load_state, clear_state, acquire_lock, release_lock
from internal.llm.state_store import clearMemory
from langchain_core.runnables import RunnableLambda
from internal.graph.resume.resume_state import ResumeState
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
        wf.add_node(ResumeNode.ASK_JOB_DETAIL.value, self._ask_job_detail_node)
        wf.add_node(ResumeNode.ENRICH_CONTEXT.value, self._enrich_context_node)
        wf.add_node(ResumeNode.ERROR_HANDLER.value, self._error_handler_node)

        wf.set_entry_point(ResumeNode.ROUTER.value)

        wf.add_conditional_edges(
            ResumeNode.ROUTER.value,
            self._route_from_state,
            {
                ResumeNode.PARSE_RESUME.value: ResumeNode.PARSE_RESUME.value,
                ResumeNode.EXTRACT_INFO.value: ResumeNode.EXTRACT_INFO.value,
                ResumeNode.ASK_JOB_DETAIL.value: ResumeNode.ASK_JOB_DETAIL.value,
                ResumeNode.ENRICH_CONTEXT.value: ResumeNode.ENRICH_CONTEXT.value,
                ResumeNode.ERROR_HANDLER.value: ResumeNode.ERROR_HANDLER.value,
            },
        )

        for node in [
            ResumeNode.PARSE_RESUME.value,
            ResumeNode.EXTRACT_INFO.value,
            ResumeNode.ASK_JOB_DETAIL.value,
            ResumeNode.ENRICH_CONTEXT.value,
        ]:
            wf.add_conditional_edges(
                node,
                self._after_node_continue_or_pause,
                {
                    "continue": ResumeNode.ROUTER.value,
                    "pause": END,
                },
            )

        wf.add_edge(ResumeNode.ERROR_HANDLER.value, END)
        return wf.compile()

    def _router_node(self, state: ResumeState) -> ResumeState:
        return state

    def _route_from_state(self, state: ResumeState) -> str:
        step_to_node = {
            ResumeStep.PARSE_RESUME: ResumeNode.PARSE_RESUME.value,
            ResumeStep.EXTRACT_INFO: ResumeNode.EXTRACT_INFO.value,
            ResumeStep.ASK_JOB_DETAIL: ResumeNode.ASK_JOB_DETAIL.value,
            ResumeStep.ENRICH_CONTEXT: ResumeNode.ENRICH_CONTEXT.value,
            ResumeStep.ERROR: ResumeNode.ERROR_HANDLER.value,
        }
        return step_to_node.get(state.current_step, ResumeNode.ERROR_HANDLER.value)

    def _parse_resume_node(self, state: ResumeState) -> ResumeState:
        return state.model_copy(update={
            "current_step": ResumeStep.PARSE_RESUME,
        })

    def _extract_info_node(self, state: ResumeState) -> ResumeState:
        return state.model_copy(update={
            "message": state.message or "",
            "current_step": ResumeStep.EXTRACT_INFO,
            "should_pause": False,
        })

    def _ask_job_detail_node(self, state: ResumeState) -> ResumeState:
        return state.model_copy(update={
            "message": state.message or "",
            "current_step": ResumeStep.ASK_JOB_DETAIL,
            "should_pause": False,
        })

    def _enrich_context_node(self, state: ResumeState) -> ResumeState:
        return state.model_copy(update={
            "message": state.message or "",
            "current_step": ResumeStep.ENRICH_CONTEXT,
            "should_pause": False,
        })

    def _error_handler_node(self, state: ResumeState) -> ResumeState:
        logger.error(f"[ERROR_HANDLER]: {state.error_message}")
        return state.model_copy(update={
            "message": "ขออภัยครับ เกิดข้อผิดพลาดในการประมวลผล กรุณาลองใหม่อีกครั้ง",
            "match_score": 0,
            "current_step": ResumeStep.ERROR,
        })
    
    def _after_node_continue_or_pause(self, state: ResumeState) -> str:
        return "pause" if state.should_pause else "continue"

    def _invoke_node(self, prompt, schema, session_id: str, user_input: str):
        chat_history = getChatHistory(session_id)
        msgs = getattr(chat_history, "messages", [])

        runnable_struct = prompt | self.llm.with_structured_output(schema)

        def to_both(x):
            d = x.model_dump() if hasattr(x, "model_dump") else x
            msg = d.get("message")
            if not isinstance(msg, str):
                import json
                msg = json.dumps(d, ensure_ascii=False)
            return {"raw": d, "output": msg}

        runnable_both = runnable_struct | RunnableLambda(to_both)

        def _get_history_for_langchain(config):
            try:
                if isinstance(config, str):
                    sid = config
                elif isinstance(config, dict):
                    sid = config.get("configurable", {}).get("session_id") \
                        or config.get("configurable", {}).get("thread_id") \
                        or config.get("session_id") \
                        or config.get("thread_id") \
                        or session_id
                else:
                    sid = session_id
            except Exception:
                sid = session_id

            return getChatHistory(sid)


        chain = RunnableWithMessageHistory(
            runnable=runnable_both,
            get_session_history=_get_history_for_langchain,
            input_messages_key="input",
            history_messages_key="history",
            output_messages_key="output",
        )

        data = chain.invoke(
            {"input": user_input},
            config={"configurable": {"session_id": session_id}},
        )

        msgs_after = getattr(getChatHistory(session_id), "messages", [])
        logger.info("[CHAT_HISTORY:after] sid=%s count=%d messages=%s", session_id, len(msgs_after), msgs_after)

        return schema(**data["raw"])

    def invoke(self, session_id: str, file_input: BytesIO) -> ResumeState:
        locked = acquire_lock(session_id)
        try:
            prev_state = load_state(session_id)

            if prev_state:
                initial_state = prev_state.model_copy(update={"file_input": file_input})
            else:
                initial_state = ResumeState(
                    session_id=session_id,
                    file_input=file_input,
                    current_step=ResumeStep.PARSE_RESUME,
                    message="",
                    match_score=0,
                )

            result = self.graph.invoke(
                initial_state,
                config={"configurable": {
                    "session_id": session_id,
                    "thread_id": session_id,
                }}
            )
            normalized = ResumeState(**result) if isinstance(result, dict) else result

            logger.info(f"[ResumeGraph.invoke]: step={normalized.current_step}, message={normalized.message!r}")

            save_state(session_id, normalized)

            if normalized.current_step in (
                ResumeStep.ENRICH_CONTEXT,
                ResumeStep.ERROR,
            ):
                clear_state(session_id)
                clearMemory(session_id)

            return normalized

        except Exception as e:
            logger.exception("[ResumeGraph.invoke] exception")
            err = ResumeState(
                session_id=session_id,
                file_input=file_input,
                current_step=ResumeStep.ERROR,
                message="ขออภัยครับ เกิดข้อผิดพลาดในการประมวลผล กรุณาลองใหม่อีกครั้ง",
                match_score=0,
                error_message=str(e),
            )
            save_state(session_id, err)
            return err
        finally:
            if locked:
                release_lock(session_id)
