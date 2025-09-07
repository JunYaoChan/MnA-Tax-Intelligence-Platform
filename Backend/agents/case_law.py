import asyncio
from typing import List, Dict
from agents.base import BaseAgent
from models.state import AgentState
from models.results import RetrievalResult
import time

class CaseLawAgent(BaseAgent):
    """Specializes in retrieving case law and rulings"""
    
    def __init__(self, settings, vector_store, function_tools=None):
        super().__init__("CaseLawAgent", settings)
        self.vector_store = vector_store
        self.function_tools = function_tools or {}
        
    async def process(self, state: AgentState) -> RetrievalResult:
        start_time = time.time()
        
        try:
            search_query = self._build_case_query(state)
            documents = await self._vector_search(search_query)
            filtered_docs = self._filter_by_relevance(documents, state)
            confidence = self._calculate_confidence(filtered_docs)
            
            result = RetrievalResult(
                documents=filtered_docs,
                confidence=confidence,
                source="case_law",
                metadata={
                    "query": search_query, 
                    "total_found": len(documents),
                    "filtered_count": len(filtered_docs)
                },
                retrieval_time=time.time() - start_time
            )
            
            self.log_performance(start_time, result)
            return result
            
        except Exception as e:
            self.logger.error(f"Error in CaseLawAgent: {e}")
            return RetrievalResult(
                documents=[],
                confidence=0.0,
                source="case_law",
                metadata={"error": str(e)},
                retrieval_time=time.time() - start_time
            )
    
    def _build_case_query(self, state: AgentState) -> str:
        """Build case law specific search query"""
        base_query = state.query
        case_terms = ["revenue ruling", "case", "decision", "court", "PLR"]
        enhanced_query = f"{base_query} {' '.join(case_terms)}"
        return enhanced_query
    
    async def _vector_search(self, query: str) -> List[Dict]:
        """Perform vector similarity search"""
        results = await self.vector_store.search(
            query=query,
            top_k=self.settings.top_k_results,
            filter={"type": ["revenue_ruling", "private_letter_ruling", "case"]}
        )
        return results
    
    def _filter_by_relevance(self, documents: List[Dict], state: AgentState) -> List[Dict]:
        """Filter documents by relevance threshold"""
        threshold = getattr(self.settings, 'similarity_threshold', 0.7)
        filtered = [
            doc for doc in documents 
            if doc.get('relevance_score', 0) >= threshold
        ]
        
        # Sort by relevance
        return sorted(filtered, key=lambda x: x.get('relevance_score', 0), reverse=True)
    
    def _calculate_confidence(self, documents: List[Dict]) -> float:
        """Calculate confidence score based on retrieved documents"""
        if not documents:
            return 0.0
        
        scores = [doc.get('relevance_score', 0) for doc in documents]
        avg_score = sum(scores) / len(scores)
        
        # Adjust based on document count
        doc_count_factor = min(len(documents) / 5, 1.0)
        
        return avg_score * doc_count_factor
