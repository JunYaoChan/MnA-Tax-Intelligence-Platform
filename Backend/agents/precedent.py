import asyncio
from typing import List, Dict
from datetime import datetime
from agents.base import BaseAgent
from models.state import AgentState
from models.results import RetrievalResult
import time

class PrecedentAgent(BaseAgent):
    """Searches internal deal database for precedents"""
    
    def __init__(self, settings, neo4j_client):
        super().__init__("PrecedentAgent", settings)
        self.neo4j = neo4j_client
        
    async def process(self, state: AgentState) -> RetrievalResult:
        start_time = time.time()
        
        try:
            graph_query = self._build_graph_query(state)
            precedents = await self._search_precedents(graph_query, state)
            ranked_precedents = self._rank_precedents(precedents, state)
            confidence = self._calculate_confidence(ranked_precedents)
            
            result = RetrievalResult(
                documents=ranked_precedents,
                confidence=confidence,
                source="precedents",
                metadata={
                    "total_precedents": len(precedents),
                    "query_type": state.intent.get('type', 'unknown'),
                    "filters_applied": self._get_applied_filters(state)
                },
                retrieval_time=time.time() - start_time
            )
            
            self.log_performance(start_time, result)
            return result
            
        except Exception as e:
            self.logger.error(f"Error in PrecedentAgent: {e}")
            return RetrievalResult(
                documents=[],
                confidence=0.0,
                source="precedents",
                metadata={"error": str(e)},
                retrieval_time=time.time() - start_time
            )
    
    def _build_graph_query(self, state: AgentState) -> Dict:
        """Build Neo4j query for precedent search"""
        entities = state.intent.get('entities', [])
        keywords = state.intent.get('keywords', [])
        
        # Build Cypher query dynamically
        query_parts = []
        params = {}
        
        # Base query
        cypher = "MATCH (d:Deal)-[:INVOLVES]->(e:Election) "
        
        # Add conditions based on entities
        conditions = []
        if entities:
            conditions.append("e.section IN $sections")
            params['sections'] = entities
        
        # Add keyword search
        if keywords:
            keyword_conditions = []
            for i, keyword in enumerate(keywords[:5]):  # Limit to 5 keywords
                keyword_conditions.append(f"d.description CONTAINS $keyword{i}")
                params[f'keyword{i}'] = keyword
            
            if keyword_conditions:
                conditions.append(f"({' OR '.join(keyword_conditions)})")
        
        # Add date filter for recent precedents
        conditions.append("d.date >= $min_date")
        params['min_date'] = "2020-01-01"
        
        if conditions:
            cypher += "WHERE " + " AND ".join(conditions) + " "
        
        cypher += "RETURN d, e ORDER BY d.date DESC LIMIT 20"
        
        return {"query": cypher, "params": params}
    
    async def _search_precedents(self, query: Dict, state: AgentState) -> List[Dict]:
        """Search precedent database using Neo4j"""
        results = await self.neo4j.execute_query(
            query["query"],
            query["params"]
        )
        
        precedents = []
        for record in results:
            deal = record['d']
            election = record['e']
            
            precedent = {
                "id": deal.get('id'),
                "title": deal.get('title'),
                "content": deal.get('description'),
                "date": deal.get('date'),
                "deal_value": deal.get('value'),
                "election_type": election.get('type'),
                "section": election.get('section'),
                "type": "precedent",
                "relevance_score": self._calculate_relevance(deal, election, state)
            }
            precedents.append(precedent)
        
        return precedents
    
    def _calculate_relevance(self, deal: Dict, election: Dict, state: AgentState) -> float:
        """Calculate relevance score for a precedent"""
        score = 0.5  # Base score
        
        # Boost for matching sections
        if election.get('section') in state.intent.get('entities', []):
            score += 0.2
        
        # Boost for recent deals
        deal_date = datetime.fromisoformat(deal.get('date', '2020-01-01'))
        if deal_date.year >= 2023:
            score += 0.15
        elif deal_date.year >= 2022:
            score += 0.1
        
        # Boost for similar deal size (if available)
        if 'deal_size' in state.context:
            target_size = state.context['deal_size']
            deal_size = self._parse_deal_value(deal.get('value', '0'))
            if 0.5 <= deal_size / target_size <= 2.0:
                score += 0.1
        
        # Boost for keyword matches
        keywords = state.intent.get('keywords', [])
        description = deal.get('description', '').lower()
        matching_keywords = sum(1 for kw in keywords if kw in description)
        score += min(0.15, matching_keywords * 0.03)
        
        return min(score, 1.0)
    
    def _parse_deal_value(self, value_str: str) -> float:
        """Parse deal value string to float"""
        import re
        
        # Remove currency symbols and convert to number
        value_str = value_str.upper().replace('$', '').replace(',', '')
        
        # Handle millions/billions
        multiplier = 1
        if 'B' in value_str:
            multiplier = 1_000_000_000
            value_str = value_str.replace('B', '')
        elif 'M' in value_str:
            multiplier = 1_000_000
            value_str = value_str.replace('M', '')
        
        try:
            return float(value_str) * multiplier
        except:
            return 0
    
    def _rank_precedents(self, precedents: List[Dict], state: AgentState) -> List[Dict]:
        """Rank precedents by relevance and recency"""
        # Sort by relevance score, then by date
        return sorted(
            precedents,
            key=lambda x: (x.get('relevance_score', 0), x.get('date', '')),
            reverse=True
        )
    
    def _get_applied_filters(self, state: AgentState) -> List[str]:
        """Get list of filters applied in the search"""
        filters = []
        
        if state.intent.get('entities'):
            filters.append(f"sections: {', '.join(state.intent['entities'])}")
        
        if state.context.get('deal_size'):
            filters.append(f"deal_size: ~${state.context['deal_size']}")
        
        if state.context.get('date_range'):
            filters.append(f"date_range: {state.context['date_range']}")
        
        return filters
    
    def _calculate_confidence(self, precedents: List[Dict]) -> float:
        """Calculate confidence based on precedent matches"""
        if not precedents:
            return 0.3
        
        # Calculate based on number and quality of precedents
        high_quality = [p for p in precedents if p.get('relevance_score', 0) >= 0.8]
        recent = [p for p in precedents if p.get('date', '') >= '2023-01-01']
        
        base_confidence = 0.5
        
        # Boost for high quality matches
        if high_quality:
            base_confidence += min(0.2, len(high_quality) * 0.05)
        
        # Boost for recent precedents
        if recent:
            base_confidence += min(0.15, len(recent) * 0.03)
        
        # Boost for total number of precedents
        if len(precedents) >= 5:
            base_confidence += 0.1
        
        return min(base_confidence, 0.95)
