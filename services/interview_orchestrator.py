"""
Interview Orchestrator

This is the main entry point for the interview system.
It handles:
1. Session management
2. State persistence
3. Delegation to the conversation state machine
4. Error handling and recovery

This replaces the old interview_graph.py with a cleaner architecture.
"""

from domain.models.interview import InterviewState, InterviewProcessStep, InterviewProcessNode
from services.conversation_state_machine import ConversationStateMachine
from infrastructure.llm.state_store import acquire_lock, load_state, save_state, release_lock, clear_state
from core.log.logger import logger
from datetime import datetime, timezone


class InterviewOrchestrator:
    """
    Main orchestrator for interview sessions.

    Responsibilities:
    - Manage interview sessions and state
    - Coordinate with conversation state machine
    - Handle errors and edge cases
    - Persist state between user messages
    """

    def __init__(self):
        self.state_machine = ConversationStateMachine()

    async def process_message(
        self,
        session_id: str,
        user_input: str,
        position: str = "",
        selected_stages: list[str] = None
    ) -> InterviewState:
        """
        Process a user message in the interview.

        This is the main entry point for each user interaction.

        Args:
            session_id: Unique session identifier
            user_input: User's message/response
            position: Job position (used for first message)
            selected_stages: Interview stages to include (used for first message)

        Returns:
            Updated interview state with AI response
        """
        if selected_stages is None:
            selected_stages = []

        # Acquire lock for session (prevent concurrent modifications)
        locked = acquire_lock(session_id)

        try:
            # Load or initialize state
            state = self._load_or_initialize_state(
                session_id=session_id,
                user_input=user_input,
                position=position,
                selected_stages=selected_stages
            )

            logger.info(
                f"[ORCHESTRATOR] Processing message for session {session_id}, "
                f"stage: {state.current_step.name}"
            )

            # Process through state machine
            result = await self.state_machine.invoke(state)

            # Handle completion or errors
            if result.current_step == InterviewProcessStep.COMPLETED:
                logger.info(f"[ORCHESTRATOR] Interview completed for session {session_id}")
                clear_state(session_id)
                return result

            if result.current_step == InterviewProcessStep.ERROR_HANDLER:
                logger.error(f"[ORCHESTRATOR] Error in session {session_id}: {result.error_message}")
                clear_state(session_id)
                return result

            # Save state for next turn
            save_state(session_id, result)

            return result

        except Exception as e:
            logger.error(
                f"[ORCHESTRATOR] Critical error in session {session_id}: {str(e)}",
                exc_info=True
            )

            # Create error state
            error_state = InterviewState(
                session_id=session_id,
                user_input=user_input,
                context_prompt="",
                message=f"I apologize, but I encountered an error: {str(e)}. Please try again.",
                position=position,
                example_questions=[],
                current_storing_node=InterviewProcessNode.ERROR_HANDLER,
                start_at=datetime.now(timezone.utc).isoformat(),
                end_at=datetime.now(timezone.utc).isoformat(),
                go_to_next_step=False,
                error_message=str(e),
                current_step=InterviewProcessStep.ERROR_HANDLER,
                selected_stages=selected_stages,
            )

            save_state(session_id, error_state)
            return error_state

        finally:
            if locked:
                release_lock(session_id)

    def _load_or_initialize_state(
        self,
        session_id: str,
        user_input: str,
        position: str,
        selected_stages: list[str]
    ) -> InterviewState:
        """
        Load existing state or create a new one for first message.
        """
        # Try to load existing state
        prev_state = load_state(session_id)

        if prev_state:
            # Existing conversation - update with new user input
            logger.info(f"[ORCHESTRATOR] Loaded existing state for session {session_id}")
            return prev_state.model_copy(update={
                "user_input": user_input,
                "message": "",  # Clear previous message
                "error_message": "",  # Clear any errors
            })

        # New conversation - initialize
        logger.info(f"[ORCHESTRATOR] Creating new session {session_id}")
        return InterviewState(
            session_id=session_id,
            user_input=user_input,
            context_prompt="",
            message="",
            position=position,
            example_questions=[],
            current_storing_node=InterviewProcessNode.GREETING,
            start_at=datetime.now(timezone.utc).isoformat(),
            end_at=datetime.now(timezone.utc).isoformat(),
            go_to_next_step=True,  # First message should trigger state processing
            error_message="",
            current_step=InterviewProcessStep.GREETING,
            selected_stages=selected_stages,
        )

    async def get_session_state(self, session_id: str) -> InterviewState:
        """
        Get the current state of a session without processing.
        """
        state = load_state(session_id)
        if not state:
            raise ValueError(f"Session {session_id} not found")
        return state

    def reset_session(self, session_id: str) -> None:
        """
        Reset/clear a session (for testing or restart).
        """
        logger.info(f"[ORCHESTRATOR] Resetting session {session_id}")
        clear_state(session_id)

    def get_active_stage(self, session_id: str) -> str:
        """
        Get the current active stage name for a session.
        """
        state = load_state(session_id)
        if not state:
            return "Not Started"

        return state.current_step.name
