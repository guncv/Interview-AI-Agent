from langchain_text_splitters import RecursiveCharacterTextSplitter
from internal.adapters.vector_db.embedder import create_embedder
from internal.adapters.vector_db.factory import get_vector_store
from internal.adapters.log.logger import logger
from typing import Optional
from langchain_community.document_loaders import PyMuPDFLoader
import tempfile

def ingest_document(
    uploaded_pdf_bytes: bytes,
    doc_id: str,
    metadata: Optional[dict] = {},
    chunk_size: int = 300,
    chunk_overlap: int = 50,
) -> None:
    logger.info(f"[INGEST_DOCUMENT] Ingesting document for session {doc_id}")

    with tempfile.NamedTemporaryFile(delete=True, suffix=".pdf") as tmp_file:
        tmp_file.write(uploaded_pdf_bytes)
        tmp_file.flush()

        loader = PyMuPDFLoader(file_path=tmp_file.name)
        documents = loader.load()

    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = splitter.split_documents(documents)
    logger.info(f"chunks : {chunks}")

    texts = [chunk.page_content for chunk in chunks]
    logger.info(f"texts : {texts}")
    embeddings = create_embedder()(texts)
    logger.info(f"embeddings : {embeddings}")
    
    vector_store = get_vector_store()
    vector_store.add(
        ids=[f"{doc_id}_{i}" for i in range(len(texts))],
        documents=texts,
        metadatas = [{"source": "resume", "chunk_index": i} for i in range(len(texts))],
        embeddings=embeddings
    )
