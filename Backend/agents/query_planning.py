from typing import Dict, List
from agents.base import BaseAgent
from models.state import AgentState
from models.results import RetrievalResult
from models.enums import QueryComplexity
from config.settings import Settings
import time


class QueryPlanningAgent(BaseAgent):
    """Plans the retrieval strategy based on query analysis"""
    
    def __init__(self, settings: Settings):
        super().__init__("QueryPlanningAgent", settings)
        
    async def process(self, state: AgentState) -> RetrievalResult:
        start_time = time.time()
        
        # Analyze query intent and complexity
        intent = await self._analyze_intent(state.query)
        complexity = self._determine_complexity(intent)
        
        # Create retrieval strategy
        strategy = self._create_strategy(intent, complexity)
        
        # Update state
        state.intent = intent
        state.complexity = complexity
        state.metadata['strategy'] = strategy
        
        result = RetrievalResult(
            documents=[],
            confidence=0.95,
            source="query_planning",
            metadata={"strategy": strategy, "intent": intent},
            retrieval_time=time.time() - start_time
        )
        
        self.log_performance(start_time, result)
        return result
    
    async def _analyze_intent(self, query: str) -> Dict:
        """Analyze query intent using NLP"""
        # Simulate intent analysis
        keywords = query.lower().split()
        intent_type = "research"
        
        if any(word in keywords for word in ["section", "§", "reg", "regulation"]):
            intent_type = "regulation_lookup"
        elif any(word in keywords for word in ["case", "ruling", "decision"]):
            intent_type = "case_law"
        elif any(word in keywords for word in ["precedent", "similar", "previous"]):
            intent_type = "precedent_search"
            
        return {
            "type": intent_type,
            "keywords": keywords,
            "entities": self._extract_entities(query)
        }
    
    def _extract_entities(self, query: str) -> List[str]:
        """Extract tax-specific entities from query"""
        # Simplified entity extraction
        entities = []
        if "section" in query.lower():
            import re
            sections = re.findall(r'section\s+(\d+[a-z]?\(\w+\)?\(?[\d\w]*\)?)', query.lower())
            entities.extend(sections)
        return entities
    
    def _determine_complexity(self, intent: Dict) -> QueryComplexity:
        """Determine query complexity"""
        num_entities = len(intent.get('entities', []))
        num_keywords = len(intent.get('keywords', []))
        
        if num_entities <= 1 and num_keywords <= 5:
            return QueryComplexity.SIMPLE
        elif num_entities <= 3 and num_keywords <= 10:
            return QueryComplexity.MODERATE
        elif num_entities <= 5:
            return QueryComplexity.COMPLEX
        else:
            return QueryComplexity.EXPERT
    
    def _create_strategy(self, intent: Dict, complexity: QueryComplexity) -> Dict:
        """Create retrieval strategy based on intent and complexity"""
        strategy = {
            "parallel_agents": [],
            "priority_order": [],
            "fallback_options": []
        }
        
        if complexity == QueryComplexity.SIMPLE:
            strategy["parallel_agents"] = ["RegulationAgent"]
        elif complexity in [QueryComplexity.MODERATE, QueryComplexity.COMPLEX]:
            strategy["parallel_agents"] = [
                "CaseLawAgent", "RegulationAgent", 
                "PrecedentAgent", "ExpertAgent"
            ]
        else:  # EXPERT
            strategy["parallel_agents"] = [
                "CaseLawAgent", "RegulationAgent",
                "PrecedentAgent", "ExpertAgent"
            ]
            strategy["fallback_options"] = ["DeepSearchAgent"]
            
        return strategy