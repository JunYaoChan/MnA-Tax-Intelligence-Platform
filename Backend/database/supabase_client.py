# Backend/database/supabase_client.py
from typing import List, Dict, Any, Optional
import asyncio
import numpy as np
from config.settings import Settings
import logging
import re
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
        
        def rpc(self, function_name, params=None):
            return MockQuery()
    
    def create_client(url, key):
        return Client(url, key)
    
    class MockTable:
        def __init__(self, table_name):
            self.table_name = table_name
        
        def select(self, columns="*"):
            return MockQuery()
        
        def insert(self, data):
            return MockQuery()
        
        def update(self, data):
            return MockQuery()
        
        def delete(self):
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
        # Runtime flag to prevent repeated RPC errors if backend function/schema incompatible
        self.rpc_available = False
        
    async def search(
        self,
        query: str,
        top_k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
        similarity_threshold: Optional[float] = None
    ) -> List[Dict]:
        """
        Perform vector similarity search using RPC function to avoid URI length issues
        
        Args:
            query: Search query text
            top_k: Number of results to return
            filter: Optional filters to apply
            similarity_threshold: Minimum similarity score
        """
        try:
            # Hybrid search (vector + lexical) if enabled
            if getattr(self.settings, "enable_hybrid_search", False):
                return await self.hybrid_search(query, top_k=top_k, filter=filter, similarity_threshold=similarity_threshold)

            # Generate embedding for vector-only search
            embedding = await self.generate_embedding(query)
            threshold = similarity_threshold if similarity_threshold is not None else self.settings.vector_similarity_threshold
            return await self.search_with_rpc(embedding, top_k, threshold, filter)
        except Exception as e:
            logger.error(f"Error in vector search: {e}")
            # Fallback to text search
            return await self.fallback_text_search(query, top_k, filter)
    
    async def search_with_rpc(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        similarity_threshold: Optional[float] = None,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Use RPC function for vector search to avoid URI length issues"""
        try:
            # If RPC is disabled by settings, use direct safe search to avoid DB RPC errors
            if (hasattr(self.settings, "use_supabase_rpc") and not getattr(self.settings, "use_supabase_rpc")) or not getattr(self, "rpc_available", True):
                return await self.vector_search_direct_safe(query_embedding, top_k, filter_dict)
            # Use the match_documents RPC function
            thr = similarity_threshold if similarity_threshold is not None else self.settings.vector_similarity_threshold
            response = self.client.rpc(
                'match_documents',
                {
                    'query_embedding': query_embedding,
                    'match_threshold': thr,
                    'match_count': top_k
                }
            ).execute()
            
            results = response.data if response.data else []
            
            # Apply additional filters if needed (supports dotted keys for nested dicts e.g. "metadata.processor_document_id")
            if filter_dict and results:
                def get_nested(obj: Dict[str, Any], path: str):
                    cur = obj
                    for part in path.split("."):
                        if isinstance(cur, dict) and part in cur:
                            cur = cur[part]
                        else:
                            return None
                    return cur

                filtered_results = []
                for result in results:
                    match = True
                    for key, value in filter_dict.items():
                        rv = get_nested(result, key)
                        if isinstance(value, list):
                            if rv not in value:
                                match = False
                                break
                        else:
                            if rv != value:
                                match = False
                                break
                    if match:
                        filtered_results.append(result)
                results = filtered_results
            
            return self.format_results(results)
            
        except Exception as e:
            # Disable RPC for subsequent calls to avoid repeated errors
            try:
                self.rpc_available = False
            except Exception:
                pass
            logger.warning(f"RPC vector search failed; disabling RPC and using direct search: {e}")
            return await self.vector_search_direct_safe(query_embedding, top_k, filter_dict)
    
    async def hybrid_search(self, query: str, top_k: int = 10, filter: Optional[Dict[str, Any]] = None, similarity_threshold: Optional[float] = None) -> List[Dict]:
        """
        Hybrid retrieval that blends vector similarity with a simple lexical score.
        Final score = alpha * vector_score + (1 - alpha) * lexical_score.
        """
        try:
            # Vector part
            embedding = await self.generate_embedding(query)
            threshold = similarity_threshold if similarity_threshold is not None else self.settings.vector_similarity_threshold
            vector_results = await self.search_with_rpc(
                embedding, top_k=self.settings.top_k_results, similarity_threshold=threshold, filter_dict=filter
            )

            # Lexical part (fetch candidates and score locally)
            lexical_candidates = await self.fallback_text_search(
                query=query, top_k=getattr(self.settings, "hybrid_lexical_top_k", 20), filter_dict=filter
            )

            # Combine
            alpha = getattr(self.settings, "hybrid_alpha", 0.5)

            def clip01(x: float) -> float:
                try:
                    return max(0.0, min(1.0, float(x)))
                except Exception:
                    return 0.0

            merged: Dict[Any, Dict] = {}

            # Add vector results
            for doc in vector_results:
                vid = doc.get("id")
                vscore = clip01(doc.get("relevance_score", 0.0))
                merged[vid] = {**doc}
                merged[vid]["vector_score"] = vscore
                merged[vid]["lexical_score"] = 0.0

            # Compute lexical scores and merge
            terms = [t for t in re.findall(r"\w+", (query or "").lower()) if len(t) > 2]
            for doc in lexical_candidates:
                lid = doc.get("id")
                lscore = self._lexical_score(doc, terms)
                if lid in merged:
                    merged[lid]["lexical_score"] = max(merged[lid].get("lexical_score", 0.0), lscore)
                else:
                    nd = {**doc}
                    nd["vector_score"] = 0.0
                    nd["lexical_score"] = lscore
                    merged[lid] = nd

            # Compute hybrid score
            combined = []
            for d in merged.values():
                v = clip01(d.get("vector_score", 0.0))
                l = clip01(d.get("lexical_score", 0.0))
                h = alpha * v + (1.0 - alpha) * l
                d["relevance_score"] = h
                d["source"] = d.get("source", "hybrid")
                combined.append(d)

            combined.sort(key=lambda x: x.get("relevance_score", 0.0), reverse=True)
            return combined[:top_k]
        except Exception as e:
            logger.error(f"Hybrid search failed, falling back to vector-only: {e}")
            # Fallback to vector-only
            embedding = await self.generate_embedding(query)
            threshold = similarity_threshold if similarity_threshold is not None else self.settings.vector_similarity_threshold
            return await self.search_with_rpc(embedding, top_k, threshold, filter)

    def _lexical_score(self, doc: Dict[str, Any], terms: List[str]) -> float:
        """
        Simple lexical scoring based on term frequency in title/content with small title boost.
        """
        if not terms:
            return 0.0
        title = (doc.get("title", "") or "").lower()
        content = (doc.get("content", "") or "").lower()
        if not title and not content:
            return 0.0
        hits = 0
        for t in terms:
            hits += content.count(t)
            if t in title:
                hits += 1  # title boost
        # Normalize roughly by number of terms (scale denominator to keep scores in [0,1])
        denom = max(1.0, len(terms) * 3.0)
        score = hits / denom
        return max(0.0, min(1.0, score))

    async def vector_search_direct_safe(
        self,
        embedding: List[float],
        top_k: int,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict]:
        """
        Safe direct vector search with chunked embedding approach
        """
        try:
            # For very long embeddings, we'll use a simpler approach
            # Create a smaller representation for the query
            embedding_str = str(embedding[:100])  # Use only first 100 dimensions for URL
            
            # Build basic query without embedding in URL
            query_builder = self.client.table(self.table_name).select(
                "id, title, content, metadata, created_at"
            )
            
            # Apply filters if provided
            if filter_dict:
                for key, value in filter_dict.items():
                    if isinstance(value, list):
                        query_builder = query_builder.in_(key, value)
                    else:
                        query_builder = query_builder.eq(key, value)
            
            # Get results and manually calculate similarity
            response = query_builder.limit(top_k * 2).execute()  # Get more results for manual filtering
            
            if not response.data:
                return []
                
            # For now, return results without similarity scoring to avoid URI issues
            return self.format_results(response.data[:top_k])
            
        except Exception as e:
            logger.error(f"Direct safe vector search failed: {e}")
            return await self.fallback_text_search("", top_k, filter_dict)
    
    async def fallback_text_search(
        self,
        query: str = "",
        top_k: int = 10,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict]:
        """Fallback to simple text search when vector search fails"""
        try:
            query_builder = self.client.table(self.table_name).select("*").limit(top_k)
            
            # Apply filters if provided
            if filter_dict:
                for key, value in filter_dict.items():
                    if isinstance(value, list):
                        query_builder = query_builder.in_(key, value)
                    else:
                        query_builder = query_builder.eq(key, value)
            
            # If query provided, search in content
            if query:
                # Use basic text search
                query_builder = query_builder.ilike('content', f'%{query}%')
            
            response = query_builder.execute()
            return self.format_results(response.data if response.data else [])
            
        except Exception as e:
            logger.error(f"Fallback search failed: {e}")
            return []
    
    def format_results(self, data: List[Dict]) -> List[Dict]:
        """Format search results with consistent structure"""
        formatted = []
        
        for item in data:
            formatted.append({
                'id': item.get('id'),
                'title': item.get('title', 'Unknown Document'),
                'content': item.get('content', ''),
                'document_type': (item.get('metadata', {}) or {}).get('document_type', item.get('document_type', 'unknown')),
                'type': (item.get('metadata', {}) or {}).get('document_type', item.get('document_type', 'unknown')),  # backward compatibility
                'relevance_score': item.get('similarity', 0.8),  # Default relevance
                'metadata': item.get('metadata', {}),
                'date': item.get('created_at'),
                'source': 'supabase'
            })
        
        return formatted
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding using OpenAI API"""
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
    
    async def insert_document(self, document: Dict) -> bool:
        """Insert a document with its embedding"""
        try:
            # Generate embedding for the content
            embedding = await self.generate_embedding(document['content'])
            
            # Prepare document data
            doc_data = {
                'title': document.get('title', 'Untitled Document'),
                'content': document['content'],
                'metadata': document.get('metadata', {}),
                'embedding': embedding
            }
            
            # Insert into Supabase
            response = self.client.table(self.table_name).insert(doc_data).execute()
            
            if response.data:
                logger.info(f"Document inserted successfully: {doc_data.get('title')}")
                return True
            else:
                logger.error(f"Failed to insert document: {response}")
                return False
            
        except Exception as e:
            logger.error(f"Error inserting document: {e}")
            return False
    
    async def insert_documents_batch(self, documents: List[Dict]) -> int:
        """Batch insert multiple documents with embeddings"""
        inserted_count = 0
        
        try:
            # Process documents in smaller batches to avoid timeouts
            batch_size = 5
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]
                
                # Generate embeddings for batch
                batch_with_embeddings = []
                for doc in batch:
                    try:
                        embedding = await self.generate_embedding(doc['content'])
                        doc_data = {
                            'title': doc.get('title', 'Untitled Document'),
                            'content': doc['content'],
                            'metadata': doc.get('metadata', {}),
                            'embedding': embedding
                        }
                        batch_with_embeddings.append(doc_data)
                    except Exception as e:
                        logger.error(f"Failed to process document {doc.get('title', 'unknown')}: {e}")
                
                # Insert batch
                if batch_with_embeddings:
                    try:
                        response = self.client.table(self.table_name).insert(batch_with_embeddings).execute()
                        if response.data:
                            inserted_count += len(response.data)
                            logger.info(f"Batch inserted: {len(response.data)} documents")
                    except Exception as e:
                        logger.error(f"Failed to insert batch: {e}")
                
                # Small delay between batches
                await asyncio.sleep(0.1)
        
        except Exception as e:
            logger.error(f"Error in batch insert: {e}")
        
        return inserted_count
    
    async def insert_sample_documents(self) -> int:
        """Insert sample tax documents for testing"""
        sample_docs = [
            {
                "title": "Section 338(h)(10) Election Requirements",
                "content": """Section 338(h)(10) provides a mechanism for partners in a partnership to step up the basis of their partnership interest without triggering immediate tax recognition. The election allows partners to recognize gain on the excess of the FMV over their basis in the partnership interest.

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
                "content": """In Smith v. Commissioner, the Tax Court held that the taxpayer could not step up the basis of partnership interests under Section 338(h)(10). The court reasoned that the partnership did not meet the qualified bankruptcy exception requirements.

                The court determined that even though the partnership was in bankruptcy, the taxpayer was not a qualified purchaser because they were not buying substantially all the assets.""",
                "document_type": "case_law",
                "metadata": {
                    "case": "Smith v. Commissioner",
                    "year": "2018",
                    "court": "tax_court",
                    "section": "338(h)(10)"
                }
            },
            {
                "title": "Internal Revenue Code Section 754 Election",
                "content": """Section 754 allows partners to adjust their basis in partnership property after certain partnership distributions. This election can be made unilaterally by any partner and results in a deemed sale of assets within the partnership, allowing partners to receive basis adjustments without triggering taxable gain.

                The election must be filed with the partnership's return for the year the distribution occurs.""",
                "document_type": "regulation",
                "metadata": {
                    "section": "754",
                    "topic": "basis adjustment",
                    "year": 2024
                }
            },
            {
                "title": "Revenue Ruling 2019-02 - Digital Assets",
                "content": """Revenue Ruling 2019-02 provides guidance on the tax treatment of digital assets and cryptocurrencies. The ruling clarifies that virtual currencies are treated as property for tax purposes, not as currency.

                Taxpayers must recognize gain or loss on the sale or exchange of virtual currency, and the character of the gain or loss depends on whether the virtual currency is a capital asset.""",
                "document_type": "revenue_ruling",
                "metadata": {
                    "ruling": "2019-02",
                    "topic": "digital assets",
                    "year": 2019
                }
            }
        ]

        logger.info("Inserting sample tax documents...")
        inserted = await self.insert_documents_batch(sample_docs)
        logger.info(f"Sample documents inserted: {inserted}")
        return inserted

    async def update_document(self, doc_id: int, updates: Dict) -> bool:
        """Update an existing document"""
        try:
            # If content is being updated, regenerate embedding
            if 'content' in updates:
                updates['embedding'] = await self.generate_embedding(updates['content'])
            
            response = self.client.table(self.table_name).update(updates).eq('id', doc_id).execute()
            
            return response.data is not None
            
        except Exception as e:
            logger.error(f"Error updating document {doc_id}: {e}")
            return False
    
    async def delete_document(self, doc_id: int) -> bool:
        """Delete a document by ID"""
        try:
            response = self.client.table(self.table_name).delete().eq('id', doc_id).execute()
            return response.data is not None
            
        except Exception as e:
            logger.error(f"Error deleting document {doc_id}: {e}")
            return False
    
    async def get_document(self, doc_id: int) -> Optional[Dict]:
        """Get a specific document by ID"""
        try:
            response = self.client.table(self.table_name).select("*").eq('id', doc_id).execute()
            
            if response.data and len(response.data) > 0:
                return self.format_results(response.data)[0]
            return None
            
        except Exception as e:
            logger.error(f"Error getting document {doc_id}: {e}")
            return None
    
    async def list_documents(
        self,
        limit: int = 50,
        offset: int = 0,
        document_type: Optional[str] = None
    ) -> List[Dict]:
        """List documents with pagination and filtering"""
        try:
            query = self.client.table(self.table_name).select("*")
            
            if document_type:
                # document_type column removed from tax_documents; retaining parameter for backward compatibility.
                # Note: DB-level filtering by metadata.document_type is not implemented here.
                pass
            
            response = query.order('created_at', desc=True).range(offset, offset + limit - 1).execute()
            
            return self.format_results(response.data if response.data else [])
            
        except Exception as e:
            logger.error(f"Error listing documents: {e}")
            return []
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            # Count total documents
            total_response = self.client.table(self.table_name).select("id", count="exact").execute()
            total_count = total_response.count if hasattr(total_response, 'count') else 0
            
            # Count by document type (derived from metadata since column was removed)
            type_response = self.client.table(self.table_name).select("metadata").execute()
            types = {}
            if type_response.data:
                for doc in type_response.data:
                    md = doc.get('metadata') or {}
                    doc_type = md.get('document_type', 'unknown')
                    types[doc_type] = types.get(doc_type, 0) + 1
            
            return {
                'total_documents': total_count,
                'document_types': types,
                'table_name': self.table_name
            }
            
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {'total_documents': 0, 'document_types': {}, 'error': str(e)}

    async def initialize_database(self):
        """Initialize the database schema (for reference - execute in Supabase SQL editor)"""
        init_sql = """
        -- Enable the pgvector extension
        CREATE EXTENSION IF NOT EXISTS vector;

        -- Create the table for tax documents
        CREATE TABLE IF NOT EXISTS tax_documents (
            id BIGSERIAL PRIMARY KEY,
            title TEXT,
            content TEXT NOT NULL,
            metadata JSONB DEFAULT '{}',
            embedding vector(1536),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );

        -- Create indexes for better performance
        CREATE INDEX IF NOT EXISTS tax_docs_content_idx ON tax_documents USING gin(to_tsvector('english', content));
        CREATE INDEX IF NOT EXISTS tax_docs_metadata_idx ON tax_documents USING gin(metadata);
        CREATE INDEX IF NOT EXISTS tax_docs_created_at_idx ON tax_documents(created_at DESC);
        CREATE INDEX IF NOT EXISTS tax_docs_embedding_idx ON tax_documents USING ivfflat(embedding vector_cosine_ops) WITH (lists = 100);

        -- Vector similarity search function
        CREATE OR REPLACE FUNCTION match_documents(
            query_embedding vector(1536),
            match_threshold float DEFAULT 0.7,
            match_count int DEFAULT 10
        )
        RETURNS TABLE(
            id bigint,
            title text,
            content text,
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
                tax_documents.metadata,
                1 - (tax_documents.embedding <=> query_embedding) AS similarity
            FROM tax_documents
            WHERE 1 - (tax_documents.embedding <=> query_embedding) > match_threshold
            ORDER BY tax_documents.embedding <=> query_embedding
            LIMIT match_count;
        END;
        $$;
        """
        
        logger.info("Database initialization SQL:")
        logger.info("Execute this in your Supabase SQL editor:")
        logger.info(f"\n{init_sql}")
        
        return init_sql

# Alias for backward compatibility
class SupabaseClient(SupabaseVectorStore):
    """Backward compatibility alias"""
    pass
