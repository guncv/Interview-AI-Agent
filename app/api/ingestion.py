from fastapi import APIRouter, UploadFile, File, Form
from core.utils.exception import InterviewSimulationException
from domain.enums.exception import InterviewSimulationErrorCodes
from core.log.logger import logger
from infrastructure.vector_db.ingestion_loader import ingest_document_from_bytes
from domain.models.vector import VectorCollections
from pydantic import BaseModel

router = APIRouter()

class IngestionResponse(BaseModel):
    success: bool

@router.post("/ingest", response_model=IngestionResponse)
async def ingest_file_api(
    session_id: str = Form(...),
    file: UploadFile = File(..., description="PDF file to ingest"),
):
    try:
        if not file.filename.lower().endswith('.pdf'):
            raise InterviewSimulationException(
                error_code=InterviewSimulationErrorCodes.INTERNAL_ERROR,
                description="Only PDF files are supported"
            )
        
        collection_name = VectorCollections.RESUMES
        
        file_bytes = await file.read()
        if len(file_bytes) == 0:
            raise InterviewSimulationException(
                error_code=InterviewSimulationErrorCodes.INTERNAL_ERROR,
                description="Uploaded file is empty"
            )
        
        ingest_document_from_bytes(
            collection_name=collection_name,
            file_bytes=file_bytes,
            session_id=session_id,
            file_extension=".pdf"
        )
        
        return IngestionResponse(
            success=True, 
        )
        
    except InterviewSimulationException as e:
        logger.error(f"[Ingestion API Error]: {e}")
        raise e
    except Exception as e:
        error = InterviewSimulationException(
            error_code=InterviewSimulationErrorCodes.INTERNAL_ERROR,
            description=f"[{type(e).__name__}]: {str(e)}"
        )
        logger.error(f"[Ingestion API Error]: {error}")
        raise error
