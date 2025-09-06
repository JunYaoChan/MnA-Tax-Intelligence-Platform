from typing import List, Dict, Any, Optional
import asyncio
from supabase import create_client, Client
import numpy as np
from config.settings import Settings
import logging

logger = logging.getLogger(__name__)

class SupabaseVectorStore:
    """Supabase vector store with pgvector for similarity search"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client: Client = create_client(
            settings.supabase_url,
            settings.supabase_key
        )
        self.table_name = "tax_documents"
        
    async def search(
        self,
        query: str,
        top_k: int = 10,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict]:
        """
        Perform vector similarity search
        
        Args:
            query: Search query text
            top_k: Number of results to return
            filter: Optional filters to apply
        """
        try:
            # Generate embedding for query
            embedding = await self._generate_embedding(query)
            
            # Build query
            query_builder = self.client.table(self.table_name).select("*")
            
            # Apply filters if provided
            if filter:
                for key, value in filter.items():
                    if isinstance(value, list):
                        query_builder = query_builder.in_(key, value)
                    else:
                        query_builder = query_builder.eq(key, value)
            
            # Perform similarity search using pgvector
            response = await self._vector_search(
                query_builder,
                embedding,
                top_k
            )
            
            return self._format_results(response.data)
            
        except Exception as e:
            logger.error(f"Error in vector search: {e}")
            return []
    
    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding using OpenAI"""
        import openai
        
        openai.api_key = self.settings.openai_api_key
        
        response = await openai.Embedding.acreate(
            input=text,
            model="text-embedding-ada-002"
        )
        
        return response['data'][0]['embedding']
    
    async def _vector_search(
        self,
        query_builder,
        embedding: List[float],
        top_k: int
    ) -> Any:
        """Execute vector similarity search"""
        # Use pgvector's <-> operator for cosine similarity
        embedding_str = f"[{','.join(map(str, embedding))}]"
        
        response = query_builder.rpc(
            'match_documents',
            {
                'query_embedding': embedding_str,
                'match_count': top_k,
                'filter': {}
            }
        ).execute()
        
        return response
    
    def _format_results(self, data: List[Dict]) -> List[Dict]:
        """Format search results"""
        formatted = []
        
        for item in data:
            formatted.append({
                'id': item.get('id'),
                'title': item.get('title'),
                'content': item.get('content'),
                'type': item.get('document_type'),
                'relevance_score': item.get('similarity', 0),
                'metadata': item.get('metadata', {}),
                'date': item.get('created_at')
            })
        
        return formatted
    
    async def insert_document(self, document: Dict) -> bool:
        """Insert a document with its embedding"""
        try:
            # Generate embedding
            embedding = await self._generate_embedding(document['content'])
            
            # Prepare document
            doc_data = {
                **document,
                'embedding': embedding
            }
            
            # Insert into Supabase
            response = self.client.table(self.table_name).insert(doc_data).execute()
            
            return response.data is not None
            
        except Exception as e:
            logger.error(f"Error inserting document: {e}")
            return False
    
    async def batch_insert(self, documents: List[Dict]) -> int:
        """Batch insert multiple documents"""
        inserted = 0
        
        for doc in documents:
            if await self.insert_document(doc):
                inserted += 1
        
        logger.info(f"Inserted {inserted}/{len(documents)} documents")
        return inserted