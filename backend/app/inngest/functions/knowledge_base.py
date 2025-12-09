"""
Knowledge Base File Processing Inngest Function.

Handles file processing pipeline with full observability and automatic retries.

Events:
- dealmotion/knowledge.file.uploaded: Triggers file processing
- dealmotion/knowledge.file.processed: Emitted when processing is complete
- dealmotion/knowledge.file.failed: Emitted when processing fails

Steps:
1. Update status to processing
2. Download file from Supabase Storage
3. Extract text from file (PDF, DOCX, TXT, MD)
4. Chunk text into 500-char segments
5. Generate embeddings via Voyage AI
6. Store vectors in Pinecone
7. Save chunks to database
8. Update status to completed
"""

import logging
import io
from typing import List, Dict, Any
import inngest
from inngest import NonRetriableError, TriggerEvent

from app.inngest.client import inngest_client
from app.database import get_supabase_service
from app.services.file_processor import FileProcessor
from app.services.text_chunker import TextChunker
from app.services.embeddings import EmbeddingsService
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)

# Database client
supabase = get_supabase_service()


@inngest_client.create_function(
    fn_id="knowledge-file-process",
    trigger=TriggerEvent(event="dealmotion/knowledge.file.uploaded"),
    retries=2,
)
async def process_knowledge_file_fn(ctx, step):
    """
    Process an uploaded knowledge base file with full observability.
    
    Steps:
    1. Update status to processing
    2. Download file from storage
    3. Extract text
    4. Chunk text
    5. Generate embeddings
    6. Store in Pinecone
    7. Save chunks to database
    8. Update status to completed
    """
    event_data = ctx.event.data
    file_id = event_data["file_id"]
    file_path = event_data["file_path"]
    file_type = event_data["file_type"]
    organization_id = event_data["organization_id"]
    
    logger.info(f"Starting Inngest knowledge base processing for file {file_id}")
    
    try:
        # Step 1: Update status to processing
        await step.run(
            "update-status-processing",
            update_file_status,
            file_id, "processing", None, None
        )
        
        # Step 2: Download file from storage
        file_data = await step.run(
            "download-file",
            download_file_from_storage,
            file_path
        )
        
        # Step 3: Extract text from file
        text = await step.run(
            "extract-text",
            extract_text_from_file,
            file_data, file_type
        )
        
        # Step 4: Chunk text
        chunks = await step.run(
            "chunk-text",
            chunk_text,
            text
        )
        
        # Step 5: Generate embeddings
        embeddings = await step.run(
            "generate-embeddings",
            generate_embeddings,
            chunks
        )
        
        # Step 6: Store vectors in Pinecone
        await step.run(
            "store-vectors-pinecone",
            store_vectors_in_pinecone,
            file_id, organization_id, chunks, embeddings
        )
        
        # Step 7: Save chunks to database
        await step.run(
            "save-chunks-db",
            save_chunks_to_database,
            file_id, organization_id, chunks
        )
        
        # Step 8: Update status to completed
        chunk_count = len(chunks)
        await step.run(
            "update-status-completed",
            update_file_status,
            file_id, "completed", chunk_count, None
        )
        
        # Emit completion event
        await step.send_event(
            "emit-completion",
            inngest.Event(
                name="dealmotion/knowledge.file.processed",
                data={
                    "file_id": file_id,
                    "organization_id": organization_id,
                    "chunk_count": chunk_count,
                    "success": True
                }
            )
        )
        
        logger.info(f"Knowledge base file {file_id} processed: {chunk_count} chunks")
        
        return {
            "file_id": file_id,
            "chunk_count": chunk_count,
            "status": "completed"
        }
        
    except Exception as e:
        logger.error(f"Knowledge base processing failed for {file_id}: {e}")
        
        # Update status to failed
        try:
            await update_file_status(file_id, "failed", None, str(e))
        except:
            pass
        
        # Emit failure event
        await step.send_event(
            "emit-failure",
            inngest.Event(
                name="dealmotion/knowledge.file.failed",
                data={
                    "file_id": file_id,
                    "organization_id": organization_id,
                    "error": str(e)
                }
            )
        )
        
        raise NonRetriableError(f"Processing failed: {e}")


# =============================================================================
# Step Functions
# =============================================================================

