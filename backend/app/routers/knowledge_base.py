"""
Knowledge Base API endpoints.
Handles file uploads, processing, and retrieval.
"""

import uuid
import logging
from typing import List
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks, Response
from fastapi.responses import JSONResponse
from app.deps import get_current_user, get_auth_token
from app.database import get_supabase_service, get_user_client
from app.services.file_processor import FileProcessor
from app.services.text_chunker import TextChunker
from app.services.embeddings import EmbeddingsService
from app.services.vector_store import VectorStore

# Inngest integration
from app.inngest.events import send_event, use_inngest_for, Events

logger = logging.getLogger(__name__)

router = APIRouter()

# Use centralized database module
supabase_service = get_supabase_service()

# File upload configuration
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_MIME_TYPES = [
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown"
]
ALLOWED_EXTENSIONS = [".pdf", ".docx", ".txt", ".md"]


async def process_file_background(
    file_id: str,
    file_path: str,
    file_type: str,
    organization_id: str
):
    """
    Background task to process uploaded file.
    1. Download from storage
    2. Extract text
    3. Chunk text
    4. Generate embeddings
    5. Store in Pinecone
    6. Update database
    """
    try:
        # Update status to processing (use service client for background tasks)
        supabase_service.table("knowledge_base_files").update({
            "status": "processing"
        }).eq("id", file_id).execute()
        
        # Download file from storage (use service client for background tasks)
        file_data = supabase_service.storage.from_("knowledge-base-files").download(file_path)
        
        # Extract text
        file_processor = FileProcessor()
        import io
        text = file_processor.extract_text(io.BytesIO(file_data), file_type)
        
        if not text or not text.strip():
            raise ValueError("No text could be extracted from file")
        
        # Chunk text
        chunker = TextChunker(chunk_size=500, chunk_overlap=50)
        chunks = chunker.chunk_text(text)
        
        if not chunks:
            raise ValueError("No chunks created from text")
        
        # Generate embeddings
        embeddings_service = EmbeddingsService()
        chunk_texts = [chunk["content"] for chunk in chunks]
        embeddings = embeddings_service.generate_embeddings(chunk_texts, input_type="document")
        
        # Prepare vectors for Pinecone
        vector_store = VectorStore()
        vectors = []
        chunk_records = []
        
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            vector_id = f"{file_id}:{i}"
            
            vectors.append({
                "id": vector_id,
                "values": embedding,
                "metadata": {
                    "file_id": file_id,
                    "chunk_index": i,
                    "organization_id": organization_id,
                    "content_preview": chunk["content"][:200]  # First 200 chars
                }
            })
            
            chunk_records.append({
                "file_id": file_id,
                "organization_id": organization_id,
                "chunk_index": i,
                "content": chunk["content"],
                "token_count": chunk["token_count"],
                "embedding_id": vector_id
            })
        
        # Store vectors in Pinecone
        vector_store.upsert_vectors(vectors)
        
        # Store chunks in database (use service client for background tasks)
        supabase_service.table("knowledge_base_chunks").insert(chunk_records).execute()
        
        # Update file status to completed (use service client for background tasks)
        supabase_service.table("knowledge_base_files").update({
            "status": "completed",
            "chunk_count": len(chunks)
        }).eq("id", file_id).execute()
        
    except Exception as e:
        # Update status to failed (use service client for background tasks)
        supabase_service.table("knowledge_base_files").update({
            "status": "failed",
            "error_message": str(e)
        }).eq("id", file_id).execute()
        
        # Clean up: delete file from storage (use service client for background tasks)
        try:
            supabase_service.storage.from_("knowledge-base-files").remove([file_path])
        except:
            pass


