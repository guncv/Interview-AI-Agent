from core.log.logger import logger
from domain.models.interview import InterviewNode, InterviewState, InterviewProcessStep, ExampleQuestionsResponse
from langgraph.graph import StateGraph, END
from services.process_graph import InterviewProcessingGraph
from datetime import datetime, timezone
from domain.models.interview import InterviewProcessNode
from infrastructure.llm.state_store import acquire_lock, load_state, save_state, release_lock, clear_state
from services.prompts.example_question_prompt import EXAMPLE_QUESTIONS_PROMPT
from infrastructure.llm.loader import loadLLM
from langchain_core.runnables import RunnableWithMessageHistory, RunnableLambda
from infrastructure.llm.loader import getChatHistory
from services.interview_session import InterviewSessionService

class InterviewGraph:
    def __init__(self):
        self.graph = self._build_graph()
        self.process_graph = InterviewProcessingGraph()
        self.interview_session_service = InterviewSessionService()
        self.llm = loadLLM("example_question")

    def _ok_or_error(self, state: InterviewState) -> str:
        return "error" if state.error_message else "ok"

    def _build_graph(self):
        wf = StateGraph(InterviewState)

        wf.add_node(InterviewNode.QUERY_VECTOR_DB.value, self._query_vector_db_node)
        wf.add_node(InterviewNode.GET_EXAMPLE_QUESTION.value, self._get_example_question_node)
        wf.add_node(InterviewNode.PROCESS_ANSWER.value, self._process_answer_node)
        wf.add_node(InterviewNode.STORE_ANSWER.value, self._store_answer_node)
        
        wf.set_entry_point(InterviewNode.QUERY_VECTOR_DB.value)

        wf.add_conditional_edges(InterviewNode.QUERY_VECTOR_DB.value, self._ok_or_error, {
            "ok": InterviewNode.GET_EXAMPLE_QUESTION.value,
            "error": END,
        })

        wf.add_conditional_edges(InterviewNode.GET_EXAMPLE_QUESTION.value, self._ok_or_error, {
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

        compiled_graph = wf.compile()
        return compiled_graph
    

    resume_section_map = {
        InterviewProcessStep.ROUTER: [],
        InterviewProcessStep.INTRO: ["is_experience"],
        InterviewProcessStep.ASK_EXPERIENCE: ["experience"],
        InterviewProcessStep.ASK_PROJECT: ["project"],
        InterviewProcessStep.TECHNICAL_QUESTION: ["skill_technical"],
        InterviewProcessStep.BEHAVIORAL_QUESTION: ["behavior"],
        InterviewProcessStep.WRAP_UP: [],
    }

    async def _query_vector_db_node(self, state: InterviewState) -> InterviewState:
        if state.current_step in [InterviewProcessStep.GREETING, InterviewProcessStep.ROUTER]:
            return state
        
        if not state.go_to_next_step:
            return state
        
        if not state.session_id:
            return state.model_copy(update={
                "error_message": "Session ID is required for resume context retrieval"
            })
        
        try:
            resume_context = await self.interview_session_service.get_resume_context(state.session_id)
            
            relevant_sections = self.resume_section_map.get(
                state.current_step,
                []
            )
            
            if not relevant_sections:
                return state
            
            context_parts = []
            for section in relevant_sections:
                if section in resume_context and resume_context[section]:
                    section_title = section.replace("_", " ").title()
                    context_parts.append(f"=== {section_title} ===\n{resume_context[section]}")
            
            if not context_parts:
                logger.warning(f"[GET RESUME CONTEXT]: No relevant resume data found for session {state.session_id}")
            
            context_text = "\n\n".join(context_parts)
            
            return state.model_copy(update={
                "context_prompt": context_text,
            })
            
        except Exception as e:
            logger.error(f"[GET RESUME CONTEXT]: Unexpected error - {str(e)}", exc_info=True)
            return state.model_copy(update={
                "error_message": f"Resume context retrieval failed: {str(e)}"
            })
    
    async def _get_example_question_node(self, state: InterviewState) -> InterviewState:
        try:
            if state.go_to_next_step:
                if state.current_step in [InterviewProcessStep.GREETING, InterviewProcessStep.INTRO, InterviewProcessStep.WRAP_UP]:
                    return state.model_copy(update={
                        "example_questions": [],
                    })
                
                prompt_input = {
                    "position": state.position,
                    "resume_info": state.context_prompt,
                    "current_state": state.current_storing_node.value,
                    "input": state.user_input.strip() or "Generate example questions for this interview"
                }
                
                runnable_struct = EXAMPLE_QUESTIONS_PROMPT | self.llm.with_structured_output(ExampleQuestionsResponse)
                
                def to_both(x):
                    d = x.model_dump() if hasattr(x, "model_dump") else x
                    return {"raw": d, "output": d.get("example_questions", [])}
                
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
                                or state.session_id
                        else:
                            sid = state.session_id
                    except Exception:
                        sid = state.session_id
                    return getChatHistory(sid)
                
                chain = RunnableWithMessageHistory(
                    runnable=runnable_both,
                    get_session_history=_get_history_for_langchain,
                    input_messages_key="input",
                    history_messages_key="history",
                    output_messages_key="output",
                )
                
                data = chain.invoke(
                    prompt_input,
                    config={"configurable": {"session_id": state.session_id}},
                )
                
                example_questions = data["raw"].get("example_questions", [])
            
            else:
                example_questions = state.example_questions
                
            return state.model_copy(update={
                "example_questions": example_questions,
            })
            
        except Exception as e:
            logger.error(f"[GET EXAMPLE QUESTIONS] Error generating example questions: {str(e)}")
            return state.model_copy(update={
                "error_message": f"Failed to generate example questions: {str(e)}",
            })

    async def _process_answer_node(self, state: InterviewState) -> InterviewState:
        try:
            answer = await self.process_graph.invoke(state)
            return answer
        except Exception as e:
            logger.error(f"[PROCESS ANSWER]: Error processing answer: {str(e)}", exc_info=True)
            return state.model_copy(update={
                "error_message": str(e),
            })

    async def _store_answer_node(self, state: InterviewState) -> InterviewState:
        try:
            return state
        except Exception as e:
            return state.model_copy(update={
                "error_message": str(e),
            })

    async def invoke(self, session_id: str, user_input: str, position: str, selected_stages: list[str] = None) -> InterviewState:
        if selected_stages is None:
            selected_stages = []
            
        locked = acquire_lock(session_id)
        try:
            prev_state = load_state(session_id)
            
            if prev_state:
                initial_state = prev_state.model_copy(
                    update={
                        "user_input": user_input,
                        "message": "",
                        "error_message": "",
                    }
                )
            else:
                initial_state = InterviewState(
                    session_id=session_id,
                    user_input=user_input,
                    context_prompt="",
                    message="",
                    position=position,
                    example_questions=[],
                    current_storing_node=InterviewProcessNode.GREETING,
                    start_at=datetime.now(timezone.utc).isoformat(),
                    end_at=datetime.now(timezone.utc).isoformat(),
                    go_to_next_step=True,
                    error_message="",
                    current_step=InterviewProcessStep.GREETING,
                    selected_stages=selected_stages,
                )

            result = await self.graph.ainvoke(
                initial_state,
                config={"configurable": {
                    "session_id": session_id,
                    "thread_id": session_id,
                }}
            )

            normalized = InterviewState(**result) if isinstance(result, dict) else result

            if normalized.current_step == InterviewProcessStep.ERROR_HANDLER:
                clear_state(session_id)
                return normalized
            else:
                save_state(session_id, normalized)
                return normalized

        except Exception as e:
            logger.error(f"[INVOKE]: Exception occurred for session {session_id}: {str(e)}", exc_info=True)
            err = InterviewState(
                session_id=session_id,
                user_input=user_input,
                context_prompt="",
                message="",
                position="",
                example_questions=[],
                current_storing_node=InterviewProcessNode.GREETING,
                start_at=datetime.now(timezone.utc).isoformat(),
                end_at=datetime.now(timezone.utc).isoformat(),
                go_to_next_step=False,
                error_message=str(e),
                current_step=InterviewProcessStep.ERROR_HANDLER,
                selected_stages=selected_stages if selected_stages else [],
            )
            save_state(session_id, err)
            return err
        finally:
            if locked:
                release_lock(session_id)