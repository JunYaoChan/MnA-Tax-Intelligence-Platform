from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class VectorStore(ABC):
    """Abstract base class for vector stores"""
    
    @abstractmethod
    async def search(
        self,
        query: str,
        top_k: int = 10,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict]:
        """Search for similar documents"""
        pass
    
    @abstractmethod
    async def insert_document(self, document: Dict) -> bool:
        """Insert a document"""
        pass
    
    @abstractmethod
    async def batch_insert(self, documents: List[Dict]) -> int:
        """Batch insert documents"""
        pass

class KnowledgeBase:
    """Internal knowledge base management"""
    
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
        self._cache = {}
        
    async def search(
        self,
        query: str,
        additional_terms: List[str] = None,
        top_k: int = 10
    ) -> List[Dict]:
        """Search knowledge base"""
        # Enhance query with additional terms
        if additional_terms:
            enhanced_query = f"{query} {' '.join(additional_terms)}"
        else:
            enhanced_query = query
        
        # Check cache
        cache_key = f"{enhanced_query}_{top_k}"
        if cache_key in self._cache:
            logger.debug(f"Cache hit for query: {enhanced_query[:50]}...")
            return self._cache[cache_key]
        
        # Search vector store
        results = await self.vector_store.search(
            enhanced_query,
            top_k=top_k,
            filter={"type": ["knowledge_base", "guide", "checklist"]}
        )
        
        # Cache results
        self._cache[cache_key] = results
        
        return results
    
    async def get_annotations(
        self,
        query: str,
        entities: List[str] = None
    ) -> List[Dict]:
        """Get expert annotations"""
        filter_dict = {"type": "annotation"}
        
        if entities:
            filter_dict["entities"] = entities
        
        annotations = await self.vector_store.search(
            query,
            top_k=20,
            filter=filter_dict
        )
        
        # Format annotations
        formatted = []
        for ann in annotations:
            formatted.append({
                'id': ann.get('id'),
                'note': ann.get('content'),
                'expert': ann.get('author'),
                'confidence': ann.get('relevance_score', 0.8),
                'keywords': ann.get('metadata', {}).get('keywords', []),
                'entities': ann.get('metadata', {}).get('entities', [])
            })
        
        return formatted