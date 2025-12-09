"""
Vector store service using Pinecone.
Stores and retrieves embeddings for knowledge base chunks.
"""

import os
from typing import List, Dict, Optional
from pinecone import Pinecone


class VectorStore:
    """Manage vector storage in Pinecone."""
    
    def __init__(self):
        """Initialize Pinecone client and connect to index."""
        api_key = os.getenv("PINECONE_API_KEY")
        index_name = os.getenv("PINECONE_INDEX_NAME", "dealmotion-knowledge-base")
        
        if not api_key:
            raise ValueError("PINECONE_API_KEY must be set")
        
        # Initialize Pinecone (new API)
        pc = Pinecone(api_key=api_key)
        
        # Connect to index
        self.index_name = index_name
        self.index = pc.Index(index_name)
    
    def upsert_vectors(
        self,
        vectors: List[Dict[str, any]]
    ) -> Dict[str, int]:
        """
        Upsert vectors to Pinecone.
        
        Args:
            vectors: List of vector objects, each containing:
                - id: Unique vector ID (e.g., "file_id:chunk_index")
                - values: Embedding vector (1024 dimensions)
                - metadata: Dict with file_id, chunk_index, organization_id, etc.
        
        Returns:
            Dict with upserted_count
        """
        try:
            response = self.index.upsert(vectors=vectors)
            return {"upserted_count": response.upserted_count}
        except Exception as e:
            raise ValueError(f"Failed to upsert vectors: {str(e)}")
    
    def query_vectors(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filter: Optional[Dict] = None,
        include_metadata: bool = True
    ) -> List[Dict]:
        """
        Query similar vectors from Pinecone.
        
        Args:
            query_vector: Query embedding (1024 dimensions)
            top_k: Number of results to return
            filter: Metadata filter (e.g., {"organization_id": "uuid"})
            include_metadata: Whether to include metadata in results
            
        Returns:
            List of matches with id, score, and metadata
        """
        try:
            response = self.index.query(
                vector=query_vector,
                top_k=top_k,
                filter=filter,
                include_metadata=include_metadata
            )
            return response.matches
        except Exception as e:
            raise ValueError(f"Failed to query vectors: {str(e)}")
    
    def delete_vectors(self, ids: List[str]) -> None:
        """
        Delete vectors from Pinecone.
        
        Args:
            ids: List of vector IDs to delete
        """
        try:
            self.index.delete(ids=ids)
        except Exception as e:
            raise ValueError(f"Failed to delete vectors: {str(e)}")
    
    def delete_by_filter(self, filter: Dict) -> None:
        """
        Delete vectors by metadata filter.
        
        Args:
            filter: Metadata filter (e.g., {"file_id": "uuid"})
        """
        try:
            self.index.delete(filter=filter)
        except Exception as e:
            raise ValueError(f"Failed to delete vectors by filter: {str(e)}")
    
    def delete_by_file(self, file_id: str) -> None:
        """
        Delete all vectors for a specific file.
        
        Args:
            file_id: File ID to delete vectors for
        """
        self.delete_by_filter({"file_id": file_id})
    
    def get_stats(self) -> Dict:
        """
        Get index statistics.
        
        Returns:
            Dict with total_vector_count and other stats
        """
        try:
            return self.index.describe_index_stats()
        except Exception as e:
            raise ValueError(f"Failed to get index stats: {str(e)}")
