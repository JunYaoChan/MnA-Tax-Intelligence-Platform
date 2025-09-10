from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
import logging
import asyncio
from io import StringIO, BytesIO
import json
import PyPDF2
from docx import Document as DocxDocument

from services.document_processor import DocumentProcessor
from database.supabase_client import SupabaseVectorStore
from database.neo4j_client import Neo4jClient
from database.chat_repository import ChatRepository
from config.settings import Settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/upload", tags=["Document Upload"])

# Initialize services (will be dependency injected)
settings = Settings()
vector_store = SupabaseVectorStore(settings)
neo4j_client = Neo4jClient(settings)
document_processor = DocumentProcessor(settings, vector_store, neo4j_client)
chat_repo = ChatRepository(settings)

@router.post("/document")
async def upload_document(
    file: UploadFile = File(...),
    document_type: Optional[str] = Form(None),
    metadata: Optional[str] = Form(None),
    conversation_id: Optional[str] = Form(None),
    user_id: Optional[str] = Form(None)
):
    """
    Upload a single document to be processed and stored in vector and graph databases
    
    Args:
        file: The document file (PDF, DOCX, TXT)
        document_type: Type of document (regulation, case_law, precedent, expert_analysis, etc.)
        metadata: Optional JSON string with additional metadata
    """
    try:
        # Validate/normalize document type
        valid_types = ["regulation", "case_law", "precedent", "expert_analysis", "irs_guidance", "revenue_ruling"]
        if document_type:
            if document_type not in valid_types:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid document_type. Must be one of: {', '.join(valid_types)}"
                )
        else:
            document_type = "unknown"
        
        # Parse metadata if provided
        doc_metadata = {}
        if metadata:
            try:
                doc_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid metadata JSON format")
        
        # Extract text from file
        file_content = await _extract_text_from_file(file)
        
        if not file_content.strip():
            raise HTTPException(status_code=400, detail="Document appears to be empty or text could not be extracted")
        
        # Process the document
        result = await document_processor.process_document(
            file_content=file_content,
            filename=file.filename,
            document_type=document_type,
            metadata=doc_metadata
        )
        
        if result["success"]:
            response_content: Dict[str, Any] = {
                "message": "Document processed successfully",
                "document_id": result["document_id"],
                "chunks_processed": result["chunks_processed"],
                "vector_chunks_stored": result["vector_success"],
                "graph_entities_created": result["graph_success"],
                "metadata": result["metadata"]
            }

            # Optionally create a high-level document record and link to conversation
            try:
                if user_id:
                    import uuid as _uuid
                    doc_record_id = str(_uuid.uuid4())
                    # Persist to a 'documents' table for metadata/browsing
                    doc_meta = result.get("metadata") or {}
                    if not isinstance(doc_meta, dict):
                        doc_meta = {}
                    doc_meta = {**doc_meta, "processor_document_id": result.get("document_id")}
                    chat_repo.client.table("documents").insert({
                        "id": doc_record_id,
                        "user_id": user_id,
                        "filename": file.filename,
                        "metadata": doc_meta
                    }).execute()
                    response_content["document_record_id"] = doc_record_id

                    if conversation_id:
                        linked = chat_repo.link_document(conversation_id, doc_record_id)
                        response_content["linked_to_conversation"] = bool(linked)
                        response_content["conversation_id"] = conversation_id
            except Exception as link_err:
                logger.warning(f"Document record/linking failed: {link_err}")
                response_content["link_warning"] = str(link_err)

            return JSONResponse(status_code=200, content=response_content)
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process document: {result.get('error', 'Unknown error')}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in upload_document: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during document upload")

