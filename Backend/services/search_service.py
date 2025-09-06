from typing import List, Dict, Any, Optional
import asyncio
import logging
from datetime import datetime
from services.embedding_service import EmbeddingService
from database.supabase_client import SupabaseVectorStore
from database.neo4j_client import Neo4jClient
from utils.text_processing import TextProcessor
from config.settings import Settings

logger = logging.getLogger(__name__)

class SearchService:
    """Unified search service"""
    
    def __init__(
        self,
        settings: Settings,
        vector_store: SupabaseVectorStore,
        neo4j_client: Neo4jClient
    ):
        self.settings = settings
        self.vector_store = vector_store
        self.neo4j = neo4j_client
        self.embedding_service = EmbeddingService(settings)
        self.text_processor = TextProcessor()
        
    async def hybrid_search(
        self,
        query: str,
        search_type: str = "all",
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search across multiple sources
        
        Args:
            query: Search query
            search_type: Type of search (all, vector, graph, keyword)
            filters: Optional filters
            top_k: Number of results
        """
        results = []
        
        # Determine search strategies based on type
        strategies = self._get_search_strategies(search_type)
        
        # Execute searches in parallel
        search_tasks = []
        
        if "vector" in strategies:
            search_tasks.append(
                self._vector_search(query, filters, top_k)
            )
        
        if "graph" in strategies:
            search_tasks.append(
                self._graph_search(query, filters, top_k)
            )
        
        if "keyword" in strategies:
            search_tasks.append(
                self._keyword_search(query, filters, top_k)
            )
        
        # Wait for all searches to complete
        if search_tasks:
            search_results = await asyncio.gather(*search_tasks, return_exceptions=True)
            
            # Combine results
            for result in search_results:
                if isinstance(result, list):
                    results.extend(result)
                elif isinstance(result, Exception):
                    logger.error(f"Search failed: {result}")
        
        # Deduplicate and rank results
        ranked_results = self._rank_and_deduplicate(results, query)
        
        return ranked_results[:top_k]
    
    async def _vector_search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Perform vector similarity search"""
        try:
            # Enhance query for better retrieval
            enhanced_query = await self.embedding_service.enhance_query(query)
            
            # Search vector store
            results = await self.vector_store.search(
                query=enhanced_query,
                top_k=top_k * 2,  # Get more results for later filtering
                filter=filters
            )
            
            # Add search metadata
            for result in results:
                result['search_type'] = 'vector'
                result['search_score'] = result.get('relevance_score', 0)
            
            return results
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []
    
    async def _graph_search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Perform graph database search"""
        try:
            # Extract entities from query
            sections = self.text_processor.extract_section_references(query)
            dates = self.text_processor.extract_dates(query)
            values = self.text_processor.extract_monetary_values(query)
            
            # Build graph query parameters
            deal_characteristics = {
                'election_type': '338' if '338' in query else None,
                'min_date': dates[0] if dates else '2020-01-01',
                'min_value': values[0]['amount'] if values else 0,
                'max_value': values[0]['amount'] * 2 if values else 1e12
            }
            
            # Search for similar deals
            graph_results = await self.neo4j.find_similar_deals(
                deal_characteristics,
                limit=top_k
            )
            
            # Format results
            results = []
            for record in graph_results:
                deal = record.get('d', {})
                election = record.get('e', {})
                
                result = {
                    'id': deal.get('id'),
                    'title': deal.get('title'),
                    'content': deal.get('description'),
                    'type': 'precedent',
                    'search_type': 'graph',
                    'search_score': self._calculate_graph_relevance(
                        deal, election, query
                    ),
                    'metadata': {
                        'deal_value': deal.get('value'),
                        'date': deal.get('date'),
                        'election_type': election.get('type')
                    }
                }
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Graph search failed: {e}")
            return []
    
    async def _keyword_search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Perform keyword-based search"""
        try:
            # Extract keywords
            keywords = self.text_processor.tokenize(query)
            
            # Build keyword query
            keyword_query = ' OR '.join(keywords[:5])  # Limit keywords
            
            # Search with keywords
            results = await self.vector_store.search(
                query=keyword_query,
                top_k=top_k,
                filter=filters
            )
            
            # Add search metadata
            for result in results:
                result['search_type'] = 'keyword'
                result['search_score'] = self._calculate_keyword_relevance(
                    result.get('content', ''),
                    keywords
                )
            
            return results
            
        except Exception as e:
            logger.error(f"Keyword search failed: {e}")
            return []
    
    def _get_search_strategies(self, search_type: str) -> List[str]:
        """Determine which search strategies to use"""
        if search_type == "all":
            return ["vector", "graph", "keyword"]
        elif search_type == "vector":
            return ["vector"]
        elif search_type == "graph":
            return ["graph"]
        elif search_type == "keyword":
            return ["keyword"]
        else:
            return ["vector"]  # Default to vector search
    
    def _rank_and_deduplicate(
        self,
        results: List[Dict[str, Any]],
        query: str
    ) -> List[Dict[str, Any]]:
        """Rank and deduplicate search results"""
        # Deduplicate by ID
        seen_ids = set()
        unique_results = []
        
        for result in results:
            result_id = result.get('id')
            
            # Skip if already seen
            if result_id and result_id in seen_ids:
                continue
            
            if result_id:
                seen_ids.add(result_id)
            
            # Calculate combined score
            result['combined_score'] = self._calculate_combined_score(
                result, query
            )
            
            unique_results.append(result)
        
        # Sort by combined score
        unique_results.sort(
            key=lambda x: x.get('combined_score', 0),
            reverse=True
        )
        
        return unique_results
    
    def _calculate_combined_score(
        self,
        result: Dict[str, Any],
        query: str
    ) -> float:
        """Calculate combined relevance score"""
        # Get base search score
        search_score = result.get('search_score', 0)
        
        # Apply weights based on search type
        search_type = result.get('search_type', 'unknown')
        
        type_weights = {
            'vector': 1.0,
            'graph': 0.9,
            'keyword': 0.8,
            'unknown': 0.5
        }
        
        weighted_score = search_score * type_weights.get(search_type, 0.5)
        
        # Boost for recency (if date available)
        if 'date' in result.get('metadata', {}):
            try:
                doc_date = datetime.fromisoformat(result['metadata']['date'])
                days_old = (datetime.now() - doc_date).days
                recency_boost = max(0, 1 - (days_old / 365))  # Decay over 1 year
                weighted_score += recency_boost * 0.1
            except:
                pass
        
        # Boost for exact matches
        if query.lower() in result.get('title', '').lower():
            weighted_score += 0.2
        
        return min(weighted_score, 1.0)  # Cap at 1.0
    
    def _calculate_graph_relevance(
        self,
        deal: Dict,
        election: Dict,
        query: str
    ) -> float:
        """Calculate relevance score for graph results"""
        score = 0.5  # Base score
        
        query_lower = query.lower()
        
        # Check for section matches
        if election.get('section') and election['section'] in query:
            score += 0.2
        
        # Check for keyword matches in description
        description = deal.get('description', '').lower()
        keywords = self.text_processor.tokenize(query)
        
        matching_keywords = sum(1 for kw in keywords if kw in description)
        score += min(0.3, matching_keywords * 0.05)
        
        return min(score, 1.0)
    
    def _calculate_keyword_relevance(
        self,
        content: str,
        keywords: List[str]
    ) -> float:
        """Calculate keyword-based relevance score"""
        content_lower = content.lower()
        
        # Count keyword occurrences
        matches = sum(1 for kw in keywords if kw in content_lower)
        
        # Calculate score
        score = min(1.0, matches / max(len(keywords), 1))
        
        return score