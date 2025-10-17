# RAG-Based Interview Architecture

## Overview

This document describes the **Retrieval-Augmented Generation (RAG)** architecture used in the interview AI agent system. The new architecture replaces the previous hardcoded section mapping approach with intelligent semantic search, enabling more context-aware and personalized interview questions.

## Problem Statement

### Previous Architecture Issues

1. **No Real RAG**: The system claimed to use RAG but actually just retrieved pre-extracted resume JSON from Redis/Postgres using hardcoded section mappings
2. **Vector DB Unused**: Vector database infrastructure existed but was never used for retrieval
3. **Inefficient**: Generated 20-25 questions for every state change using the entire resume context
4. **LangGraph as Prompt Switcher**: LangGraph only switched between different prompts based on state, without real intelligence

### Example of Old Approach

```python
# Old hardcoded mapping
resume_section_map = {
    InterviewProcessStep.ASK_EXPERIENCE: ["experience"],
    InterviewProcessStep.ASK_PROJECT: ["project"],
    # ... etc
}

# Just retrieved pre-extracted JSON
resume_context = await get_resume_context(session_id)
context = resume_context[section_name]  # No semantic search!
```

## New RAG Architecture

### Core Components

#### 1. RAG Retrieval Service (`services/rag_retrieval.py`)

Performs semantic search on vector database to retrieve relevant resume chunks based on interview stage.

**Key Features:**
- Stage-specific query templates for targeted retrieval
- Semantic search using embeddings
- Relevance scoring and ranking
- Support for custom queries

**Query Templates by Stage:**

```python
query_templates = {
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
    # ... etc
}
```

**Usage:**

```python
rag_service = RAGRetrievalService(collection_name=VectorCollections.RESUMES)

# Retrieve context for a specific stage
result = await rag_service.retrieve_context_for_stage(
    session_id="session_123",
    current_step=InterviewProcessStep.ASK_EXPERIENCE,
    position="Senior Software Engineer",
    k=5  # Top 5 most relevant chunks
)

context = result["context"]  # Retrieved text
chunks = result["chunks"]    # Individual chunks with scores
```

#### 2. Updated Interview Graph (`services/interview_graph.py`)

The `_query_vector_db_node` now actually queries the vector database:

```python
async def _query_vector_db_node(self, state: InterviewState):
    # Use RAG to retrieve relevant context
    rag_result = await self.rag_service.retrieve_context_for_stage(
        session_id=state.session_id,
        current_step=state.current_step,
        position=state.position,
        k=5
    )

    context_text = rag_result.get("context", "")

    return state.model_copy(update={
        "context_prompt": context_text,
    })
```

#### 3. Optimized Question Generation (`services/prompts/example_question_prompt.py`)

Generates **8-12 focused questions** (down from 20-25) based on retrieved context:

**Key Changes:**
- Questions are based on semantically retrieved context, not entire resume
- Reduced number of questions (more focused, less repetitive)
- Explicit instruction to use retrieved context
- Better prompt structure for RAG workflow

### Architecture Flow

```
┌─────────────────────────────────────────────────────────────┐
│                     Interview Request                        │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              Interview Graph (LangGraph)                     │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  1. QUERY_VECTOR_DB Node                               │ │
│  │     - Identifies current interview stage               │ │
│  │     - Calls RAG Retrieval Service                      │ │
│  │     - Performs semantic search                         │ │
│  │     - Retrieves top K relevant chunks                  │ │
│  └────────────────┬───────────────────────────────────────┘ │
│                   │                                          │
│                   ▼                                          │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  2. GET_EXAMPLE_QUESTION Node                          │ │
│  │     - Receives retrieved context from RAG              │ │
│  │     - Generates 8-12 focused questions                 │ │
│  │     - Uses LLM with optimized prompt                   │ │
│  └────────────────┬───────────────────────────────────────┘ │
│                   │                                          │
│                   ▼                                          │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  3. PROCESS_ANSWER Node                                │ │
│  │     - Processes candidate's answer                     │ │
│  │     - Manages interview state transitions              │ │
│  └────────────────┬───────────────────────────────────────┘ │
│                   │                                          │
│                   ▼                                          │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  4. STORE_ANSWER Node                                  │ │
│  │     - Stores conversation history                      │ │
│  │     - Prepares for next stage                          │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Resume PDF
    │
    ├─> PDF Parsing (PyMuPDF/LlamaIndex)
    │
    ├─> Hierarchical Chunking (500/1000/2000 tokens)
    │
    ├─> Embedding Generation (text-embedding-3-small)
    │
    ├─> Vector DB Storage (ChromaDB/Pinecone)
    │       with metadata: {session_id, chunk_id}
    │
    └─> Resume Context Extraction (LLM)
            stored in Redis/Postgres for fallback
```

```
Interview Stage Change
    │
    ├─> RAG Service
    │       │
    │       ├─> Select query templates for stage
    │       │
    │       ├─> Semantic Search (query_by_text)
    │       │       - Filters by session_id
    │       │       - Returns top K chunks
    │       │       - Scores by relevance
    │       │
    │       └─> Format context with relevance scores
    │
    ├─> Question Generation (LLM)
    │       - Input: Retrieved context
    │       - Output: 8-12 focused questions
    │
    └─> Interview Prompt Selection
            - Uses generated questions in prompt
```

## Key Improvements

### 1. Semantic Search Instead of Hardcoded Mapping

**Before:**
```python
# Hardcoded section extraction
if stage == "experience":
    context = resume_json["experience"]
```

