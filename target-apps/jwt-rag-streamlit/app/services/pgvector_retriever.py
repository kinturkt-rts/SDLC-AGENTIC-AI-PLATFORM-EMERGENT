from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.config import get_settings
from app.models.document import DocumentChunk, Document
from app.models.collection import Collection
from app.services.bedrock_client import invoke_embed


def retrieve_relevant_chunks(db: Session, collection_id: int, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Retrieve most relevant document chunks for a query using vector similarity"""
    settings = get_settings()
    
    try:
        # Generate query embedding
        query_embedding = invoke_embed(query)
        query_vector_str = ','.join(map(str, query_embedding))
        
        # For SQLite (testing), use simple text matching
        if settings.database_url.startswith("sqlite://"):
            chunks = db.query(DocumentChunk).join(Document).filter(
                Document.collection_id == collection_id,
                DocumentChunk.content.contains(query.split()[0]) if query.split() else True
            ).limit(top_k).all()
            
            results = []
            for chunk in chunks:
                results.append({
                    'content': chunk.content,
                    'document_title': chunk.document.title,
                    'page_number': chunk.page_number,
                    'confidence': 0.8  # Mock confidence for SQLite
                })
            return results
        
        # For PostgreSQL with pgvector, use cosine similarity
        query_sql = text("""
            SELECT 
                dc.content,
                d.title as document_title,
                dc.page_number,
                1 - (dc.embedding <=> CAST(:query_vector AS vector)) as similarity
            FROM document_chunks dc
            JOIN documents d ON dc.document_id = d.id
            WHERE d.collection_id = :collection_id
                AND dc.embedding IS NOT NULL
            ORDER BY dc.embedding <=> CAST(:query_vector AS vector)
            LIMIT :top_k
        """)
        
        result = db.execute(query_sql, {
            'query_vector': f'[{query_vector_str}]',
            'collection_id': collection_id,
            'top_k': top_k
        })
        
        chunks = []
        for row in result:
            chunks.append({
                'content': row.content,
                'document_title': row.document_title,
                'page_number': row.page_number,
                'confidence': float(row.similarity)
            })
        
        return chunks
        
    except Exception as e:
        print(f"Vector retrieval failed: {e}")
        
        # Fallback to simple text search
        search_term = query.split()[0] if query.split() else ''
        chunks = db.query(DocumentChunk).join(Document).filter(
            Document.collection_id == collection_id,
            DocumentChunk.content.ilike(f'%{search_term}%')
        ).limit(top_k).all()
        
        results = []
        for chunk in chunks:
            results.append({
                'content': chunk.content,
                'document_title': chunk.document.title,
                'page_number': chunk.page_number,
                'confidence': 0.6  # Lower confidence for fallback search
            })
        
        return results
