from langgraph.graph import StateGraph, END
from internal.domain.models.interview import InterviewProcessStep, InterviewProcessNode, InterviewProcessState
from internal.adapters.log.logger import logger
from internal.adapters.llm.state_store import acquire_lock, load_state, save_state, release_lock, clear_state
from langgraph.checkpoint.memory import MemorySaver

class InterviewProcessingGraph:
    def __init__(self):
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
        return "pause" if state.error_message else "continue"

    def _intro_node(self, state: InterviewProcessState) -> InterviewProcessState:
        logger.info("[INTRO] Introducing the interview")
        
        return state.model_copy(update={
            "message": "Welcome to the interview. Let's get started.",
            "current_step": InterviewProcessStep.ASK_EXPERIENCE,
        })

    def _experience_node(self, state: InterviewProcessState) -> InterviewProcessState:
        logger.info("[EXPERIENCE] Asking experience question")
        
        return state.model_copy(update={
            "asked_experience": True,
            "message": "Can you tell me about your work experience?",
            "current_step": InterviewProcessStep.ASK_PROJECT,
        })

    def _projects_node(self, state: InterviewProcessState) -> InterviewProcessState:
        logger.info("[PROJECTS] Asking projects question")
        
        return state.model_copy(update={
            "asked_projects": True,
            "message": "Tell me about a project you're proud of.",
            "current_step": InterviewProcessStep.TECHNICAL_QUESTION,
        })

    def _technical_node(self, state: InterviewProcessState) -> InterviewProcessState:
        logger.info("[TECHNICAL] Asking technical question")
        
        return state.model_copy(update={
            "asked_technical": True,
            "message": "How would you debug a bug without help from teammates?",
            "current_step": InterviewProcessStep.BEHAVIORAL_QUESTION,
        })

    def _behavior_node(self, state: InterviewProcessState) -> InterviewProcessState:
        logger.info("[BEHAVIOR] Asking behavioral question")
        
        return state.model_copy(update={
            "asked_behavior": True,
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

    async def invoke(self, session_id: str, user_input: str) -> InterviewProcessState:
        locked = acquire_lock(session_id)
        try:
            prev_state = load_state(session_id)

            if prev_state:
                initial_state = prev_state.model_copy(update={"user_input": user_input})
            else:
                initial_state = InterviewProcessState(
                    session_id=session_id,
                    user_input=user_input,
                    current_step=InterviewProcessStep.INTRO,
                    message="",
                )

            result = await self.graph.ainvoke(
                initial_state,
                config={
                    "configurable": {
                        "session_id": session_id,
                        "thread_id": session_id,
                    },
                    "recursion_limit": 50
                }
            )
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
                error_message=str(e),
            )
            save_state(session_id, err)
            return err
        finally:
            if locked:
                release_lock(session_id)
