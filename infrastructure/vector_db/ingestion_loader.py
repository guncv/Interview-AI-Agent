from __future__ import annotations
import tempfile
import os
import json
from llama_index.readers.file import PDFReader
from llama_index.core.node_parser import SentenceSplitter
from infrastructure.vector_db.embedder import create_embedder
from infrastructure.vector_db.factory import get_vector_store
from core.log.logger import logger


def _detect_chunk_type(text: str) -> str:
    """
    Detect the type/category of a resume chunk based on keywords.
    This helps with better RAG retrieval filtering.
    """
    text_lower = text.lower()

    # Keywords for different sections
    experience_keywords = ['experience', 'work', 'employment', 'job', 'position', 'role', 'company', 'worked at']
    project_keywords = ['project', 'built', 'developed', 'created', 'implemented', 'designed', 'github', 'portfolio']
    education_keywords = ['education', 'university', 'college', 'degree', 'bachelor', 'master', 'phd', 'graduated']
    skill_keywords = ['skills', 'technologies', 'programming', 'languages', 'frameworks', 'tools', 'proficient']
    achievement_keywords = ['achievement', 'award', 'recognition', 'certification', 'honor', 'accomplishment']

    # Count keyword matches
    scores = {
        'experience': sum(1 for kw in experience_keywords if kw in text_lower),
        'project': sum(1 for kw in project_keywords if kw in text_lower),
        'education': sum(1 for kw in education_keywords if kw in text_lower),
        'skill': sum(1 for kw in skill_keywords if kw in text_lower),
        'achievement': sum(1 for kw in achievement_keywords if kw in text_lower),
    }

    # Return type with highest score, or 'general' if no clear match
    max_score = max(scores.values())
    if max_score == 0:
        return 'general'

    return max(scores, key=scores.get)


def ingest_document_from_bytes(
    collection_name: str,
    file_bytes: bytes,
    session_id: str,
    file_extension: str = ".pdf",
):
    """
    Ingest a document (PDF) into vector database with improved chunking and metadata.

    Improvements:
    - Semantic chunking with sentence splitting
    - Rich metadata (chunk_type, position, length)
    - Better logging and error handling
    """
    # Load PDF
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_file_path = os.path.join(tmp_dir, f"document{file_extension}")
        with open(tmp_file_path, 'wb') as tmp_file:
            tmp_file.write(file_bytes)

        reader = PDFReader()
        documents = reader.load_data(file=tmp_file_path)

    logger.info(f"[INGESTION] Loaded {len(documents)} pages from PDF for session {session_id}")

    # Use semantic chunking with overlap for better context preservation
    node_parser = SentenceSplitter(
        chunk_size=512,  # Optimal for embeddings
        chunk_overlap=50,  # Overlap to preserve context
        paragraph_separator="\n\n",
        secondary_chunking_regex="[^,.;。]+[,.;。]?"
    )

    nodes = node_parser.get_nodes_from_documents(documents)
    logger.info(f"[INGESTION] Created {len(nodes)} chunks for session {session_id}")

    vector_store = get_vector_store(collection_name=collection_name)
    embedder = create_embedder()

    # Batch process nodes for efficiency
    for idx, node in enumerate(nodes):
        chunk_id = f"{session_id}_chunk_{idx}"
        text = node.get_content()

        # Skip empty or too-short chunks
        if not text or len(text.strip()) < 10:
            logger.warning(f"[INGESTION] Skipping empty/short chunk {idx}")
            continue

        # Detect chunk type for better retrieval
        chunk_type = _detect_chunk_type(text)

        # Rich metadata for better filtering and retrieval
        chunk_metadata = {
            "session_id": session_id,
            "chunk_index": idx,
            "chunk_type": chunk_type,  # experience, project, education, skill, etc.
            "chunk_length": len(text),
            "total_chunks": len(nodes),
            "position_ratio": round(idx / len(nodes), 2),  # 0.0 to 1.0 (top to bottom of resume)
        }

        # Logging
        node_info = {
            "chunk_id": chunk_id,
            "chunk_index": f"{idx + 1}/{len(nodes)}",
            "chunk_type": chunk_type,
            "text_length": len(text),
            "text_preview": text[:100].replace("\n", " ") + "..." if len(text) > 100 else text,
        }

        if (idx + 1) % 5 == 0 or (idx + 1) == len(nodes):
            logger.info(f"[INGESTION] Processing chunk {idx + 1}/{len(nodes)}")

        logger.debug(f"[INGESTION] Chunk details:\n{json.dumps(node_info, indent=2, ensure_ascii=False)}")

        try:
            # Generate embedding
            embedding = embedder([text])

            # Store in vector database
            vector_store.add(
                ids=[chunk_id],
                documents=[text],
                metadatas=[chunk_metadata],
                embeddings=embedding
            )
        except Exception as e:
            logger.error(f"[INGESTION] Failed to process chunk {idx}: {str(e)}")
            continue

    logger.info(f"[INGESTION] Successfully ingested {len(nodes)} chunks for session {session_id}")
    