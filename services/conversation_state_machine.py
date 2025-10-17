"""
Conversation State Machine for Interview AI Agent

This module implements a proper conversational state machine using LangGraph.
Each interview stage is a conversational agent that:
1. Retrieves relevant context using RAG
2. Generates responses using LLM
3. Decides when to transition to next state
4. Handles multi-turn conversations within each state

Design Pattern: Agent-based Conversation with RAG
"""

from typing import Dict, Any, List
from langgraph.graph import StateGraph, END
from domain.models.interview import InterviewState, InterviewProcessStep, InterviewProcessNode, ProcessPromptResponse
from services.rag_retrieval import RAGRetrievalService
from infrastructure.llm.loader import loadLLM, getChatHistory
from langchain_core.runnables import RunnableWithMessageHistory
from langchain_core.prompts import ChatPromptTemplate
from domain.models.vector import VectorCollections
from core.log.logger import logger
from datetime import datetime, timezone


class ConversationAgent:
    """
    Base class for conversational agents in each interview stage.
    Each agent handles RAG retrieval, LLM generation, and state transitions.
    """

    def __init__(
        self,
        stage: InterviewProcessStep,
        node_name: InterviewProcessNode,
        rag_service: RAGRetrievalService,
        llm,
        prompt_template: ChatPromptTemplate
    ):
        self.stage = stage
        self.node_name = node_name
        self.rag_service = rag_service
        self.llm = llm
        self.prompt_template = prompt_template

    async def process(self, state: InterviewState) -> InterviewState:
        """
        Main processing logic for the conversation agent.

        Flow:
        1. Retrieve context using RAG (if needed)
        2. Generate response using LLM
        3. Decide whether to stay or transition
        4. Update state
        """
        try:
            logger.info(f"[AGENT:{self.node_name.value}] Processing state for session {state.session_id}")

            # Step 1: Retrieve context using RAG if transitioning to new state
            if state.go_to_next_step:
                context = await self._retrieve_context(state)
            else:
                context = state.context_prompt

            # Step 2: Generate response using LLM
            response = await self._generate_response(state, context)

            # Step 3: Determine next state
            next_state = self._determine_next_state(state, response)

            # Step 4: Update and return state
            return self._update_state(state, response, context, next_state)

        except Exception as e:
            logger.error(f"[AGENT:{self.node_name.value}] Error: {str(e)}", exc_info=True)
            return state.model_copy(update={
                "error_message": f"Agent {self.node_name.value} failed: {str(e)}",
                "current_step": InterviewProcessStep.ERROR_HANDLER
            })

    async def _retrieve_context(self, state: InterviewState) -> str:
        """Retrieve relevant context using RAG."""
        try:
            rag_result = await self.rag_service.retrieve_context_for_stage(
                session_id=state.session_id,
                current_step=self.stage,
                position=state.position,
                k=5
            )
            context = rag_result.get("context", "")
            logger.info(f"[AGENT:{self.node_name.value}] Retrieved {rag_result.get('num_chunks', 0)} chunks")
            return context
        except Exception as e:
            logger.error(f"[AGENT:{self.node_name.value}] RAG retrieval failed: {str(e)}")
            return ""

    async def _generate_response(self, state: InterviewState, context: str) -> ProcessPromptResponse:
        """Generate response using LLM with chat history."""
        try:
            # Prepare prompt input
            prompt_input = {
                "input": state.user_input.strip() or "Continue the conversation",
                "resume_info": context,
            }

            # Create runnable with chat history
            runnable_struct = self.prompt_template | self.llm.with_structured_output(ProcessPromptResponse)

            def get_session_history(config):
                session_id = config.get("configurable", {}).get("session_id", state.session_id)
                return getChatHistory(session_id)

            chain = RunnableWithMessageHistory(
                runnable=runnable_struct,
                get_session_history=get_session_history,
                input_messages_key="input",
                history_messages_key="history",
                output_messages_key="output",
            )

            # Invoke LLM
            result = chain.invoke(
                prompt_input,
                config={"configurable": {"session_id": state.session_id}},
            )

            return ProcessPromptResponse(**result) if isinstance(result, dict) else result

        except Exception as e:
            logger.error(f"[AGENT:{self.node_name.value}] LLM generation failed: {str(e)}")
            return ProcessPromptResponse(
                message=f"I'm sorry, I encountered an error. Can we try again?",
                go_to_next_step=False
            )

    def _determine_next_state(self, state: InterviewState, response: ProcessPromptResponse) -> InterviewProcessStep:
        """Determine the next state based on response."""
        if not response.go_to_next_step:
            # Stay in current state for more conversation
            return self.stage

        # Transition to next stage
        return self._get_next_stage(state)

    def _get_next_stage(self, state: InterviewState) -> InterviewProcessStep:
        """Get the next enabled stage based on selected_stages."""
        # Define stage flow order
        stage_flow = [
            InterviewProcessStep.GREETING,
            InterviewProcessStep.INTRO,
            InterviewProcessStep.ASK_EXPERIENCE,
            InterviewProcessStep.ASK_PROJECT,
            InterviewProcessStep.TECHNICAL_QUESTION,
            InterviewProcessStep.BEHAVIORAL_QUESTION,
            InterviewProcessStep.WRAP_UP,
            InterviewProcessStep.COMPLETED,
        ]

        # Mandatory stages
        mandatory_stages = {
            InterviewProcessStep.GREETING,
            InterviewProcessStep.INTRO,
            InterviewProcessStep.WRAP_UP,
        }

        # Map stage names to steps
        stage_name_map = {
            "Experience": InterviewProcessStep.ASK_EXPERIENCE,
            "Project": InterviewProcessStep.ASK_PROJECT,
            "Technical": InterviewProcessStep.TECHNICAL_QUESTION,
            "Behavioral": InterviewProcessStep.BEHAVIORAL_QUESTION,
        }

        # Find current index
        try:
            current_index = stage_flow.index(self.stage)
        except ValueError:
            return InterviewProcessStep.ERROR_HANDLER

        # Find next enabled stage
        for i in range(current_index + 1, len(stage_flow)):
            next_stage = stage_flow[i]

            # Check if stage is enabled
            if next_stage in mandatory_stages:
                return next_stage

            # Check if stage is in selected_stages
            for stage_name, stage_step in stage_name_map.items():
                if stage_step == next_stage and stage_name in state.selected_stages:
                    return next_stage

        # No more stages, go to completion
        return InterviewProcessStep.COMPLETED

    def _update_state(
        self,
        state: InterviewState,
        response: ProcessPromptResponse,
        context: str,
        next_state: InterviewProcessStep
    ) -> InterviewState:
        """Update state with response and transition info."""
        now = datetime.now(timezone.utc).isoformat()

        return state.model_copy(update={
            "message": response.message,
            "context_prompt": context,
            "current_storing_node": self.node_name,
            "current_step": next_state,
            "go_to_next_step": response.go_to_next_step,
            "end_at": now,
        })