async def update_file_status(
    file_id: str,
    status: str,
    chunk_count: int = None,
    error_message: str = None
) -> dict:
    """Update file status in database."""
    try:
        update_data = {"status": status}
        if chunk_count is not None:
            update_data["chunk_count"] = chunk_count
        if error_message is not None:
            update_data["error_message"] = error_message
        
        supabase.table("knowledge_base_files").update(update_data).eq("id", file_id).execute()
        logger.info(f"Updated file {file_id} status to {status}")
        return {"updated": True}
    except Exception as e:
        logger.error(f"Failed to update file status: {e}")
        raise NonRetriableError(f"Status update failed: {e}")


async def download_file_from_storage(file_path: str) -> bytes:
    """Download file from Supabase Storage."""
    try:
        file_data = supabase.storage.from_("knowledge-base-files").download(file_path)
        logger.info(f"Downloaded file from {file_path} ({len(file_data)} bytes)")
        return file_data
    except Exception as e:
        logger.error(f"Failed to download file: {e}")
        raise NonRetriableError(f"Download failed: {e}")


async def extract_text_from_file(file_data: bytes, file_type: str) -> str:
    """Extract text from file using FileProcessor."""
    try:
        file_processor = FileProcessor()
        text = file_processor.extract_text(io.BytesIO(file_data), file_type)
        
        if not text or not text.strip():
            raise NonRetriableError("No text could be extracted from file")
        
        logger.info(f"Extracted {len(text)} characters from file")
        return text
    except NonRetriableError:
        raise
    except Exception as e:
        logger.error(f"Failed to extract text: {e}")
        raise NonRetriableError(f"Text extraction failed: {e}")


async def chunk_text(text: str) -> List[Dict[str, Any]]:
    """Split text into chunks."""
    try:
        chunker = TextChunker(chunk_size=500, chunk_overlap=50)
        chunks = chunker.chunk_text(text)
        
        if not chunks:
            raise NonRetriableError("No chunks created from text")
        
        logger.info(f"Created {len(chunks)} chunks")
        return chunks
    except NonRetriableError:
        raise
    except Exception as e:
        logger.error(f"Failed to chunk text: {e}")
        raise NonRetriableError(f"Chunking failed: {e}")


async def generate_embeddings(chunks: List[Dict[str, Any]]) -> List[List[float]]:
    """Generate embeddings for chunks using Voyage AI."""
    try:
        embeddings_service = EmbeddingsService()
        chunk_texts = [chunk["content"] for chunk in chunks]
        embeddings = embeddings_service.generate_embeddings(chunk_texts, input_type="document")
        
        logger.info(f"Generated {len(embeddings)} embeddings")
        return embeddings
    except Exception as e:
        logger.error(f"Failed to generate embeddings: {e}")
        # Embeddings can fail due to rate limits - allow retry
        raise


async def store_vectors_in_pinecone(
    file_id: str,
    organization_id: str,
    chunks: List[Dict[str, Any]],
    embeddings: List[List[float]]
) -> dict:
    """Store vectors in Pinecone."""
    try:
        vector_store = VectorStore()
        vectors = []
        
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            vector_id = f"{file_id}:{i}"
            vectors.append({
                "id": vector_id,
                "values": embedding,
                "metadata": {
                    "file_id": file_id,
                    "chunk_index": i,
                    "organization_id": organization_id,
                    "content_preview": chunk["content"][:200]
                }
            })
        
        vector_store.upsert_vectors(vectors)
        logger.info(f"Stored {len(vectors)} vectors in Pinecone")
        return {"stored": len(vectors)}
    except Exception as e:
        logger.error(f"Failed to store vectors: {e}")
        # Pinecone can have transient failures - allow retry
        raise


async def save_chunks_to_database(
    file_id: str,
    organization_id: str,
    chunks: List[Dict[str, Any]]
) -> dict:
    """Save chunks to database."""
    try:
        chunk_records = []
        for i, chunk in enumerate(chunks):
            vector_id = f"{file_id}:{i}"
            chunk_records.append({
                "file_id": file_id,
                "organization_id": organization_id,
                "chunk_index": i,
                "content": chunk["content"],
                "token_count": chunk["token_count"],
                "embedding_id": vector_id
            })
        
        supabase.table("knowledge_base_chunks").insert(chunk_records).execute()
        logger.info(f"Saved {len(chunk_records)} chunks to database")
        return {"saved": len(chunk_records)}
    except Exception as e:
        logger.error(f"Failed to save chunks: {e}")
        raise NonRetriableError(f"Database save failed: {e}")

