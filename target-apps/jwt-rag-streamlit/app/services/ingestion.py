import os
import uuid
from pathlib import Path
from typing import List, Dict
from PyPDF2 import PdfReader
from sqlalchemy.orm import Session
from app.config import get_settings
from app.models.document import Document, DocumentChunk
from app.models.pg_types import DocumentStatus
from app.services.bedrock_client import invoke_embed


def save_pdf_file(file_content: bytes, filename: str) -> str:
    """Save uploaded PDF file to storage directory"""
    settings = get_settings()
    storage_dir = Path(settings.pdf_storage_dir)
    
    # Ensure storage directory exists
    storage_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    file_id = str(uuid.uuid4())
    file_extension = Path(filename).suffix or '.pdf'
    unique_filename = f"{file_id}{file_extension}"
    file_path = storage_dir / unique_filename
    
    # Write file
    with open(file_path, 'wb') as f:
        f.write(file_content)
    
    return str(file_path)


def extract_text_from_pdf(file_path: str) -> List[Dict[str, any]]:
    """Extract text from PDF with page numbers"""
    pages = []
    
    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PdfReader(file)
            
            for page_num, page in enumerate(pdf_reader.pages, 1):
                text = page.extract_text()
                if text.strip():  # Only include non-empty pages
                    pages.append({
                        'page_number': page_num,
                        'text': text.strip()
                    })
    except Exception as e:
        raise Exception(f"Failed to extract text from PDF: {str(e)}")
    
    return pages


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """Split text into overlapping chunks by words"""
    words = text.split()
    chunks = []
    
    for i in range(0, len(words), chunk_size - overlap):
        chunk_words = words[i:i + chunk_size]
        chunk = ' '.join(chunk_words)
        chunks.append(chunk)
        
        # Stop if we've covered all words
        if i + chunk_size >= len(words):
            break
    
    return chunks


def process_document_ingestion(db: Session, document: Document) -> bool:
    """Process document ingestion: extract text, chunk, embed, and store"""
    settings = get_settings()
    
    try:
        # Update status to processing
        document.status = DocumentStatus.processing
        db.commit()
        
        # Extract text from PDF
        pages = extract_text_from_pdf(document.file_path)
        
        if not pages:
            raise Exception("No text content found in PDF")
        
        chunk_index = 0
        
        # Process each page
        for page_data in pages:
            page_text = page_data['text']
            page_number = page_data['page_number']
            
            # Chunk the page text
            chunks = chunk_text(
                page_text,
                chunk_size=settings.chunk_size,
                overlap=settings.chunk_overlap
            )
            
            # Process each chunk
            for chunk_text in chunks:
                if not chunk_text.strip():
                    continue
                
                # Generate embedding
                try:
                    embedding = invoke_embed(chunk_text)
                    embedding_str = ','.join(map(str, embedding))  # Store as comma-separated string
                except Exception as e:
                    print(f"Failed to generate embedding for chunk: {e}")
                    embedding_str = None
                
                # Create document chunk
                chunk = DocumentChunk(
                    document_id=document.id,
                    content=chunk_text,
                    embedding=embedding_str,
                    page_number=page_number,
                    chunk_index=chunk_index
                )
                
                db.add(chunk)
                chunk_index += 1
        
        # Update status to success
        document.status = DocumentStatus.success
        db.commit()
        
        return True
        
    except Exception as e:
        # Update status to failed
        document.status = DocumentStatus.failed
        db.commit()
        
        print(f"Document ingestion failed: {e}")
        return False
