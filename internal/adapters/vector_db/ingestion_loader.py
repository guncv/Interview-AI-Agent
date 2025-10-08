from langchain_text_splitters import RecursiveCharacterTextSplitter
from internal.adapters.vector_db.embedder import create_embedder
from internal.adapters.vector_db.factory import get_vector_store
from internal.adapters.log.logger import logger
from langchain_community.document_loaders import PyMuPDFLoader
import tempfile

def ingest_document(
    collection_name: str,
    uploaded_pdf_bytes: bytes,
    doc_id: str,
    metadata: [dict],
    chunk_size: int = 300,
    chunk_overlap: int = 50,
) -> None:
    with tempfile.NamedTemporaryFile(delete=True, suffix=".pdf") as tmp_file:
        tmp_file.write(uploaded_pdf_bytes)
        tmp_file.flush()

        loader = PyMuPDFLoader(file_path=tmp_file.name)
        documents = loader.load()

    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = splitter.split_documents(documents)

    texts = [chunk.page_content for chunk in chunks]
    embeddings = create_embedder()(texts)
    
    vector_store = get_vector_store(collection_name=collection_name)
    vector_store.add(
        ids=[f"{doc_id}_{i}" for i in range(len(texts))],
        documents=texts,
        metadatas = [metadata for i in range(len(texts))],
        embeddings=embeddings
    )