@router.post("/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    auth_token: str = Depends(get_auth_token)
):
    """
    Upload a file to the knowledge base.
    File is uploaded to storage and processed in the background.
    """
    # Create user-specific client for RLS security
    user_supabase = get_user_client(auth_token)
    
    # Get user's organization (RLS ensures user can only see their own memberships)
    user_id = current_user.get("sub")
    org_response = user_supabase.table("organization_members").select("organization_id").eq("user_id", user_id).execute()
    
    if not org_response.data:
        raise HTTPException(status_code=403, detail=f"User not in any organization")
    
    organization_id = org_response.data[0]["organization_id"]
    
    # Get file extension
    file_extension = file.filename.split(".")[-1].lower() if "." in file.filename else ""
    file_extension_with_dot = f".{file_extension}" if file_extension else ""
    
    # Validate file type (check both MIME type and extension)
    has_valid_mime = file.content_type in ALLOWED_MIME_TYPES
    has_valid_extension = file_extension_with_dot in ALLOWED_EXTENSIONS
    
    if not has_valid_mime and not has_valid_extension:
        raise HTTPException(
            status_code=400,
            detail=f"File type not supported. Allowed types: PDF, DOCX, TXT, MD"
        )
    
    # Read file content
    file_content = await file.read()
    file_size = len(file_content)
    
    # Validate file size
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE / 1024 / 1024}MB"
        )
    
    if file_size == 0:
        raise HTTPException(status_code=400, detail="File is empty")
    
    # Generate unique file ID
    file_id = str(uuid.uuid4())
    
    # Use extension from earlier validation, or default to "bin"
    if not file_extension:
        file_extension = "bin"
    
    # Storage path: {organization_id}/{file_id}.{extension}
    storage_path = f"{organization_id}/{file_id}.{file_extension}"
    
    # Fix MIME type for certain file extensions
    content_type = file.content_type
    if file_extension == "md":
        content_type = "text/markdown"
    elif file_extension == "txt":
        content_type = "text/plain"
    elif file_extension == "pdf":
        content_type = "application/pdf"
    elif file_extension == "docx":
        content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    
    try:
        # Upload to Supabase Storage (use service client - RLS already checked via organization_members)
        # We manually verified user has access to this organization above
        supabase_service.storage.from_("knowledge-base-files").upload(
            path=storage_path,
            file=file_content,
            file_options={"content-type": content_type}
        )
        
        # Create database record
        db_record = {
            "id": file_id,
            "organization_id": organization_id,
            "user_id": user_id,
            "filename": file.filename,
            "file_size": file_size,
            "file_type": file.content_type,
            "storage_path": storage_path,
            "status": "uploading"
        }
        
        result = supabase_service.table("knowledge_base_files").insert(db_record).execute()
        
        # Start processing via Inngest (if enabled) or BackgroundTasks (fallback)
        if use_inngest_for("knowledge_base"):
            event_sent = await send_event(
                Events.KNOWLEDGE_FILE_UPLOADED,
                {
                    "file_id": file_id,
                    "file_path": storage_path,
                    "file_type": file.content_type,
                    "organization_id": organization_id,
                    "user_id": user_id,
                    "filename": file.filename
                },
                user={"id": user_id}
            )
            
            if event_sent:
                logger.info(f"Knowledge base file {file_id} triggered via Inngest")
            else:
                # Fallback to BackgroundTasks if Inngest fails
                logger.warning(f"Inngest event failed, falling back to BackgroundTasks for file {file_id}")
                background_tasks.add_task(
                    process_file_background,
                    file_id,
                    storage_path,
                    file.content_type,
                    organization_id
                )
        else:
            # Use BackgroundTasks (legacy/fallback)
            background_tasks.add_task(
                process_file_background,
                file_id,
                storage_path,
                file.content_type,
                organization_id
            )
            logger.info(f"Knowledge base file {file_id} triggered via BackgroundTasks")
        
        return JSONResponse(
            status_code=201,
            content={
                "id": file_id,
                "filename": file.filename,
                "file_size": file_size,
                "file_type": file.content_type,
                "status": "uploading",
                "created_at": result.data[0]["created_at"]
            }
        )
        
    except Exception as e:
        # Clean up: try to delete uploaded file (use service client)
        try:
            supabase_service.storage.from_("knowledge-base-files").remove([storage_path])
        except:
            pass
        
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/files")
async def list_files(
    current_user: dict = Depends(get_current_user),
    auth_token: str = Depends(get_auth_token)
):
    """
    List all knowledge base files for the user's organization.
    """
    # Create user-specific client for RLS security
    user_supabase = get_user_client(auth_token)
    
    # Get user's organization (RLS ensures user can only see their own memberships)
    user_id = current_user.get("sub")
    org_response = user_supabase.table("organization_members").select("organization_id").eq("user_id", user_id).execute()
    
    if not org_response.data:
        raise HTTPException(status_code=403, detail="User not in any organization")
    
    organization_id = org_response.data[0]["organization_id"]
    
    # Get files
    files_response = user_supabase.table("knowledge_base_files").select("*").eq("organization_id", organization_id).order("created_at", desc=True).execute()
    
    return {"files": files_response.data}


@router.delete("/files/{file_id}")
async def delete_file(
    file_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a file from the knowledge base.
    """
    # Get user's organization (use service client to bypass RLS for delete operations)
    user_id = current_user.get("sub")
    org_response = supabase_service.table("organization_members").select("organization_id").eq("user_id", user_id).execute()
    
    if not org_response.data:
        raise HTTPException(status_code=403, detail="User not in any organization")
    
    organization_id = org_response.data[0]["organization_id"]
    
    # Get file (ensure it belongs to user's organization)
    file_response = supabase_service.table("knowledge_base_files").select("*").eq("id", file_id).eq("organization_id", organization_id).execute()
    
    if not file_response.data:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_data = file_response.data[0]
    storage_path = file_data["storage_path"]
    
    try:
        # Delete from Pinecone
        vector_store = VectorStore()
        vector_store.delete_by_file(file_id)
        
        # Delete from storage (use service client)
        supabase_service.storage.from_("knowledge-base-files").remove([storage_path])
        
        # Delete chunks (will cascade from file deletion)
        # Delete file record (will cascade delete chunks due to ON DELETE CASCADE)
        supabase_service.table("knowledge_base_files").delete().eq("id", file_id).execute()
        
        return Response(status_code=204)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


@router.get("/files/{file_id}/status")
async def get_file_status(
    file_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get processing status of a file.
    """
    # Get user's organization (use service client)
    user_id = current_user.get("sub")
    org_response = supabase_service.table("organization_members").select("organization_id").eq("user_id", user_id).execute()
    
    if not org_response.data:
        raise HTTPException(status_code=403, detail="User not in any organization")
    
    organization_id = org_response.data[0]["organization_id"]
    
    # Get file (use service client)
    file_response = supabase_service.table("knowledge_base_files").select("*").eq("id", file_id).eq("organization_id", organization_id).execute()
    
    if not file_response.data:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_data = file_response.data[0]
    
    # Calculate progress
    progress = 0
    message = ""
    
    if file_data["status"] == "uploading":
        progress = 10
        message = "Uploading file..."
    elif file_data["status"] == "processing":
        progress = 50
        message = f"Processing file... ({file_data.get('chunk_count', 0)} chunks)"
    elif file_data["status"] == "completed":
        progress = 100
        message = f"Completed ({file_data['chunk_count']} chunks)"
    elif file_data["status"] == "failed":
        progress = 0
        message = f"Failed: {file_data.get('error_message', 'Unknown error')}"
    
    return {
        "id": file_id,
        "status": file_data["status"],
        "progress": progress,
        "message": message,
        "chunk_count": file_data.get("chunk_count", 0)
    }
