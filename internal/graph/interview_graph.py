from internal.infra.log.logger import logger
from internal.graph.interview_step import InterviewStep
from internal.graph.interview_state import InterviewState, AskQuestionRes
from internal.llm.prompt_builder import ASK_QUESTION_PROMPT
from langgraph.graph import StateGraph, END
from internal.llm.loader import getChatHistory
from langchain_core.runnables import RunnableWithMessageHistory
from internal.infra.db.redis import save_state, load_state, clear_state, acquire_lock, release_lock
from internal.llm.state_store import clearMemory
from langchain_core.runnables import RunnableLambda

class InterviewGraph:
    def __init__(self, llm):
        self.llm = llm
        self.graph = self._build_graph()
    
    def _build_graph(self):
        wf = StateGraph(InterviewState)
        
        wf.add_node(InterviewState.ROLE_SELECTION.value, self._router_node)
        wf.add_node(InterviewState.ASK_QUESTION.value, self._ask_question_node)
        wf.add_node(InterviewState.PARSE_ANSWER.value, self._parse_answer_node)
        wf.add_node(InterviewState.GIVE_FEEDBACK.value, self._give_feedback_node)
        wf.add_node(InterviewState.END_INTERVIEW.value, self._end_interview_node)
        wf.add_node(InterviewState.ERROR.value, self._error_handler_node)

        wf.set_entry_point(InterviewState.ROLE_SELECTION.value)

        wf.add_conditional_edges(
            InterviewState.ROLE_SELECTION.value,
            self._route_from_state,
            {
                InterviewState.ASK_QUESTION.value: InterviewState.ASK_QUESTION.value,
                InterviewState.PARSE_ANSWER.value: InterviewState.PARSE_ANSWER.value,
                InterviewState.GIVE_FEEDBACK.value: InterviewState.GIVE_FEEDBACK.value,
                InterviewState.END_INTERVIEW.value: InterviewState.END_INTERVIEW.value,
                InterviewState.ERROR.value: InterviewState.ERROR.value,
            },
        )

        for node in [
            InterviewState.ASK_QUESTION.value,
            InterviewState.PARSE_ANSWER.value,
            InterviewState.GIVE_FEEDBACK.value,
        ]:
            wf.add_conditional_edges(
                node,
                self._after_node_continue_or_pause,
                {
                    "continue": InterviewState.ROLE_SELECTION.value,
                    "pause": END,
                },
            )
            
        wf.add_edge(InterviewState.END_INTERVIEW.value, END)
        wf.add_edge(InterviewState.ERROR.value, END)
        return wf.compile()

    def _router_node(self, state: InterviewState) -> InterviewState:
        return state

    def _route_from_state(self, state: InterviewState) -> InterviewState:
        return state.current_step

    def _ask_question_node(self, state: InterviewState) -> InterviewState:
        logger.info(f"[VALIDATION INPUT]: input={state.user_input}")
        
        out = self._invoke_node(ASK_QUESTION_PROMPT, AskQuestionRes, state.session_id, state.user_input)
        
        logger.info(f"[VALIDATION OUTPUT]: out={out}")
        
        current_step = InterviewState.ASK_QUESTION
        
        return state.model_copy(update={
            "message": out.message,
            "current_step": current_step,
        })
        
    def _error_handler_node(self, state: InterviewState) -> InterviewState:
        logger.error(f"[ERROR_HANDLER]: {state.error_message}")
        return state.model_copy(update={
            "message": "ขออภัยครับ เกิดข้อผิดพลาดในการประมวลผล กรุณาลองใหม่อีกครั้ง",
            "match_score": 0,
            "current_step": InterviewState.ERROR,
        })
    
    def _after_node_continue_or_pause(self, state: InterviewState) -> str:
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

    def invoke(self, session_id: str, user_input: str) -> InterviewState:
        locked = acquire_lock(session_id)
        try:
            prev_state = load_state(session_id)

            if prev_state:
                initial_state = prev_state.model_copy(update={"user_input": user_input})
            else:
                initial_state = InterviewState(
                    session_id=session_id,
                    user_input=user_input,
                    current_step=InterviewState.ASK_QUESTION,
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
            normalized = InterviewState(**result) if isinstance(result, dict) else result

            logger.info(f"[InterviewGraph.invoke]: step={normalized.current_step}, message={normalized.message!r}")

            save_state(session_id, normalized)

            if normalized.current_step in (
                InterviewState.REJECT,
                InterviewState.END_CONVERSATION,
                InterviewState.ERROR,
            ):
                clear_state(session_id)
                clearMemory(session_id)

            return normalized

        except Exception as e:
            logger.exception("[InterviewGraph.invoke] exception")
            err = InterviewState(
                session_id=session_id,
                user_input=user_input,
                current_step=InterviewState.ERROR,
                message="ขออภัยครับ เกิดข้อผิดพลาดในการประมวลผล กรุณาลองใหม่อีกครั้ง",
                match_score=0,
                error_message=str(e),
            )
            save_state(session_id, err)
            return err
        finally:
            if locked:
                release_lock(session_id)
