from langchain_core.runnables import RunnableLambda
from langgraph.graph import StateGraph, END
from internal.domain.models.interview import InterviewProcessStep, InterviewProcessNode, InterviewProcessState, ProcessPromptResponse
from internal.adapters.log.logger import logger
from internal.adapters.llm.state_store import acquire_lock, load_state, save_state, release_lock, clear_state
from langgraph.checkpoint.memory import MemorySaver
from internal.service.prompts.interview_prompt import INTRO_PROMPT, ASK_EXPERIENCE_PROMPT, ASK_PROJECT_PROMPT
from internal.adapters.llm.loader import getChatHistory, loadLLM
from internal.domain.models.vector import VectorCollections
from internal.adapters.vector_db.factory import get_vector_store
from langchain_core.runnables import RunnableWithMessageHistory

class InterviewProcessingGraph:
    def __init__(self):
        self.llm = loadLLM("interview")
        self.graph = self._build_graph()
        self.state_checkpointer = MemorySaver()

    def _build_graph(self):
        wf = StateGraph(InterviewProcessState)

        wf.add_node(InterviewProcessNode.ROUTER.value, self._router_node)
        wf.add_node(InterviewProcessNode.INTRO.value, self._intro_node)
        wf.add_node(InterviewProcessNode.ASK_EXPERIENCE.value, self._experience_node)
        wf.add_node(InterviewProcessNode.ASK_PROJECT.value, self._projects_node)
        wf.add_node(InterviewProcessNode.TECHNICAL_QUESTION.value, self._technical_node)
        wf.add_node(InterviewProcessNode.BEHAVIORAL_QUESTION.value, self._behavior_node)
        wf.add_node(InterviewProcessNode.WRAP_UP.value, self._feedback_node)
        wf.add_node(InterviewProcessNode.ERROR_HANDLER.value, self._error_handler_node)

        wf.set_entry_point(InterviewProcessNode.ROUTER.value)

        wf.add_conditional_edges(
            InterviewProcessNode.ROUTER.value,
            self._route_from_state,
            {
                InterviewProcessStep.INTRO: InterviewProcessNode.INTRO.value,
                InterviewProcessStep.ASK_EXPERIENCE: InterviewProcessNode.ASK_EXPERIENCE.value,
                InterviewProcessStep.ASK_PROJECT: InterviewProcessNode.ASK_PROJECT.value,
                InterviewProcessStep.TECHNICAL_QUESTION: InterviewProcessNode.TECHNICAL_QUESTION.value,
                InterviewProcessStep.BEHAVIORAL_QUESTION: InterviewProcessNode.BEHAVIORAL_QUESTION.value,
                InterviewProcessStep.WRAP_UP: InterviewProcessNode.WRAP_UP.value,
                InterviewProcessStep.ERROR_HANDLER: InterviewProcessNode.ERROR_HANDLER.value,
            },
        )
        
        for node in [
            InterviewProcessNode.INTRO.value,
            InterviewProcessNode.ASK_EXPERIENCE.value,
            InterviewProcessNode.ASK_PROJECT.value,
            InterviewProcessNode.TECHNICAL_QUESTION.value,
            InterviewProcessNode.BEHAVIORAL_QUESTION.value,
        ]:
            wf.add_conditional_edges(
                node,
                self._after_node_continue_or_pause,
                {
                    "continue": InterviewProcessNode.ROUTER.value,
                    "pause": END,
                },
            )

        wf.add_edge(InterviewProcessNode.WRAP_UP.value, END)
        wf.add_edge(InterviewProcessNode.ERROR_HANDLER.value, END)
        
        return wf.compile()

    def _router_node(self, state: InterviewProcessState) -> InterviewProcessState:
        return state

    def _route_from_state(self, state: InterviewProcessState) -> InterviewProcessStep:
        return state.current_step

    def _after_node_continue_or_pause(self, state: InterviewProcessState) -> str:
        return "continue" if state.go_to_next_step else "pause"

    def _intro_node(self, state: InterviewProcessState) -> InterviewProcessState:
        logger.info("[INTRO] Asking candidate to introduce themselves")
        
        try:
            vector_resume_store = get_vector_store(collection_name=VectorCollections.RESUMES)
            results = vector_resume_store.query_by_text(text=state.session_id, k=100)
            resume_text = "\n".join(
                item.document for item in results.items if item.document
            )
            
            logger.info(f"[INTRO] Resume info preview: {resume_text}")
        except Exception as e:
            logger.exception("[INTRO] Error querying resume from VectorDB")
            resume_text = ""
        
        prompt_input = {
            "input": state.user_input if state.user_input.strip() else "This is the start of the interview - please ask the candidate to introduce themselves.",
            "resume_info": resume_text if resume_text else "No resume information available"
        }
        
        out = self._invoke_node(INTRO_PROMPT, ProcessPromptResponse, state.session_id, prompt_input)

        if out.next_step == "ASK_PROJECT":
            next_step = InterviewProcessStep.ASK_PROJECT
            go_to_next_step = True
        elif out.next_step == "ASK_EXPERIENCE":
            next_step = InterviewProcessStep.ASK_EXPERIENCE
            go_to_next_step = True
        else:
            next_step = InterviewProcessStep.INTRO
            go_to_next_step = False
            
        logger.info(f"[INTRO] Next step determined: {next_step}")
        logger.info(f"[INTRO] Message: {out.message}")
        
        return state.model_copy(update={
            "message": out.message,
            "current_step": next_step,
            "go_to_next_step": go_to_next_step,
        })

    def _experience_node(self, state: InterviewProcessState) -> InterviewProcessState:
        logger.info("[EXPERIENCE] Asking experience question")
        
        prompt_input = {
            "input": state.user_input if state.user_input.strip() else "This is the start of experience question - please ask the candidate to tell you about their work experience.",
            "context": state.context if state.context else "No context available"
        }
        
        out = self._invoke_node(ASK_EXPERIENCE_PROMPT, ProcessPromptResponse, state.session_id, prompt_input)
        
        if out.next_step == "ASK_PROJECT":
            go_to_next_step = True
            next_step = InterviewProcessStep.ASK_PROJECT
        else:
            go_to_next_step = False
            next_step = InterviewProcessStep.ASK_EXPERIENCE
            
        return state.model_copy(update={
            "message": out.message,
            "current_step": next_step,
            "go_to_next_step": go_to_next_step,
        })

    def _projects_node(self, state: InterviewProcessState) -> InterviewProcessState:
        logger.info("[PROJECTS] Asking projects question")
        
        prompt_input = {
            "input": state.user_input if state.user_input.strip() else "This is the start of projects question - please ask the candidate to tell you about their projects.",
            "context": state.context if state.context else "No context available"
        }
        
        out = self._invoke_node(ASK_PROJECT_PROMPT, ProcessPromptResponse, state.session_id, prompt_input)
        
        if out.next_step == "TECHNICAL_QUESTION":
            go_to_next_step = True
            next_step = InterviewProcessStep.TECHNICAL_QUESTION
        else:
            go_to_next_step = False
            next_step = InterviewProcessStep.ASK_PROJECT
            
        return state.model_copy(update={
            "message": out.message,
            "current_step": next_step,
            "go_to_next_step": go_to_next_step,
        })
        

    def _technical_node(self, state: InterviewProcessState) -> InterviewProcessState:
        logger.info("[TECHNICAL] Asking technical question")
        
        return state.model_copy(update={
            "message": "How would you debug a bug without help from teammates?",
            "current_step": InterviewProcessStep.BEHAVIORAL_QUESTION,
        })

    def _behavior_node(self, state: InterviewProcessState) -> InterviewProcessState:
        logger.info("[BEHAVIOR] Asking behavioral question")
        
        return state.model_copy(update={
            "message": "Tell me about a time you had to deal with a difficult situation.",
            "current_step": InterviewProcessStep.WRAP_UP,
        })

    def _feedback_node(self, state: InterviewProcessState) -> InterviewProcessState:
        logger.info("[FEEDBACK] Wrapping up")
        
        return state.model_copy(update={
            "message": "Great job! That concludes this part of the interview.",
        })

    def _error_handler_node(self, state: InterviewProcessState) -> InterviewProcessState:
        logger.error(f"[ERROR HANDLER] Processing error: {state.error_message}")
        
        return state.model_copy(update={
            "message": "Sorry, there was an error processing your request. Please try again.",
        })
        
    def _invoke_node(self, prompt, schema, session_id: str, prompt_input):
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

        if isinstance(prompt_input, str):
            invoke_data = {"input": prompt_input}
        else:
            invoke_data = prompt_input

        data = chain.invoke(
            invoke_data,
            config={"configurable": {"session_id": session_id}},
        )

        msgs_after = getattr(getChatHistory(session_id), "messages", [])
        logger.info("[CHAT_HISTORY:after] sid=%s count=%d messages=%s", session_id, len(msgs_after), msgs_after)

        return schema(**data["raw"])

    async def invoke(self, session_id: str, user_input: str, context: str = "") -> InterviewProcessState:
        logger.info(f"[InterviewProcessingGraph.invoke] Called:")
        locked = acquire_lock(session_id)
        try:
            prev_state = load_state(session_id)

            if prev_state:
                initial_state = prev_state.model_copy(
                    update={
                        "user_input": user_input,
                        "context": context
                    }
                )
            else:
                initial_state = InterviewProcessState(
                    session_id=session_id,
                    user_input=user_input,
                    current_step=InterviewProcessStep.INTRO,
                    message=None,
                    context=context,
                    error_message=None,
                )

            result = await self.graph.ainvoke(initial_state)
            normalized = InterviewProcessState(**result) if isinstance(result, dict) else result

            logger.info(f"[InterviewProcessingGraph.invoke]: step={normalized.current_step}, message={normalized.message!r}")
            if normalized.current_step == InterviewProcessStep.ERROR_HANDLER:
                clear_state(session_id)
            else:
                save_state(session_id, normalized)
            return normalized

        except Exception as e:
            logger.exception("[InterviewProcessingGraph.invoke] exception")
            err = InterviewProcessState(
                session_id=session_id,
                user_input=user_input,
                current_step=InterviewProcessStep.ERROR_HANDLER,
                message="Sorry, there was an error processing your request. Please try again.",
                context=None,
                error_message=str(e),
            )
            save_state(session_id, err)
            return err
        finally:
            if locked:
                release_lock(session_id)