@router.post("/batch")
async def upload_documents_batch(
    files: List[UploadFile] = File(...),
    document_types: str = Form(...),  # JSON array of document types
    metadata: Optional[str] = Form(None)  # JSON object with metadata
):
    """
    Upload multiple documents in batch
    
    Args:
        files: List of document files
        document_types: JSON array of document types corresponding to each file
        metadata: Optional JSON object with metadata for all documents
    """
    try:
        # Parse document types
        try:
            types_list = json.loads(document_types)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid document_types JSON format")
        
        if len(files) != len(types_list):
            raise HTTPException(
                status_code=400, 
                detail="Number of files must match number of document types"
            )
        
        # Parse metadata
        batch_metadata = {}
        if metadata:
            try:
                batch_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid metadata JSON format")
        
        # Process each document
        documents_to_process = []
        
        for file, doc_type in zip(files, types_list):
            file_content = await _extract_text_from_file(file)
            if file_content.strip():  # Only process non-empty documents
                documents_to_process.append({
                    "content": file_content,
                    "filename": file.filename,
                    "document_type": doc_type,
                    "metadata": batch_metadata
                })
        
        if not documents_to_process:
            raise HTTPException(status_code=400, detail="No valid documents to process")
        
        # Process documents in batch
        batch_result = await document_processor.batch_process_documents(documents_to_process)
        
        return JSONResponse(
            status_code=200,
            content={
                "message": f"Batch processing completed",
                "total_files": len(files),
                "processed_successfully": batch_result["successful"],
                "failed": batch_result["failed"],
                "results": batch_result["results"]
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in upload_documents_batch: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during batch upload")

@router.post("/text")
async def upload_text_content(
    title: str = Form(...),
    content: str = Form(...),
    document_type: Optional[str] = Form(None),
    metadata: Optional[str] = Form(None),
    conversation_id: Optional[str] = Form(None),
    user_id: Optional[str] = Form(None)
):
    """
    Upload text content directly without file upload
    
    Args:
        title: Document title/filename
        content: The text content
        document_type: Type of document
        metadata: Optional JSON metadata
    """
    try:
        # Validate/normalize document type
        valid_types = ["regulation", "case_law", "precedent", "expert_analysis", "irs_guidance", "revenue_ruling"]
        if document_type:
            if document_type not in valid_types:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid document_type. Must be one of: {', '.join(valid_types)}"
                )
        else:
            document_type = "unknown"
        
        # Parse metadata
        doc_metadata = {}
        if metadata:
            try:
                doc_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid metadata JSON format")
        
        if not content.strip():
            raise HTTPException(status_code=400, detail="Content cannot be empty")
        
        # Process the document
        result = await document_processor.process_document(
            file_content=content,
            filename=title,
            document_type=document_type,
            metadata=doc_metadata
        )
        
        if result["success"]:
            response_content: Dict[str, Any] = {
                "message": "Text content processed successfully",
                "document_id": result["document_id"],
                "chunks_processed": result["chunks_processed"],
                "vector_chunks_stored": result["vector_success"],
                "graph_entities_created": result["graph_success"],
                "metadata": result["metadata"]
            }

            # Optionally create a high-level document record and link
            try:
                if user_id:
                    import uuid as _uuid
                    doc_record_id = str(_uuid.uuid4())
                    doc_meta = result.get("metadata") or {}
                    if not isinstance(doc_meta, dict):
                        doc_meta = {}
                    doc_meta = {**doc_meta, "processor_document_id": result.get("document_id")}
                    chat_repo.client.table("documents").insert({
                        "id": doc_record_id,
                        "user_id": user_id,
                        "filename": title,
                        "metadata": doc_meta
                    }).execute()
                    response_content["document_record_id"] = doc_record_id

                    if conversation_id:
                        linked = chat_repo.link_document(conversation_id, doc_record_id)
                        response_content["linked_to_conversation"] = bool(linked)
                        response_content["conversation_id"] = conversation_id
            except Exception as link_err:
                logger.warning(f"Text document record/linking failed: {link_err}")
                response_content["link_warning"] = str(link_err)

            return JSONResponse(status_code=200, content=response_content)
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process content: {result.get('error', 'Unknown error')}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in upload_text_content: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during text upload")

@router.get("/status/{document_id}")
async def get_upload_status(document_id: str):
    """
    Get the processing status of an uploaded document
    
    Args:
        document_id: The document ID returned from upload
    """
    try:
        # Query vector database to check if document exists
        # This is a simple check - in production you might want more detailed status tracking
        results = await vector_store.search(query="", top_k=1, filter={"metadata.document_id": document_id})
        
        if results:
            return JSONResponse(
                status_code=200,
                content={
                    "document_id": document_id,
                    "status": "completed",
                    "chunks_found": len(results),
                    "message": "Document processing completed successfully"
                }
            )
        else:
            return JSONResponse(
                status_code=404,
                content={
                    "document_id": document_id,
                    "status": "not_found",
                    "message": "Document not found or still processing"
                }
            )
    
    except Exception as e:
        logger.error(f"Error checking upload status: {e}")
        raise HTTPException(status_code=500, detail="Error checking document status")

async def _extract_text_from_file(file: UploadFile) -> str:
    """Extract text content from uploaded file based on file type"""
    try:
        file_extension = file.filename.lower().split('.')[-1] if '.' in file.filename else ''
        
        if file_extension == 'txt':
            content = await file.read()
            return content.decode('utf-8')
        
        elif file_extension == 'pdf':
            content = await file.read()
            pdf_file = BytesIO(content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text

        elif file_extension in ['docx']:
            content = await file.read()
            doc_file = BytesIO(content)
            try:
                doc = DocxDocument(doc_file)
                text = ""
                for paragraph in doc.paragraphs:
                    text += paragraph.text + "\n"
                return text
            except Exception as e:
                logger.warning(f"Could not parse DOCX file {file.filename}: {e}")
                return content.decode('utf-8', errors='ignore')
        
        else:
            # Default: try to read as text
            content = await file.read()
            return content.decode('utf-8', errors='ignore')
    
    except Exception as e:
        logger.error(f"Error extracting text from file {file.filename}: {e}")
        raise HTTPException(status_code=400, detail=f"Could not extract text from file: {str(e)}")
