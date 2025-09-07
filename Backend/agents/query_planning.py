import asyncio
import time
from typing import List, Dict
from agents.base import BaseAgent
from models.state import AgentState
from models.results import RetrievalResult
from models.enums import QueryComplexity
import re

class QueryPlanningAgent(BaseAgent):
    """Agent for query analysis and planning"""
    
    def __init__(self, settings):
        # Query planning doesn't need vector store or function tools
        super().__init__("QueryPlanningAgent", settings)
    
    async def process(self, state: AgentState) -> RetrievalResult:
        """Analyze query and create execution plan"""
        start_time = time.time()
        
        try:
            # Analyze query intent
            intent = self._analyze_intent(state.query)
            
            # Determine complexity
            complexity = self._determine_complexity(intent, state.query)
            
            # Create execution strategy
            strategy = self._create_strategy(intent, complexity)
            
            # Update state
            state.intent = intent
            state.complexity = complexity
            
            result = RetrievalResult(
                documents=[],  # Planning agent doesn't retrieve documents
                confidence=0.8,  # High confidence in planning
                source="query_planning",
                metadata={
                    "intent": intent,
                    "complexity": complexity.value,
                    "strategy": strategy,
                    "entities_found": len(intent.get('entities', [])),
                    "keywords_found": len(intent.get('keywords', []))
                },
                retrieval_time=time.time() - start_time,
                pipeline_step="step_1_query_submission"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Query planning failed: {e}")
            return RetrievalResult(
                documents=[],
                confidence=0.0,
                source="query_planning",
                metadata={"error": str(e)},
                retrieval_time=time.time() - start_time
            )
    
    def _analyze_intent(self, query: str) -> Dict:
        """Analyze query intent"""
        intent = {
            "entities": self._extract_entities(query),
            "keywords": self._extract_keywords(query),
            "intent_type": self._classify_intent(query),
            "question_type": self._identify_question_type(query)
        }
        return intent
    
    def _extract_entities(self, query: str) -> List[str]:
        """Extract tax entities (sections, etc.)"""
        entities = []
        
        # Pattern for tax sections
        section_patterns = [
            r'section\s+(\d+(?:\([a-z]\))?(?:\(\d+\))?)',
            r'§\s*(\d+(?:\([a-z]\))?(?:\(\d+\))?)',
            r'(\d+(?:\([a-z]\))?(?:\(\d+\))?)(?:\s+election)'
        ]
        
        for pattern in section_patterns:
            matches = re.findall(pattern, query.lower())
            entities.extend(matches)
        
        return list(set(entities))
    
    def _extract_keywords(self, query: str) -> List[str]:
        """Extract important keywords"""
        # Simple keyword extraction - could be enhanced with NLP
        important_terms = [
            'election', 'requirement', 'regulation', 'ruling', 'precedent',
            'transaction', 'acquisition', 'merger', 'tax', 'code', 'guidance'
        ]
        
        keywords = []
        query_lower = query.lower()
        
        for term in important_terms:
            if term in query_lower:
                keywords.append(term)
        
        # Add other significant words (length > 3, not common words)
        common_words = {'what', 'when', 'where', 'why', 'how', 'the', 'and', 'for', 'are'}
        words = query_lower.split()
        
        for word in words:
            if len(word) > 3 and word not in common_words and word not in keywords:
                keywords.append(word)
        
        return keywords[:10]  # Limit keywords
    
    def _classify_intent(self, query: str) -> str:
        """Classify the type of intent"""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ['requirement', 'how to', 'process', 'step']):
            return 'procedural_guidance'
        elif any(word in query_lower for word in ['regulation', 'code', 'section']):
            return 'regulatory_guidance'
        elif any(word in query_lower for word in ['precedent', 'case', 'ruling', 'decision']):
            return 'precedent_analysis'
        elif any(word in query_lower for word in ['transaction', 'deal', 'acquisition']):
            return 'transaction_analysis'
        else:
            return 'general_guidance'
    
    def _identify_question_type(self, query: str) -> str:
        """Identify the type of question"""
        query_lower = query.lower()
        
        if query_lower.startswith('what'):
            return 'definition'
        elif query_lower.startswith('how'):
            return 'procedure'
        elif query_lower.startswith('when'):
            return 'timing'
        elif query_lower.startswith('why'):
            return 'explanation'
        elif query_lower.startswith('where'):
            return 'location'
        else:
            return 'general'
    
    def _determine_complexity(self, intent: Dict, query: str) -> QueryComplexity:
        """Determine query complexity"""
        score = 0
        
        # Entity complexity
        entities = intent.get('entities', [])
        if len(entities) > 3:
            score += 3
        elif len(entities) > 1:
            score += 2
        elif len(entities) == 1:
            score += 1
        
        # Keyword complexity
        keywords = intent.get('keywords', [])
        if len(keywords) > 8:
            score += 2
        elif len(keywords) > 5:
            score += 1
        
        # Query length complexity
        if len(query.split()) > 20:
            score += 2
        elif len(query.split()) > 10:
            score += 1
        
        # Intent type complexity
        complex_intents = ['transaction_analysis', 'precedent_analysis']
        if intent.get('intent_type') in complex_intents:
            score += 2
        
        # Determine complexity level
        if score >= 7:
            return QueryComplexity.EXPERT
        elif score >= 5:
            return QueryComplexity.COMPLEX
        elif score >= 3:
            return QueryComplexity.MODERATE
        else:
            return QueryComplexity.SIMPLE
    
    def _create_strategy(self, intent: Dict, complexity: QueryComplexity) -> Dict:
        """Create execution strategy"""
        strategy = {
            "recommended_agents": [],
            "search_approach": "parallel",
            "external_search_priority": "medium"
        }
        
        # Agent selection based on intent
        intent_type = intent.get('intent_type', 'general_guidance')
        
        if intent_type == 'regulatory_guidance':
            strategy["recommended_agents"] = ["RegulationAgent", "CaseLawAgent"]
        elif intent_type == 'precedent_analysis':
            strategy["recommended_agents"] = ["PrecedentAgent", "CaseLawAgent"]
        elif intent_type == 'transaction_analysis':
            strategy["recommended_agents"] = ["PrecedentAgent", "ExpertAgent", "CaseLawAgent"]
        else:
            strategy["recommended_agents"] = ["RegulationAgent", "CaseLawAgent"]
        
        # Add expert agent for complex queries
        if complexity in [QueryComplexity.COMPLEX, QueryComplexity.EXPERT]:
            if "ExpertAgent" not in strategy["recommended_agents"]:
                strategy["recommended_agents"].append("ExpertAgent")
        
        # External search priority
        if complexity == QueryComplexity.EXPERT:
            strategy["external_search_priority"] = "high"
        elif complexity == QueryComplexity.SIMPLE:
            strategy["external_search_priority"] = "low"
        
        return strategy
    
    # Required abstract methods from BaseAgent
    def _build_initial_query(self, state: AgentState) -> str:
        return state.query
    
    def _apply_domain_specific_filtering(self, documents: List[Dict], state: AgentState) -> List[Dict]:
        return documents
