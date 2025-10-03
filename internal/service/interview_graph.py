from internal.adapters.log.logger import logger
from internal.domain.models.interview import InterviewNode, InterviewState, InterviewProcessStep, ExampleQuestionsResponse
from langgraph.graph import StateGraph, END
from internal.service.process_graph import InterviewProcessingGraph
from datetime import datetime, timezone
from internal.domain.models.interview import InterviewProcessNode
from internal.adapters.llm.state_store import acquire_lock, load_state, save_state, release_lock, clear_state
from internal.domain.models.vector import VectorCollections
from internal.adapters.vector_db.factory import get_vector_store
from internal.service.prompts.example_question_prompt import EXAMPLE_QUESTIONS_PROMPT
from internal.adapters.llm.loader import loadLLM
from langchain_core.runnables import RunnableWithMessageHistory, RunnableLambda
from internal.adapters.llm.loader import getChatHistory

class InterviewGraph:
    def __init__(self):
        logger.info("[InterviewGraph] Initializing...")
        self.graph = self._build_graph()
        self.process_graph = InterviewProcessingGraph()
        self.llm = loadLLM("example_question")
        logger.info("[InterviewGraph] Initialization complete")

    def _ok_or_error(self, state: InterviewState) -> str:
        return "error" if state.error_message else "ok"

    def _build_graph(self):
        logger.info("[InterviewGraph] Building graph...")
        wf = StateGraph(InterviewState)

        wf.add_node(InterviewNode.QUERY_VECTOR_DB.value, self._query_vector_db_node)
        wf.add_node(InterviewNode.GET_EXAMPLE_QUESTION.value, self._get_example_question_node)
        wf.add_node(InterviewNode.PROCESS_ANSWER.value, self._process_answer_node)
        wf.add_node(InterviewNode.STORE_ANSWER.value, self._store_answer_node)
        
        wf.set_entry_point(InterviewNode.QUERY_VECTOR_DB.value)
        logger.info(f"[InterviewGraph] Entry point set to: {InterviewNode.QUERY_VECTOR_DB.value}")

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
        logger.info("[InterviewGraph] Graph compiled successfully")
        return compiled_graph
    
    query_text_map = {
        InterviewProcessStep.ASK_EXPERIENCE: "Work experience, professional history, past job roles, internships",
        InterviewProcessStep.ASK_PROJECT: "Projects, open-source work, hackathons, academic projects",
        InterviewProcessStep.TECHNICAL_QUESTION: "Technical skills, programming languages, frameworks, problem-solving",
        InterviewProcessStep.BEHAVIORAL_QUESTION: "Soft skills, teamwork, communication, leadership, decision-making"
    }

    async def _query_vector_db_node(self, state: InterviewState) -> InterviewState:
        logger.info(f"[QUERY VECTOR DB]: Querying vector database for session {state.session_id} with current step {state.current_step}")
        
        if state.current_step in [InterviewProcessStep.GREETING]:
            logger.info(f"[QUERY VECTOR DB]: Skipping for {state.current_step.value} - using static questions")
            return state
        
        if not state.go_to_next_step:
            logger.info(f"[QUERY VECTOR DB]: Skipping query - not transitioning to next step")
            return state
        
        if not state.session_id:
            return state.model_copy(update={
                "error_message": "Session ID is required for vector database query"
            })
        
        try:
            vector_resume_store = get_vector_store(collection_name=VectorCollections.RESUMES)
            query_config = self._get_query_config(state.current_step)
            query_text = self.query_text_map.get(state.current_step, "General candidate information")

            results = vector_resume_store.query_by_text(
                text=query_text,
                k=query_config["k"],
                include_documents=True,
                session_id=state.session_id
            )
            
            context_text = "\n".join([item.document for item in results.items])
            logger.info(f"[QUERY VECTOR DB]: Context text: {context_text}")
            
            return state.model_copy(update={
                "context_prompt": context_text,
            })
            
        except ValueError as e:
            logger.error(f"[QUERY VECTOR DB]: Validation error - {str(e)}")
            return state.model_copy(update={
                "error_message": f"Invalid query parameters: {str(e)}"
            })
            
        except ConnectionError as e:
            logger.error(f"[QUERY VECTOR DB]: Connection error - {str(e)}")
            return state.model_copy(update={
                "error_message": "Unable to connect to vector database. Please try again."
            })
            
        except Exception as e:
            logger.error(f"[QUERY VECTOR DB]: Unexpected error - {str(e)}", exc_info=True)
            return state.model_copy(update={
                "error_message": f"Vector database query failed: {str(e)}"
            })
    
    def _get_query_config(self, current_step: InterviewProcessStep) -> dict:
        configs = {
            InterviewProcessStep.INTRO: {
                "k": 100,
                "min_score": 0.3,
                "max_context_length": 0,
                "include_metadata": True
            },
            InterviewProcessStep.GREETING: {
                "k": 100,
                "min_score": 0.4,
                "max_context_length": 0,
                "include_metadata": False
            },
            InterviewProcessStep.ASK_EXPERIENCE: {
                "k": 15,
                "min_score": 0.5,
                "max_context_length": 3000,
                "include_metadata": True
            },
            InterviewProcessStep.ASK_PROJECT: {
                "k": 10,
                "min_score": 0.6,
                "max_context_length": 2500,
                "include_metadata": True
            },
            InterviewProcessStep.TECHNICAL_QUESTION: {
                "k": 8,
                "min_score": 0.7,
                "max_context_length": 2000,
                "include_metadata": True
            },
            InterviewProcessStep.BEHAVIORAL_QUESTION: {
                "k": 5,
                "min_score": 0.6,
                "max_context_length": 1500,
                "include_metadata": False
            },
            InterviewProcessStep.WRAP_UP: {
                "k": 20,
                "min_score": 0.4,
                "max_context_length": 4000,
                "include_metadata": True
            }
        }
        
        return configs.get(current_step, {
            "k": 10,
            "min_score": 0.5,
            "max_context_length": 3000,
            "include_metadata": True
        })
        
    async def _get_example_question_node(self, state: InterviewState) -> InterviewState:
        logger.info(f"[GET EXAMPLE QUESTIONS]: Getting example questions for session {state.session_id} with current step {state.current_step}")
        try:
            if state.go_to_next_step:
                if state.current_step in [InterviewProcessStep.GREETING, InterviewProcessStep.INTRO]:
                    logger.info(f"[GET EXAMPLE QUESTIONS] Skipping for {state.current_step.value} - examples are embedded in prompt")
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
                
                logger.info(f"[GET EXAMPLE QUESTIONS] Generated example questions: {example_questions}")
            
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
        logger.info(f"[PROCESS ANSWER]: Processing answer for session {state.session_id} with current step {state.current_step}, go_to_next_step={state.go_to_next_step}")
        try:
            answer = await self.process_graph.invoke(state)
            logger.info(f"[PROCESS ANSWER]: Process graph returned: current_step={answer.current_step}, go_to_next_step={answer.go_to_next_step}")
            return answer
        except Exception as e:
            logger.error(f"[PROCESS ANSWER]: Error processing answer: {str(e)}", exc_info=True)
            return state.model_copy(update={
                "error_message": str(e),
            })

    async def _store_answer_node(self, state: InterviewState) -> InterviewState:
        logger.info(f"[STORE ANSWER]: Storing answer for session {state.session_id} with current step {state.current_step}")
        try:
            return state
        except Exception as e:
            return state.model_copy(update={
                "error_message": str(e),
            })

    async def invoke(self, session_id: str, user_input: str, position: str) -> InterviewState:
        logger.info(f"[INVOKE]: Invoking graph for session {session_id} with user input {user_input} and position {position}")
        locked = acquire_lock(session_id)
        logger.info(f"[INVOKE]: Acquired lock: {locked}")
        try:
            logger.info(f"[INVOKE]: Loading previous state for session {session_id}")
            prev_state = load_state(session_id)
            logger.info(f"[INVOKE]: Loaded previous state: {prev_state}")
            
            if prev_state:
                logger.info(f"[INVOKE]: Loading previous state: current_step={prev_state.current_step}, go_to_next_step={prev_state.go_to_next_step}")
                initial_state = prev_state.model_copy(
                    update={
                        "user_input": user_input,
                        "message": "",
                        "error_message": "",
                    }
                )
            else:
                logger.info("[INVOKE]: No previous state found, starting with GREETING")
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
                )

            logger.info(f"[INVOKE]: Invoking graph with initial state: current_step={initial_state.current_step}, go_to_next_step={initial_state.go_to_next_step}")
            result = await self.graph.ainvoke(
                initial_state,
                config={"configurable": {
                    "session_id": session_id,
                    "thread_id": session_id,
                }}
            )
            logger.info(f"[INVOKE]: Graph execution completed")

            normalized = InterviewState(**result) if isinstance(result, dict) else result
            logger.info(f"[INVOKE]: Result normalized: current_step={normalized.current_step}, go_to_next_step={normalized.go_to_next_step}, message_length={len(normalized.message) if normalized.message else 0}")

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
            )
            save_state(session_id, err)
            return err
        finally:
            if locked:
                logger.info(f"[INVOKE]: Releasing lock for session {session_id}")
                release_lock(session_id)