**After:**
```python
# Intelligent semantic search
context = await rag_service.retrieve_context_for_stage(
    session_id=session_id,
    current_step=InterviewProcessStep.ASK_EXPERIENCE,
    k=5
)
```

### 2. Focused Question Generation

**Before:**
- Generated 20-25 questions using entire resume
- Repetitive and broad
- Not stage-specific enough

**After:**
- Generates 8-12 questions using retrieved context
- Highly specific to retrieved chunks
- Directly tied to semantic search results

### 3. Better LangGraph Usage

**Before:**
- Just switched prompts based on state
- No real coordination between nodes

**After:**
- RAG retrieval in dedicated node
- Context flows through state
- Proper separation of concerns:
  - Node 1: Retrieve context (RAG)
  - Node 2: Generate questions (LLM)
  - Node 3: Process answers (Logic)
  - Node 4: Store results (Persistence)

### 4. Scalability

**Before:**
- Entire resume context passed to LLM every time
- High token usage
- Slow for large resumes

**After:**
- Only relevant chunks retrieved
- Reduced token usage (focused context)
- Faster and more cost-effective

## Configuration

### Vector Store

Configured in `core/config/config.dev.yaml`:

```yaml
vector_db:
  kind: chroma  # or pinecone
  persist_directory: ./.chroma
```

### Collection Name

Defined in `domain/models/vector.py`:

```python
class VectorCollections:
    RESUMES = "resume"
```

### Embedding Model

Configured in `infrastructure/vector_db/embedder.py`:

```python
OpenAIEmbedder(model="text-embedding-3-small")
```

## API Endpoints

### Ingestion Endpoint

```
POST /api/ingestion/ingest
Content-Type: multipart/form-data

Fields:
  - session_id: string (required)
  - file: PDF file (required)
```

Ingests resume PDF into vector database with hierarchical chunking.

### Interview Endpoint

```
POST /api/interview
Content-Type: application/json

Body:
{
  "session_id": "session_123",
  "user_input": "Tell me about your experience",
  "position": "Senior Software Engineer",
  "selected_stages": ["Experience", "Project", "Technical"]
}
```

Conducts interview using RAG-based context retrieval.

## Monitoring and Debugging

### Log Messages

RAG operations are logged with `[RAG]` prefix:

```python
logger.info(f"[RAG] Retrieving context for stage: {stage}, session: {session_id}")
logger.info(f"[RAG] Retrieved {num_chunks} chunks")
logger.warning(f"[RAG] No relevant data found")
logger.error(f"[RAG] Error during retrieval: {error}")
```

### Debugging Tips

1. **Check vector DB ingestion:**
   ```python
   vector_store = get_vector_store(collection_name="resume")
   count = vector_store.count()
   logger.info(f"Total documents: {count}")
   ```

2. **Test RAG retrieval:**
   ```python
   result = await rag_service.retrieve_context_for_stage(
       session_id="test_session",
       current_step=InterviewProcessStep.ASK_EXPERIENCE,
       k=5
   )
   print(result["context"])
   print(f"Retrieved {len(result['chunks'])} chunks")
   ```

3. **Inspect retrieved chunks:**
   ```python
   for chunk in result["chunks"]:
       print(f"Score: {chunk['score']}")
       print(f"Text: {chunk['text'][:200]}...")
   ```

## Best Practices

1. **Resume Ingestion:**
   - Ingest resume before starting interview
   - Use consistent session_id across ingestion and interview
   - Verify ingestion success before proceeding

2. **Query Templates:**
   - Keep templates focused and specific
   - Use multiple templates per stage for diversity
   - Test templates with actual resumes

3. **Chunk Size:**
   - Default: 500/1000/2000 tokens (hierarchical)
   - Adjust based on resume complexity
   - Balance between context and specificity

4. **Number of Chunks (k):**
   - Default: k=5 per query template
   - Increase for more context, decrease for focus
   - Monitor relevance scores to tune

5. **Question Generation:**
   - Use retrieved context explicitly in prompt
   - Maintain 8-12 question limit
   - Ensure questions reference specific chunks

## Future Enhancements

1. **Hybrid Search:**
   - Combine semantic search with keyword matching
   - Boost specific sections (e.g., recent experience)

2. **Re-ranking:**
   - Add cross-encoder for better relevance scoring
   - Filter low-relevance chunks dynamically

3. **Dynamic Query Generation:**
   - Generate queries based on conversation history
   - Adapt to candidate responses

4. **Caching:**
   - Cache retrieved context per stage
   - Reduce redundant vector DB queries

5. **Answer-Aware Retrieval:**
   - Use candidate's answer to retrieve follow-up context
   - Enable deeper exploration of specific topics

## Troubleshooting

### Issue: No context retrieved

**Cause:** Vector DB empty or session_id mismatch

**Solution:**
```python
# Verify ingestion
vector_store = get_vector_store(collection_name="resume")
result = vector_store.query_by_text(
    text="experience",
    k=10,
    session_id=session_id
)
print(f"Found {len(result.items)} chunks")
```

### Issue: Generic questions generated

**Cause:** Retrieved context too broad or not specific

**Solution:**
- Increase k to retrieve more chunks
- Refine query templates
- Check embedding quality

### Issue: Slow retrieval

**Cause:** Large vector DB or inefficient queries

**Solution:**
- Add session_id filtering
- Reduce k parameter
- Consider vector DB optimization (e.g., HNSW index)

## References

- LangGraph Documentation: https://langchain-ai.github.io/langgraph/
- LlamaIndex RAG Guide: https://docs.llamaindex.ai/
- ChromaDB Documentation: https://docs.trychroma.com/
- OpenAI Embeddings: https://platform.openai.com/docs/guides/embeddings
