from typing import List, Dict, Any, Optional
import asyncio
import numpy as np
from config.settings import Settings
import logging
from openai import AsyncOpenAI

# Import supabase with fallback for compatibility issues
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError as e:
    logging.error(f"Supabase import error: {e}")
    SUPABASE_AVAILABLE = False
    # Create mock classes for development
    class Client:
        def __init__(self, url, key):
            self.url = url
            self.key = key
        
        def table(self, table_name):
            return MockTable(table_name)
    
    def create_client(url, key):
        return Client(url, key)
    
    class MockTable:
        def __init__(self, table_name):
            self.table_name = table_name
        
        def select(self, columns="*"):
            return MockQuery()
        
        def insert(self, data):
            return MockQuery()
    
    class MockQuery:
        def in_(self, key, values):
            return self
        
        def eq(self, key, value):
            return self
        
        def order(self, column):
            return self
        
        def limit(self, count):
            return self
        
        def execute(self):
            return MockResponse()
    
    class MockResponse:
        def __init__(self):
            self.data = []

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
        
        # Initialize OpenAI client with new API
        self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        
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
            
            # Perform similarity search using direct SQL since match_documents might not exist
            response = await self._vector_search_direct(
                embedding,
                top_k,
                filter
            )
            
            return self._format_results(response)
            
        except Exception as e:
            logger.error(f"Error in vector search: {e}")
            return []
    
    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding using OpenAI (Fixed for new API)"""
        try:
            response = await self.openai_client.embeddings.create(
                input=text,
                model="text-embedding-ada-002"
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            # Return zero vector on error
            return [0.0] * 1536
    
    async def _vector_search_direct(
        self,
        embedding: List[float],
        top_k: int,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict]:
        """
        Execute vector similarity search using direct SQL approach
        since match_documents function might not exist
        """
        try:
            # Convert embedding to string format
            embedding_str = f"[{','.join(map(str, embedding))}]"
            
            # Build the base query
            select_query = self.client.table(self.table_name).select(
                "id, title, content, document_type, metadata, created_at, "
                f"embedding <-> '{embedding_str}' as similarity"
            )
            
            # Apply filters if provided
            if filter_dict:
                for key, value in filter_dict.items():
                    if isinstance(value, list):
                        select_query = select_query.in_(key, value)
                    else:
                        select_query = select_query.eq(key, value)
            
            # Order by similarity and limit results
            response = select_query.order('similarity').limit(top_k).execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            logger.error(f"Direct vector search failed: {e}")
            # Fallback to simple text search
            return await self._fallback_text_search(top_k, filter_dict)
    
    async def _fallback_text_search(
        self,
        top_k: int,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict]:
        """Fallback to text search when vector search fails"""
        try:
            query = self.client.table(self.table_name).select("*").limit(top_k)
            
            if filter_dict:
                for key, value in filter_dict.items():
                    if isinstance(value, list):
                        query = query.in_(key, value)
                    else:
                        query = query.eq(key, value)
            
            response = query.execute()
            return response.data if response.data else []
            
        except Exception as e:
            logger.error(f"Fallback search failed: {e}")
            return []
    
    def _format_results(self, data: List[Dict]) -> List[Dict]:
        """Format search results"""
        formatted = []
        
        for item in data:
            formatted.append({
                'id': item.get('id'),
                'title': item.get('title'),
                'content': item.get('content'),
                'type': item.get('document_type'),
                'relevance_score': 1.0 - item.get('similarity', 1.0),  # Convert distance to similarity
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

        return inserted

    async def insert_sample_documents(self):
        """Insert some sample tax documents for testing"""
        sample_docs = [
            {
                "title": "Section 338(h)(10) Election Requirements",
                "content": """Section 338(h)(10) provides a mechanism for partners in a partnership to step up the basis of their partnership interest without triggering immediate tax recognition. The election allows partners to recognize gain on the excess of the FMV over their basis in the partnership interest...

                Requirements for making the election include:
                1. The partnership must have at least 10 partners
                2. All partners must consent to the election
                3. The election must be made on or before the 15th day of the 4th month after the end of the tax year
                4. The partnership must file the election with Form 8023

                The election is available for distributions made after October 21, 1996.""",
                "document_type": "regulation",
                "metadata": {
                    "section": "338(h)(10)",
                    "topic": "partnership basis step-up",
                    "year": 2024,
                    "authority": "irc_tax_code"
                }
            },
            {
                "title": "Case Law: Smith v. Commissioner - Basis Step Up",
                "content": """In Smith v. Commissioner, the Tax Court held that the taxpayer could not step up the basis of partnership interests under Section 338(h)(10). The court reasoned that the partnership did not meet the qualified bankruptcy exception requirements...

                The court determined that even though the partnership was in bankruptcy, the taxpayer was not a qualified purchaser because they were not buying substantially all the assets.""",
                "document_type": "case_law",
                "metadata": {
                    "case": "Smith v. Commissioner",
                    "year": "2018",
                    "court": "tax_court",
                    "section": "338(h)(10)"
                }
            }
        ]

        inserted = await self.batch_insert(sample_docs)
        logger.info(f"Sample documents inserted: {inserted}")
        return inserted

    async def initialize_database(self):
        """Initialize the database schema"""
        try:
            # SQL to create the tax_documents table with vector extension
            init_sql = """
            -- Enable the pgvector extension
            CREATE EXTENSION IF NOT EXISTS vector;

            -- Create the table for tax documents
            CREATE TABLE IF NOT EXISTS tax_documents (
                id BIGSERIAL PRIMARY KEY,
                title TEXT,
                content TEXT NOT NULL,
                document_type TEXT,
                metadata JSONB DEFAULT '{}',
                embedding vector(1536),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );

            -- Create indexes for better performance
            CREATE INDEX IF NOT EXISTS tax_docs_content_idx ON tax_documents USING gin(to_tsvector('english', content));
            CREATE INDEX IF NOT EXISTS tax_docs_type_idx ON tax_documents(document_type);
            CREATE INDEX IF NOT EXISTS tax_docs_metadata_idx ON tax_documents USING gin(metadata);
            CREATE INDEX IF NOT EXISTS tax_docs_created_at_idx ON tax_documents(created_at DESC);
            CREATE INDEX IF NOT EXISTS tax_docs_embedding_idx ON tax_documents USING ivfflat(embedding vector_cosine_ops) WITH (lists = 100);

            -- Alternative vector similarity search function
            CREATE OR REPLACE FUNCTION match_documents(
                query_embedding vector(1536),
                match_threshold float DEFAULT 0.7,
                match_count int DEFAULT 10
            )
            RETURNS TABLE(
                id bigint,
                title text,
                content text,
                document_type text,
                metadata jsonb,
                similarity float
            )
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RETURN QUERY
                SELECT
                    tax_documents.id,
                    tax_documents.title,
                    tax_documents.content,
                    tax_documents.document_type,
                    tax_documents.metadata,
                    1 - (tax_documents.embedding <=> query_embedding) AS similarity
                FROM tax_documents
                WHERE 1 - (tax_documents.embedding <=> query_embedding) > match_threshold
                ORDER BY tax_documents.embedding <=> query_embedding
                LIMIT match_count;
            END;
            $$;
            """

            # This would need to be executed via Supabase dashboard or direct SQL connection
            # Since we can't execute DDL via the client, we'll provide the SQL script
            logger.info("Database initialization SQL generated. Execute this in your Supabase SQL editor:")
            logger.info(f"\n{init_sql}")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
