from langchain_core.runnables import RunnableLambda
from langgraph.graph import StateGraph, END
from internal.domain.models.interview import InterviewProcessStep, InterviewProcessNode, ProcessPromptResponse, InterviewState
from internal.adapters.log.logger import logger
from internal.adapters.llm.state_store import save_state, clearMemory
from langgraph.checkpoint.memory import MemorySaver
from internal.service.prompts.interview_prompt import INTRO_PROMPT, ASK_EXPERIENCE_PROMPT, ASK_PROJECT_PROMPT, GREETING_PROMPT, ASK_TECHNICAL_PROMPT, ASK_BEHAVIORAL_PROMPT, WRAP_UP_PROMPT
from internal.adapters.llm.loader import getChatHistory, loadLLM
from langchain_core.runnables import RunnableWithMessageHistory
from datetime import datetime, timezone
from langchain_core.prompts import ChatPromptTemplate
from internal.service.websocket import WebSocketService

class InterviewProcessingGraph:
    def __init__(self):
        self.llm = loadLLM("interview")
        self.graph = self._build_graph()
        self.state_checkpointer = MemorySaver()
        self.websocket_service = WebSocketService()
        
        self.stage_to_step_map = {
            "Experience": InterviewProcessStep.ASK_EXPERIENCE,
            "Project": InterviewProcessStep.ASK_PROJECT,
            "Technical": InterviewProcessStep.TECHNICAL_QUESTION,
            "Behavioral": InterviewProcessStep.BEHAVIORAL_QUESTION,
        }
        
        self.mandatory_stages = [
            InterviewProcessStep.GREETING,
            InterviewProcessStep.INTRO,
            InterviewProcessStep.WRAP_UP,
        ]
        
        self.stage_flow_order = [
            InterviewProcessStep.INTRO,
            InterviewProcessStep.ASK_EXPERIENCE,
            InterviewProcessStep.ASK_PROJECT,
            InterviewProcessStep.TECHNICAL_QUESTION,
            InterviewProcessStep.BEHAVIORAL_QUESTION,
            InterviewProcessStep.WRAP_UP,
        ]
        
    def _is_stage_enabled(self, stage: InterviewProcessStep, selected_stages: list[str]) -> bool:
        if stage in self.mandatory_stages:
            return True
        
        for stage_name, stage_step in self.stage_to_step_map.items():
            if stage_step == stage and stage_name in selected_stages:
                return True
        
        return False
    
    def _get_next_enabled_stage(self, current_stage: InterviewProcessStep, selected_stages: list[str]) -> InterviewProcessStep:
        try:
            current_index = self.stage_flow_order.index(current_stage)
        except ValueError:
            logger.warning(f"[GET NEXT ENABLED STAGE] Current stage {current_stage} not found in flow order, returning COMPLETED")
            return InterviewProcessStep.ERROR_HANDLER
        
        for i in range(current_index + 1, len(self.stage_flow_order)):
            next_stage = self.stage_flow_order[i]
            if self._is_stage_enabled(next_stage, selected_stages):
                return next_stage
        
        return InterviewProcessStep.ERROR_HANDLER
        
    def _build_graph(self):
        wf = StateGraph(InterviewState)

        wf.add_node(InterviewProcessNode.ROUTER.value, self._router_node)
        wf.add_node(InterviewProcessNode.GREETING.value, self._greeting_node)
        wf.add_node(InterviewProcessNode.INTRO.value, self._intro_node)
        wf.add_node(InterviewProcessNode.ASK_EXPERIENCE.value, self._experience_node)
        wf.add_node(InterviewProcessNode.ASK_PROJECT.value, self._projects_node)
        wf.add_node(InterviewProcessNode.TECHNICAL_QUESTION.value, self._technical_node)
        wf.add_node(InterviewProcessNode.BEHAVIORAL_QUESTION.value, self._behavior_node)
        wf.add_node(InterviewProcessNode.WRAP_UP.value, self._wrap_up_node)
        wf.add_node(InterviewProcessNode.COMPLETED.value, self._completed_node)
        wf.add_node(InterviewProcessNode.ERROR_HANDLER.value, self._error_handler_node)

        wf.set_entry_point(InterviewProcessNode.ROUTER.value)

        wf.add_conditional_edges(
            InterviewProcessNode.ROUTER.value,
            self._route_from_state,
            {
                InterviewProcessStep.GREETING: InterviewProcessNode.GREETING.value,
                InterviewProcessStep.INTRO: InterviewProcessNode.INTRO.value,
                InterviewProcessStep.ASK_EXPERIENCE: InterviewProcessNode.ASK_EXPERIENCE.value,
                InterviewProcessStep.ASK_PROJECT: InterviewProcessNode.ASK_PROJECT.value,
                InterviewProcessStep.TECHNICAL_QUESTION: InterviewProcessNode.TECHNICAL_QUESTION.value,
                InterviewProcessStep.BEHAVIORAL_QUESTION: InterviewProcessNode.BEHAVIORAL_QUESTION.value,
                InterviewProcessStep.WRAP_UP: InterviewProcessNode.WRAP_UP.value,
                InterviewProcessStep.COMPLETED: InterviewProcessNode.COMPLETED.value,
                InterviewProcessStep.ERROR_HANDLER: InterviewProcessNode.ERROR_HANDLER.value,
            },
        )
        
        for node in [
            InterviewProcessNode.GREETING.value,
            InterviewProcessNode.INTRO.value,
            InterviewProcessNode.ASK_EXPERIENCE.value,
            InterviewProcessNode.ASK_PROJECT.value,
            InterviewProcessNode.TECHNICAL_QUESTION.value,
            InterviewProcessNode.BEHAVIORAL_QUESTION.value,
            InterviewProcessNode.WRAP_UP.value,
        ]:
            wf.add_conditional_edges(
                node,
                self._after_node_continue_or_pause,
                {
                    "continue": InterviewProcessNode.ROUTER.value,
                    "pause": END,
                },
            )

        wf.add_edge(InterviewProcessNode.ERROR_HANDLER.value, END)
        wf.add_edge(InterviewProcessNode.COMPLETED.value, END)
        
        return wf.compile()

    def _router_node(self, state: InterviewState) -> InterviewState:
        return state

    def _route_from_state(self, state: InterviewState) -> InterviewProcessStep:
        return state.current_step

    def _after_node_continue_or_pause(self, state: InterviewState) -> str:
        if state.go_to_next_step:
            try:
                clearMemory(state.session_id)
            except Exception:
                logger.exception(f"[MEMORY] Failed to clear memory for session {state.session_id}")
        return "pause"

    def _greeting_node(self, state: InterviewState) -> InterviewState:
        return self._run_step(
            state,
            GREETING_PROMPT,
            "This is the start of the interview - please greet the candidate.",
            InterviewProcessNode.GREETING,
            InterviewProcessStep.GREETING,
            deterministic_next_step=InterviewProcessStep.INTRO,
        )

    def _intro_node(self, state: InterviewState) -> InterviewState:
        return self._run_step(
            state,
            INTRO_PROMPT,
            "This is the start of intro question - please ask the candidate to introduce themselves.",
            InterviewProcessNode.INTRO,
            InterviewProcessStep.INTRO,
        )


    def _experience_node(self, state: InterviewState) -> InterviewState:
        return self._run_step(
            state,
            ASK_EXPERIENCE_PROMPT,
            "This is the start of experience question - please ask the candidate to tell you about their work experience.",
            InterviewProcessNode.ASK_EXPERIENCE,
            InterviewProcessStep.ASK_EXPERIENCE,
        )

    def _projects_node(self, state: InterviewState) -> InterviewState:
        return self._run_step(
            state,
            ASK_PROJECT_PROMPT,
            "This is the start of projects question - please ask the candidate to tell you about their projects.",
            InterviewProcessNode.ASK_PROJECT,
            InterviewProcessStep.ASK_PROJECT,
        )

    def _technical_node(self, state: InterviewState) -> InterviewState:
        return self._run_step(
            state,
            ASK_TECHNICAL_PROMPT,
            "This is the start of technical question - please ask the candidate to tell you about their technical skills.",
            InterviewProcessNode.TECHNICAL_QUESTION,
            InterviewProcessStep.TECHNICAL_QUESTION,
        )

    def _behavior_node(self, state: InterviewState) -> InterviewState:
        return self._run_step(
            state,
            ASK_BEHAVIORAL_PROMPT,
            "This is the start of behavioral question - please ask the candidate to tell you about a time they had to deal with a difficult situation.",
            InterviewProcessNode.BEHAVIORAL_QUESTION,
            InterviewProcessStep.BEHAVIORAL_QUESTION,
        )

    def _wrap_up_node(self, state: InterviewState) -> InterviewState:
        return self._run_step(
            state,
            WRAP_UP_PROMPT,
            "This is the start of wrap up interview - please say goodbye to the candidate.",
            InterviewProcessNode.WRAP_UP,
            InterviewProcessStep.WRAP_UP,
            deterministic_next_step=InterviewProcessStep.COMPLETED,
        )
        
    def _completed_node(self, state: InterviewState) -> InterviewState:
        return state

    def _error_handler_node(self, state: InterviewState) -> InterviewState:
        logger.error(f"[ERROR HANDLER] Processing error: {state.error_message}")
        start_date = datetime.now(timezone.utc).isoformat()
        out = ProcessPromptResponse(message=state.error_message, go_to_next_step=False)
        return self._update_state_with_message(
            state,
            start_date,
            out,
            InterviewProcessNode.ERROR_HANDLER,
            InterviewProcessStep.ERROR_HANDLER,
            False,
        )

    def _run_step(
        self,
        state: InterviewState,
        prompt: ChatPromptTemplate,
        fallback_input: str,
        current_state: InterviewProcessNode,
        current_step: InterviewProcessStep,
        deterministic_next_step: InterviewProcessStep | None = None,
    ) -> InterviewState:
        example_questions_formatted = self._format_example_questions(state.example_questions)
        
        context_prompt_input = {
            "input": state.user_input.strip() or fallback_input,
            "resume_info": state.context_prompt,
            "example_questions_formatted": example_questions_formatted,
        }
        
        start_date = datetime.now(timezone.utc).isoformat()
        out = self._invoke_node(prompt, state.session_id, context_prompt_input)
        
        if out.go_to_next_step:
            if deterministic_next_step is not None:
                next_step = deterministic_next_step
            else:
                next_step = self._get_next_enabled_stage(current_step, state.selected_stages)
        else:
            next_step = current_step

        return self._update_state_with_message(state, start_date, out, current_state, next_step, out.go_to_next_step)
    
    def _format_example_questions(self, example_questions: list[str]) -> str:
        if not example_questions:
            return "No example questions available. Please generate appropriate questions based on the context."
        
        formatted = []
        for i, question in enumerate(example_questions, 1):
            formatted.append(f"{i}. {question}")
        
        return "\n".join(formatted)

    def _update_state_with_message(
        self,
        state: InterviewState,
        start_date: str,
        out: ProcessPromptResponse,
        current_state: InterviewProcessNode,
        next_step: InterviewProcessStep,
        go_to_next_step: bool,
    ) -> InterviewState:
        
        now = datetime.now(timezone.utc).isoformat()
    
        return state.model_copy(
            update={
                "message": out.message or "",
                "current_storing_node": current_state,
                "start_at": start_date,
                "end_at": now,
                "current_step": next_step,
                "go_to_next_step": go_to_next_step,
            }
        )

    def _invoke_node(self, prompt, session_id, prompt_input):
        runnable_struct = prompt | self.llm.with_structured_output(ProcessPromptResponse)

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

        return ProcessPromptResponse(**data["raw"])

    async def invoke(self, state: InterviewState) -> InterviewState:
        
        try:
            result = await self.graph.ainvoke(state)
            normalized = InterviewState(**result) if isinstance(result, dict) else result
            
            return normalized

        except Exception as e:
            logger.exception("[InterviewProcessingGraph.invoke] exception")
            err = InterviewState(
                session_id=state.session_id,
                user_input=state.user_input,
                current_step=InterviewProcessStep.ERROR_HANDLER,
                message="",
                context_prompt="",
                position="",
                example_questions=[],
                current_storing_node=InterviewProcessNode.GREETING,
                start_at=datetime.now(timezone.utc).isoformat(),
                end_at=datetime.now(timezone.utc).isoformat(),
                selected_stages=state.selected_stages,
                go_to_next_step=False,
                error_message=str(e),
            )
            save_state(state.session_id, err)
            return err
