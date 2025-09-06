import re
import asyncio
from typing import List, Dict
from agents.base import BaseAgent
from models.state import AgentState
from models.results import RetrievalResult
import time

class RegulationAgent(BaseAgent):
    """Specializes in retrieving tax code and regulations"""
    
    def __init__(self, settings, vector_store):
        super().__init__("RegulationAgent", settings)
        self.vector_store = vector_store
        
    async def process(self, state: AgentState) -> RetrievalResult:
        start_time = time.time()
        
        try:
            reg_refs = self._extract_regulation_refs(state.query)
            documents = await self._retrieve_regulations(reg_refs, state)
            enhanced_docs = await self._cross_reference(documents)
            confidence = self._calculate_confidence(enhanced_docs)
            
            result = RetrievalResult(
                documents=enhanced_docs,
                confidence=confidence,
                source="regulations",
                metadata={
                    "references": reg_refs,
                    "cross_refs": len(enhanced_docs),
                    "direct_matches": len(reg_refs)
                },
                retrieval_time=time.time() - start_time
            )
            
            self.log_performance(start_time, result)
            return result
            
        except Exception as e:
            self.logger.error(f"Error in RegulationAgent: {e}")
            return RetrievalResult(
                documents=[],
                confidence=0.0,
                source="regulations",
                metadata={"error": str(e)},
                retrieval_time=time.time() - start_time
            )
    
    def _extract_regulation_refs(self, query: str) -> List[str]:
        """Extract regulation references from query"""
        patterns = [
            r'(?:section|§)\s*(\d+(?:\.\d+)?(?:\([a-z]\))?(?:\(\d+\))?)',
            r'(?:reg|regulation)\s*(\d+(?:\.\d+)?(?:-\d+)?)',
            r'26\s*(?:USC|U\.S\.C\.)\s*§?\s*(\d+)'
        ]
        
        refs = []
        for pattern in patterns:
            matches = re.findall(pattern, query.lower())
            refs.extend(matches)
        
        return list(set(refs))  # Remove duplicates
    
    async def _retrieve_regulations(self, refs: List[str], state: AgentState) -> List[Dict]:
        """Retrieve specific regulations"""
        documents = []
        
        # Retrieve specific references
        for ref in refs:
            docs = await self.vector_store.search(
                query=f"26 CFR section {ref}",
                top_k=3,
                filter={"type": "regulation", "section": ref}
            )
            documents.extend(docs)
        
        # General search if no specific refs
        if not refs:
            docs = await self._general_reg_search(state.query)
            documents.extend(docs)
        
        return documents
    
    async def _general_reg_search(self, query: str) -> List[Dict]:
        """General regulation search"""
        return await self.vector_store.search(
            query=query,
            top_k=self.settings.top_k_results,
            filter={"type": "regulation"}
        )
    
    async def _cross_reference(self, documents: List[Dict]) -> List[Dict]:
        """Cross-reference with related regulations"""
        enhanced = []
        
        for doc in documents:
            # Extract cross-references from content
            cross_refs = self._extract_cross_refs(doc.get('content', ''))
            doc['cross_references'] = cross_refs
            
            # Optionally fetch related sections
            if cross_refs and len(cross_refs) <= 3:
                related = await self._fetch_related_sections(cross_refs[:3])
                doc['related_sections'] = related
            
            enhanced.append(doc)
        
        return enhanced
    
    def _extract_cross_refs(self, content: str) -> List[str]:
        """Extract cross-references from regulation content"""
        pattern = r'(?:see|see also|cf\.)\s*(?:section|§)\s*(\d+(?:\.\d+)?)'
        matches = re.findall(pattern, content.lower())
        return list(set(matches))
    
    async def _fetch_related_sections(self, refs: List[str]) -> List[Dict]:
        """Fetch related regulation sections"""
        related = []
        for ref in refs:
            docs = await self.vector_store.search(
                query=f"section {ref}",
                top_k=1,
                filter={"type": "regulation"}
            )
            if docs:
                related.append({
                    "section": ref,
                    "title": docs[0].get('title', ''),
                    "relevance": docs[0].get('relevance_score', 0)
                })
        return related
    
    def _calculate_confidence(self, documents: List[Dict]) -> float:
        """Calculate confidence for regulation retrieval"""
        if not documents:
            return 0.0
        
        # Higher confidence for direct regulation matches
        direct_matches = [d for d in documents if d.get('type') == 'regulation']
        if direct_matches:
            return min(0.95, 0.85 + (len(direct_matches) * 0.02))
        
        return 0.75