class ConversationStateMachine:
    """
    Main state machine orchestrator for the interview conversation.

    Architecture:
    - Each interview stage is a conversational agent
    - Agents handle RAG + LLM + Decision making
    - State transitions are handled automatically
    - Supports multi-turn conversations in each state
    """

    def __init__(self):
        self.llm = loadLLM("interview")
        self.rag_service = RAGRetrievalService(collection_name=VectorCollections.RESUMES)

        # Initialize conversation agents for each stage
        self.agents = self._create_agents()

        # Build the state machine graph
        self.graph = self._build_graph()

    def _create_agents(self) -> Dict[InterviewProcessStep, ConversationAgent]:
        """Create conversation agents for each interview stage."""
        from services.prompts.conversation_prompts import (
            GREETING_CONVERSATION_PROMPT,
            INTRO_CONVERSATION_PROMPT,
            EXPERIENCE_CONVERSATION_PROMPT,
            PROJECT_CONVERSATION_PROMPT,
            TECHNICAL_CONVERSATION_PROMPT,
            BEHAVIORAL_CONVERSATION_PROMPT,
            WRAP_UP_CONVERSATION_PROMPT,
        )

        agents = {
            InterviewProcessStep.GREETING: ConversationAgent(
                stage=InterviewProcessStep.GREETING,
                node_name=InterviewProcessNode.GREETING,
                rag_service=self.rag_service,
                llm=self.llm,
                prompt_template=GREETING_CONVERSATION_PROMPT,
            ),
            InterviewProcessStep.INTRO: ConversationAgent(
                stage=InterviewProcessStep.INTRO,
                node_name=InterviewProcessNode.INTRO,
                rag_service=self.rag_service,
                llm=self.llm,
                prompt_template=INTRO_CONVERSATION_PROMPT,
            ),
            InterviewProcessStep.ASK_EXPERIENCE: ConversationAgent(
                stage=InterviewProcessStep.ASK_EXPERIENCE,
                node_name=InterviewProcessNode.ASK_EXPERIENCE,
                rag_service=self.rag_service,
                llm=self.llm,
                prompt_template=EXPERIENCE_CONVERSATION_PROMPT,
            ),
            InterviewProcessStep.ASK_PROJECT: ConversationAgent(
                stage=InterviewProcessStep.ASK_PROJECT,
                node_name=InterviewProcessNode.ASK_PROJECT,
                rag_service=self.rag_service,
                llm=self.llm,
                prompt_template=PROJECT_CONVERSATION_PROMPT,
            ),
            InterviewProcessStep.TECHNICAL_QUESTION: ConversationAgent(
                stage=InterviewProcessStep.TECHNICAL_QUESTION,
                node_name=InterviewProcessNode.TECHNICAL_QUESTION,
                rag_service=self.rag_service,
                llm=self.llm,
                prompt_template=TECHNICAL_CONVERSATION_PROMPT,
            ),
            InterviewProcessStep.BEHAVIORAL_QUESTION: ConversationAgent(
                stage=InterviewProcessStep.BEHAVIORAL_QUESTION,
                node_name=InterviewProcessNode.BEHAVIORAL_QUESTION,
                rag_service=self.rag_service,
                llm=self.llm,
                prompt_template=BEHAVIORAL_CONVERSATION_PROMPT,
            ),
            InterviewProcessStep.WRAP_UP: ConversationAgent(
                stage=InterviewProcessStep.WRAP_UP,
                node_name=InterviewProcessNode.WRAP_UP,
                rag_service=self.rag_service,
                llm=self.llm,
                prompt_template=WRAP_UP_CONVERSATION_PROMPT,
            ),
        }

        return agents

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state machine."""
        workflow = StateGraph(InterviewState)

        # Add nodes for each stage
        workflow.add_node("router", self._router_node)
        workflow.add_node(InterviewProcessNode.GREETING.value, self._greeting_node)
        workflow.add_node(InterviewProcessNode.INTRO.value, self._intro_node)
        workflow.add_node(InterviewProcessNode.ASK_EXPERIENCE.value, self._experience_node)
        workflow.add_node(InterviewProcessNode.ASK_PROJECT.value, self._project_node)
        workflow.add_node(InterviewProcessNode.TECHNICAL_QUESTION.value, self._technical_node)
        workflow.add_node(InterviewProcessNode.BEHAVIORAL_QUESTION.value, self._behavioral_node)
        workflow.add_node(InterviewProcessNode.WRAP_UP.value, self._wrap_up_node)
        workflow.add_node(InterviewProcessNode.COMPLETED.value, self._completed_node)
        workflow.add_node(InterviewProcessNode.ERROR_HANDLER.value, self._error_node)

        # Set entry point
        workflow.set_entry_point("router")

        # Add conditional routing from router
        workflow.add_conditional_edges(
            "router",
            self._route_to_stage,
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
            }
        )

        # All stage nodes end the graph (wait for next user input)
        for node in [
            InterviewProcessNode.GREETING.value,
            InterviewProcessNode.INTRO.value,
            InterviewProcessNode.ASK_EXPERIENCE.value,
            InterviewProcessNode.ASK_PROJECT.value,
            InterviewProcessNode.TECHNICAL_QUESTION.value,
            InterviewProcessNode.BEHAVIORAL_QUESTION.value,
            InterviewProcessNode.WRAP_UP.value,
        ]:
            workflow.add_edge(node, END)

        # Terminal nodes
        workflow.add_edge(InterviewProcessNode.COMPLETED.value, END)
        workflow.add_edge(InterviewProcessNode.ERROR_HANDLER.value, END)

        return workflow.compile()

    # Router node
    def _router_node(self, state: InterviewState) -> InterviewState:
        """Router node that directs to appropriate stage."""
        return state

    def _route_to_stage(self, state: InterviewState) -> InterviewProcessStep:
        """Routing logic based on current_step."""
        return state.current_step

    # Stage handler nodes
    async def _greeting_node(self, state: InterviewState) -> InterviewState:
        return await self.agents[InterviewProcessStep.GREETING].process(state)

    async def _intro_node(self, state: InterviewState) -> InterviewState:
        return await self.agents[InterviewProcessStep.INTRO].process(state)

    async def _experience_node(self, state: InterviewState) -> InterviewState:
        return await self.agents[InterviewProcessStep.ASK_EXPERIENCE].process(state)

    async def _project_node(self, state: InterviewState) -> InterviewState:
        return await self.agents[InterviewProcessStep.ASK_PROJECT].process(state)

    async def _technical_node(self, state: InterviewState) -> InterviewState:
        return await self.agents[InterviewProcessStep.TECHNICAL_QUESTION].process(state)

    async def _behavioral_node(self, state: InterviewState) -> InterviewState:
        return await self.agents[InterviewProcessStep.BEHAVIORAL_QUESTION].process(state)

    async def _wrap_up_node(self, state: InterviewState) -> InterviewState:
        return await self.agents[InterviewProcessStep.WRAP_UP].process(state)

    def _completed_node(self, state: InterviewState) -> InterviewState:
        """Interview completed."""
        logger.info(f"[STATE_MACHINE] Interview completed for session {state.session_id}")
        return state.model_copy(update={
            "message": "Thank you for completing the interview!",
            "current_step": InterviewProcessStep.COMPLETED,
        })

    def _error_node(self, state: InterviewState) -> InterviewState:
        """Error handler."""
        logger.error(f"[STATE_MACHINE] Error state reached: {state.error_message}")
        return state.model_copy(update={
            "message": "I apologize, but an error occurred. Please try again.",
            "current_step": InterviewProcessStep.ERROR_HANDLER,
        })

    async def invoke(self, state: InterviewState) -> InterviewState:
        """
        Invoke the state machine with current state.

        This is the main entry point for processing a user message.
        """
        try:
            result = await self.graph.ainvoke(state)
            return InterviewState(**result) if isinstance(result, dict) else result
        except Exception as e:
            logger.error(f"[STATE_MACHINE] Invocation error: {str(e)}", exc_info=True)
            return state.model_copy(update={
                "error_message": str(e),
                "current_step": InterviewProcessStep.ERROR_HANDLER,
            })
