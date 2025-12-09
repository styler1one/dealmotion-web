"""
Text chunking service for splitting documents into manageable chunks.
Uses tiktoken for accurate token counting.
"""

import tiktoken
from typing import List, Dict


class TextChunker:
    """Split text into chunks with overlap for better context preservation."""
    
    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        encoding_name: str = "cl100k_base"  # GPT-4/Claude tokenizer
    ):
        """
        Initialize text chunker.
        
        Args:
            chunk_size: Target size of each chunk in tokens
            chunk_overlap: Number of tokens to overlap between chunks
            encoding_name: Tokenizer encoding to use
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.encoding = tiktoken.get_encoding(encoding_name)
    
    def chunk_text(self, text: str) -> List[Dict[str, any]]:
        """
        Split text into chunks with overlap.
        
        Args:
            text: Text to chunk
            
        Returns:
            List of chunks, each containing:
                - content: The chunk text
                - token_count: Number of tokens
                - chunk_index: Position in document
        """
        if not text or not text.strip():
            return []
        
        # Tokenize the entire text
        tokens = self.encoding.encode(text)
        
        chunks = []
        start_idx = 0
        chunk_index = 0
        
        while start_idx < len(tokens):
            # Get chunk tokens
            end_idx = start_idx + self.chunk_size
            chunk_tokens = tokens[start_idx:end_idx]
            
            # Decode back to text
            chunk_text = self.encoding.decode(chunk_tokens)
            
            # Create chunk object
            chunks.append({
                "content": chunk_text,
                "token_count": len(chunk_tokens),
                "chunk_index": chunk_index
            })
            
            # Move to next chunk with overlap
            start_idx += self.chunk_size - self.chunk_overlap
            chunk_index += 1
        
        return chunks
    
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Number of tokens
        """
        return len(self.encoding.encode(text))
