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
        """Create execution strategy with refined queries"""
        strategy = {
            "recommended_agents": [],
            "search_approach": "parallel",
            "external_search_priority": "medium",
            "refined_queries": {}  # NEW: Agent-specific queries
        }
        
        # Base query components
        entities = intent.get('entities', [])
        keywords = intent.get('keywords', [])
        intent_type = intent.get('intent_type', 'general_guidance')
        
        # Agent selection and query refinement
        if intent_type == 'regulatory_guidance':
            strategy["recommended_agents"] = ["RegulationAgent", "CaseLawAgent"]
            strategy["refined_queries"] = {
                "RegulationAgent": self._create_regulation_query(entities, keywords),
                "CaseLawAgent": self._create_caselaw_query(entities, keywords)
            }
        elif intent_type == 'precedent_analysis':
            strategy["recommended_agents"] = ["PrecedentAgent", "CaseLawAgent"]
            strategy["refined_queries"] = {
                "PrecedentAgent": self._create_precedent_query(entities, keywords),
                "CaseLawAgent": self._create_caselaw_query(entities, keywords)
            }
        elif intent_type == 'transaction_analysis':
            strategy["recommended_agents"] = ["PrecedentAgent", "ExpertAgent", "CaseLawAgent"]
            strategy["refined_queries"] = {
                "PrecedentAgent": self._create_transaction_precedent_query(entities, keywords),
                "ExpertAgent": self._create_expert_query(entities, keywords),
                "CaseLawAgent": self._create_transaction_caselaw_query(entities, keywords)
            }
        else:
            strategy["recommended_agents"] = ["RegulationAgent", "CaseLawAgent"]
            strategy["refined_queries"] = {
                "RegulationAgent": self._create_general_regulation_query(keywords),
                "CaseLawAgent": self._create_general_caselaw_query(keywords)
            }
        
        # Add expert agent for complex queries
        if complexity in [QueryComplexity.COMPLEX, QueryComplexity.EXPERT]:
            if "ExpertAgent" not in strategy["recommended_agents"]:
                strategy["recommended_agents"].append("ExpertAgent")
                strategy["refined_queries"]["ExpertAgent"] = self._create_expert_query(entities, keywords)
        
        return strategy

    def _create_regulation_query(self, entities: List[str], keywords: List[str]) -> str:
        """Create focused regulation query (under 400 chars)"""
        # Take most important entities and keywords
        key_entities = entities[:2]  # Limit entities
        key_keywords = [kw for kw in keywords if len(kw) > 3][:4]  # Filter short words, limit count
        
        query_parts = []
        if key_entities:
            query_parts.extend(key_entities)
        if key_keywords:
            query_parts.extend(key_keywords[:3])  # Further limit for length
        
        query = " ".join(query_parts[:6])  # Max 6 terms
        return query[:390]  # Ensure under 400 chars

    def _create_precedent_query(self, entities: List[str], keywords: List[str]) -> str:
        """Create precedent-focused query"""
        precedent_terms = ["precedent", "similar", "transaction"]
        key_entities = entities[:2]
        
        query_parts = precedent_terms + key_entities
        query = " ".join(query_parts)
        return query[:390]

    def _create_transaction_precedent_query(self, entities: List[str], keywords: List[str]) -> str:
        """Create transaction precedent query"""
        transaction_terms = ["merger", "acquisition", "deal", "transaction"]
        key_entities = [e for e in entities if "338" in e or "election" in e][:2]
        
        query_parts = transaction_terms[:2] + key_entities
        query = " ".join(query_parts)
        return query[:390]

    def _create_expert_query(self, entities: List[str], keywords: List[str]) -> str:
        """Create expert analysis query"""
        expert_terms = ["analysis", "strategy", "planning"]
        key_entities = entities[:2]
        key_keywords = [kw for kw in keywords if kw in ["tax", "international", "GILTI", "NOL"]][:3]
        
        query_parts = expert_terms[:1] + key_entities + key_keywords
        query = " ".join(query_parts)
        return query[:390]

    def _create_caselaw_query(self, entities: List[str], keywords: List[str]) -> str:
        """Create case law query"""
        case_terms = ["case", "ruling", "court"]
        key_entities = entities[:2]
        
        query_parts = case_terms[:1] + key_entities
        query = " ".join(query_parts)
        return query[:390]

    def _create_transaction_caselaw_query(self, entities: List[str], keywords: List[str]) -> str:
        """Create transaction case law query"""
        key_entities = [e for e in entities if "338" in e][:1]
        transaction_terms = ["merger", "case", "ruling"]
        
        query_parts = transaction_terms[:2] + key_entities
        query = " ".join(query_parts)
        return query[:390]

    def _create_general_regulation_query(self, keywords: List[str]) -> str:
        """Create general regulation query"""
        reg_keywords = [kw for kw in keywords if kw not in ["the", "and", "or", "of", "to"]][:5]
        return " ".join(reg_keywords)[:390]

    def _create_general_caselaw_query(self, keywords: List[str]) -> str:
        """Create general case law query"""
        case_keywords = [kw for kw in keywords if kw not in ["the", "and", "or", "of", "to"]][:4]
        case_keywords.append("case")
        return " ".join(case_keywords)[:390]
    # Required abstract methods from BaseAgent
    def _build_initial_query(self, state: AgentState) -> str:
        return state.query
    
    def _apply_domain_specific_filtering(self, documents: List[Dict], state: AgentState) -> List[Dict]:
        return documents
