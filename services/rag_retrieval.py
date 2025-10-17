from typing import Dict, Any
from infrastructure.vector_db.factory import get_vector_store
from domain.models.interview import InterviewProcessStep
from domain.models.vector import VectorCollections
from core.log.logger import logger


class RAGRetrievalService:
    """
    Service for retrieving relevant resume context using semantic search (RAG).
    This replaces the hardcoded section mapping with intelligent retrieval.
    """

    def __init__(self, collection_name: str = VectorCollections.RESUMES):
        self.collection_name = collection_name
        self.vector_store = get_vector_store(collection_name=collection_name)

        # Query templates for semantic search by stage
        self.query_templates = {
            InterviewProcessStep.INTRO: [
                "professional background and career summary",
                "education and qualifications"
            ],
            InterviewProcessStep.ASK_EXPERIENCE: [
                "work experience and professional roles",
                "job responsibilities and achievements at companies",
                "technologies and tools used in work",
                "professional accomplishments and impact"
            ],
            InterviewProcessStep.ASK_PROJECT: [
                "personal projects and side projects",
                "academic projects and coursework",
                "open source contributions",
                "project technologies and implementation details"
            ],
            InterviewProcessStep.TECHNICAL_QUESTION: [
                "technical skills and expertise",
                "programming languages and frameworks",
                "system design and architecture experience",
                "technical challenges and problem solving"
            ],
            InterviewProcessStep.BEHAVIORAL_QUESTION: [
                "teamwork and collaboration experiences",
                "leadership and mentoring",
                "challenges faced and lessons learned",
                "conflict resolution and communication"
            ],
        }

        # Preferred chunk types for each stage (leverages new metadata)
        self.chunk_type_preferences = {
            InterviewProcessStep.INTRO: ['education', 'general'],
            InterviewProcessStep.ASK_EXPERIENCE: ['experience'],
            InterviewProcessStep.ASK_PROJECT: ['project'],
            InterviewProcessStep.TECHNICAL_QUESTION: ['skill', 'experience', 'project'],
            InterviewProcessStep.BEHAVIORAL_QUESTION: ['experience', 'achievement', 'project'],
        }

    async def retrieve_context_for_stage(
        self,
        session_id: str,
        current_step: InterviewProcessStep,
        position: str = "",
        k: int = 5
    ) -> Dict[str, Any]:
        """
        Retrieve relevant resume context for the current interview stage using RAG.

        Args:
            session_id: The interview session ID (used to filter to specific resume)
            current_step: Current interview stage
            position: Job position being interviewed for (optional, for context)
            k: Number of chunks to retrieve per query

        Returns:
            Dictionary containing retrieved context and metadata
        """

        # Stages that don't need RAG retrieval
        if current_step in [InterviewProcessStep.GREETING, InterviewProcessStep.ROUTER, InterviewProcessStep.WRAP_UP]:
            return {
                "context": "",
                "chunks": [],
                "stage": current_step.name
            }

        try:
            # Get query templates for this stage
            query_templates = self.query_templates.get(current_step, [])

            if not query_templates:
                logger.warning(f"[RAG] No query templates defined for stage: {current_step}")
                return {
                    "context": "",
                    "chunks": [],
                    "stage": current_step.name
                }

            # Perform semantic search for each query template
            all_chunks = []
            seen_ids = set()

            for query_template in query_templates:
                # Enhance query with position if provided
                query = f"{query_template} for {position} role" if position else query_template

                logger.info(f"[RAG] Querying vector DB with: {query} for session: {session_id}")

                # Query vector database
                result = self.vector_store.query_by_text(
                    text=query,
                    k=k,
                    include_documents=True,
                    session_id=session_id
                )

                # Collect unique chunks
                for item in result.items:
                    if item.id not in seen_ids:
                        seen_ids.add(item.id)
                        chunk_data = {
                            "id": item.id,
                            "text": item.document,
                            "score": item.score,
                            "metadata": item.metadata
                        }
                        all_chunks.append(chunk_data)

            # Boost scores for preferred chunk types
            preferred_types = self.chunk_type_preferences.get(current_step, [])
            for chunk in all_chunks:
                chunk_type = chunk["metadata"].get("chunk_type", "")
                if chunk_type in preferred_types:
                    # Boost score by 10% for preferred chunk types
                    chunk["score"] = chunk["score"] * 1.1

            # Sort by relevance score (descending)
            all_chunks.sort(key=lambda x: x.get("score", 0), reverse=True)

            # Take top k chunks overall
            top_chunks = all_chunks[:k * 2]  # Get more chunks for richer context

            # Format context text
            context_parts = []
            for i, chunk in enumerate(top_chunks, 1):
                context_parts.append(f"[Context {i}] (Relevance: {chunk['score']:.3f})\n{chunk['text']}")

            context_text = "\n\n".join(context_parts)

            logger.info(f"[RAG] Retrieved {len(top_chunks)} chunks for stage {current_step.name}")

            return {
                "context": context_text,
                "chunks": top_chunks,
                "stage": current_step.name,
                "num_chunks": len(top_chunks)
            }

        except Exception as e:
            logger.error(f"[RAG] Error retrieving context for session {session_id}: {str(e)}", exc_info=True)
            return {
                "context": "",
                "chunks": [],
                "stage": current_step.name,
                "error": str(e)
            }

    async def retrieve_for_specific_query(
        self,
        session_id: str,
        query: str,
        k: int = 5
    ) -> Dict[str, Any]:
        """
        Retrieve context for a specific custom query.
        Useful for follow-up questions or dynamic context retrieval.
        """
        try:
            logger.info(f"[RAG] Custom query: {query} for session: {session_id}")

            result = self.vector_store.query_by_text(
                text=query,
                k=k,
                include_documents=True,
                session_id=session_id
            )

            chunks = []
            for item in result.items:
                chunks.append({
                    "id": item.id,
                    "text": item.document,
                    "score": item.score,
                    "metadata": item.metadata
                })

            # Format context
            context_parts = [f"{chunk['text']}" for chunk in chunks]
            context_text = "\n\n".join(context_parts)

            return {
                "context": context_text,
                "chunks": chunks,
                "num_chunks": len(chunks)
            }

        except Exception as e:
            logger.error(f"[RAG] Error with custom query: {str(e)}", exc_info=True)
            return {
                "context": "",
                "chunks": [],
                "error": str(e)
            }