"""
File processing service for extracting text from various file types.
Supports: PDF, DOCX, TXT, MD (Markdown)
"""

import io
from typing import BinaryIO
import PyPDF2
from docx import Document
import markdown


class FileProcessor:
    """Extract text from different file types."""
    
    @staticmethod
    def extract_text(file: BinaryIO, file_type: str) -> str:
        """
        Extract text from a file based on its type.
        
        Args:
            file: Binary file object
            file_type: MIME type of the file
            
        Returns:
            Extracted text as string
            
        Raises:
            ValueError: If file type is not supported
        """
        if file_type == "application/pdf":
            return FileProcessor._extract_from_pdf(file)
        elif file_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            return FileProcessor._extract_from_docx(file)
        elif file_type == "text/plain":
            return FileProcessor._extract_from_txt(file)
        elif file_type == "text/markdown":
            return FileProcessor._extract_from_markdown(file)
        elif file_type == "application/octet-stream":
            # Fallback for .md files that get wrong MIME type
            # Try to process as markdown/text
            return FileProcessor._extract_from_markdown(file)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
    
    @staticmethod
    def _extract_from_pdf(file: BinaryIO) -> str:
        """Extract text from PDF file."""
        try:
            pdf_reader = PyPDF2.PdfReader(file)
            text_parts = []
            
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            
            return "\n\n".join(text_parts)
        except Exception as e:
            raise ValueError(f"Failed to extract text from PDF: {str(e)}")
    
    @staticmethod
    def _extract_from_docx(file: BinaryIO) -> str:
        """Extract text from DOCX file."""
        try:
            doc = Document(file)
            text_parts = []
            
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_parts.append(paragraph.text)
            
            return "\n\n".join(text_parts)
        except Exception as e:
            raise ValueError(f"Failed to extract text from DOCX: {str(e)}")
    
    @staticmethod
    def _extract_from_txt(file: BinaryIO) -> str:
        """Extract text from TXT file."""
        try:
            content = file.read()
            # Try UTF-8 first, fall back to latin-1
            try:
                return content.decode('utf-8')
            except UnicodeDecodeError:
                return content.decode('latin-1')
        except Exception as e:
            raise ValueError(f"Failed to extract text from TXT: {str(e)}")
    
    @staticmethod
    def _extract_from_markdown(file: BinaryIO) -> str:
        """Extract text from Markdown file."""
        try:
            content = file.read()
            # Try UTF-8 first, fall back to latin-1
            try:
                md_text = content.decode('utf-8')
            except UnicodeDecodeError:
                md_text = content.decode('latin-1')
            
            # Convert markdown to plain text (removes formatting)
            html = markdown.markdown(md_text)
            # Simple HTML tag removal (for plain text)
            import re
            text = re.sub('<[^<]+?>', '', html)
            return text
        except Exception as e:
            raise ValueError(f"Failed to extract text from Markdown: {str(e)}")
