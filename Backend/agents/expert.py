import asyncio
from typing import List, Dict
from agents.base import BaseAgent
from models.state import AgentState
from models.results import RetrievalResult
import time

class ExpertAgent(BaseAgent):
    """Retrieves internal expert knowledge and insights"""
    
    def __init__(self, settings, knowledge_base):
        super().__init__("ExpertAgent", settings)
        self.knowledge_base = knowledge_base
        
    async def process(self, state: AgentState) -> RetrievalResult:
        start_time = time.time()
        
        try:
            expert_docs = await self._search_knowledge_base(state)
            annotations = await self._get_expert_annotations(state)
            enhanced_docs = self._enhance_with_insights(expert_docs, annotations)
            confidence = self._calculate_confidence(enhanced_docs)
            
            result = RetrievalResult(
                documents=enhanced_docs,
                confidence=confidence,
                source="expert_knowledge",
                metadata={
                    "annotations": len(annotations),
                    "knowledge_items": len(expert_docs),
                    "experts_consulted": self._get_expert_list(annotations)
                },
                retrieval_time=time.time() - start_time
            )
            
            self.log_performance(start_time, result)
            return result
            
        except Exception as e:
            self.logger.error(f"Error in ExpertAgent: {e}")
            return RetrievalResult(
                documents=[],
                confidence=0.0,
                source="expert_knowledge",
                metadata={"error": str(e)},
                retrieval_time=time.time() - start_time
            )
    
    async def _search_knowledge_base(self, state: AgentState) -> List[Dict]:
        """Search internal knowledge base"""
        # Build search query based on intent
        search_terms = []
        
        # Add entity-specific searches
        for entity in state.intent.get('entities', []):
            search_terms.append(f"section {entity}")
        
        # Add intent-based searches
        intent_type = state.intent.get('type', '')
        if intent_type == 'regulation_lookup':
            search_terms.extend(['guide', 'checklist', 'procedure'])
        elif intent_type == 'case_law':
            search_terms.extend(['analysis', 'interpretation', 'opinion'])
        elif intent_type == 'precedent_search':
            search_terms.extend(['similar', 'comparable', 'template'])
        
        # Search knowledge base
        documents = await self.knowledge_base.search(
            query=state.query,
            additional_terms=search_terms,
            top_k=self.settings.top_k_results
        )
        
        return documents
    
    async def _get_expert_annotations(self, state: AgentState) -> List[Dict]:
        """Retrieve expert annotations and notes"""
        annotations = await self.knowledge_base.get_annotations(
            query=state.query,
            entities=state.intent.get('entities', [])
        )
        
        # Filter by confidence level
        high_confidence_annotations = [
            ann for ann in annotations
            if ann.get('confidence', 0) >= 0.8
        ]
        
        return high_confidence_annotations
    
    def _enhance_with_insights(self, docs: List[Dict], annotations: List[Dict]) -> List[Dict]:
        """Enhance documents with expert insights"""
        enhanced = []
        
        for doc in docs:
            # Add relevant annotations
            relevant_annotations = self._match_annotations(doc, annotations)
            
            enhanced_doc = {
                **doc,
                'expert_annotations': relevant_annotations,
                'enhanced': True,
                'insight_level': self._calculate_insight_level(relevant_annotations)
            }
            
            # Add expert recommendations if available
            if relevant_annotations:
                enhanced_doc['expert_recommendations'] = self._extract_recommendations(
                    relevant_annotations
                )
            
            enhanced.append(enhanced_doc)
        
        return enhanced
    
    def _match_annotations(self, doc: Dict, annotations: List[Dict]) -> List[Dict]:
        """Match annotations to document"""
        matched = []
        
        doc_content = doc.get('content', '').lower()
        doc_entities = doc.get('entities', [])
        
        for ann in annotations:
            # Check if annotation is relevant to this document
            ann_keywords = ann.get('keywords', [])
            ann_entities = ann.get('entities', [])
            
            # Match by keywords
            keyword_match = any(kw.lower() in doc_content for kw in ann_keywords)
            
            # Match by entities
            entity_match = any(ent in doc_entities for ent in ann_entities)
            
            if keyword_match or entity_match:
                matched.append(ann)
        
        return matched
    
    def _calculate_insight_level(self, annotations: List[Dict]) -> str:
        """Calculate the level of expert insight"""
        if not annotations:
            return "basic"
        
        avg_confidence = sum(ann.get('confidence', 0) for ann in annotations) / len(annotations)
        
        if avg_confidence >= 0.9 and len(annotations) >= 3:
            return "comprehensive"
        elif avg_confidence >= 0.8 or len(annotations) >= 2:
            return "moderate"
        else:
            return "basic"
    
    def _extract_recommendations(self, annotations: List[Dict]) -> List[str]:
        """Extract recommendations from annotations"""
        recommendations = []
        
        for ann in annotations:
            if 'recommendation' in ann:
                recommendations.append(ann['recommendation'])
            
            # Extract action items
            if 'action_items' in ann:
                recommendations.extend(ann['action_items'])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_recommendations = []
        for rec in recommendations:
            if rec not in seen:
                seen.add(rec)
                unique_recommendations.append(rec)
        
        return unique_recommendations
    
    def _get_expert_list(self, annotations: List[Dict]) -> List[str]:
        """Get list of experts who provided annotations"""
        experts = set()
        
        for ann in annotations:
            if 'expert' in ann:
                experts.add(ann['expert'])
        
        return list(experts)
    
    def _calculate_confidence(self, documents: List[Dict]) -> float:
        """Calculate confidence for expert knowledge"""
        if not documents:
            return 0.4
        
        # Base confidence for expert knowledge
        base_confidence = 0.85
        
        # Boost for annotations
        docs_with_annotations = [
            d for d in documents 
            if d.get('expert_annotations')
        ]
        
        if docs_with_annotations:
            annotation_boost = min(0.1, len(docs_with_annotations) * 0.02)
            base_confidence += annotation_boost
        
        # Boost for comprehensive insights
        comprehensive_docs = [
            d for d in documents
            if d.get('insight_level') == 'comprehensive'
        ]
        
        if comprehensive_docs:
            base_confidence += 0.05
        
        return min(base_confidence, 0.98)