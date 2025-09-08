import asyncio
from typing import List, Dict
from datetime import datetime
from agents.base import BaseAgent
from models.state import AgentState
from models.results import RetrievalResult
import time

class PrecedentAgent(BaseAgent):
    """Searches deal database for precedents using Neo4j and function tools when needed"""

    def __init__(self, settings, vector_store=None, neo4j_client=None, function_tools=None):
        super().__init__("PrecedentAgent", settings, vector_store, function_tools)
        self.neo4j = neo4j_client

    async def process(self, state: AgentState) -> RetrievalResult:
        start_time = time.time()

        try:
            # Build search query
            search_query = self._build_search_query(state)

            # First, try Neo4j graph search for internal precedents
            internal_precedents = await self._search_internal_precedents(state)

            # Determine if we need function tools
            use_function_tools = await self.should_use_function_tools(search_query, internal_precedents)

            enhanced_precedents = []
            all_sources = ["neo4j precedent database"]

            if use_function_tools:
                self.logger.info("Using function tools to enhance precedent search")

                # Call function tools for external research
                function_results = await self.call_function_tools(
                    search_query,
                    {"internal_documents": internal_precedents, "agent_type": "precedent"}
                )

                # Process function tool results
                for result in function_results:
                    enhanced_precedents.extend(self._process_function_results(result))

                all_sources.extend([f"{result['source']} function tool" for result in function_results])

            # Combine internal and external results
            all_precedents = internal_precedents + enhanced_precedents
            final_precedents = self._merge_and_rank_precedents(all_precedents, state)
            confidence = self._calculate_confidence(final_precedents)

            result = RetrievalResult(
                documents=final_precedents,
                confidence=confidence,
                source="precedent_agent",
                metadata={
                    "search_query": search_query,
                    "internal_precedents": len(internal_precedents),
                    "enhanced_precedents": len(enhanced_precedents),
                    "total_found": len(all_precedents),
                    "used_function_tools": use_function_tools,
                    "sources": all_sources,
                    "filters_applied": self._get_applied_filters(state)
                },
                retrieval_time=time.time() - start_time,
                pipeline_step="agent_precedent"
            )

            self.log_performance(start_time, result)
            return result

        except Exception as e:
            self.logger.error(f"Error in PrecedentAgent: {e}")
            return RetrievalResult(
                documents=[],
                confidence=0.0,
                source="precedent_agent",
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

    def _build_search_query(self, state: AgentState) -> str:
        """Build search query for precedent research"""
        base_query = state.query
        precedent_terms = ["deal", "transaction", "merger", "acquisition", "election", "precedent", "similar"]
        enhanced_query = f"{base_query} {' '.join(precedent_terms)}"

        # Add specific entities if found
        entities = state.intent.get('entities', [])
        if entities:
            enhanced_query += f" {' '.join(entities)}"

        return enhanced_query

    async def _search_internal_precedents(self, state: AgentState) -> List[Dict]:
        """Search internal Neo4j database for precedents"""
        if not self.neo4j:
            self.logger.warning("Neo4j client not available for precedent search")
            return []

        try:
            graph_query = self._build_graph_query(state)
            return await self._search_precedents(graph_query, state)
        except Exception as e:
            self.logger.error(f"Internal precedent search failed: {e}")
            return []

    def _process_function_results(self, function_result: Dict) -> List[Dict]:
        """Process results from function tools into precedent format"""
        processed_precedents = []
        data = function_result.get('data', [])
        source = function_result.get('source', 'unknown')

        if source == 'neo4j_precedent_search':
            # Format Neo4j function tool results
            for item in data:
                if isinstance(item, dict):
                    processed_precedents.append({
                        'id': item.get('deal', {}).get('id', f"neo4j_{len(processed_precedents)}"),
                        'title': item.get('deal', {}).get('title', 'Precedent Deal'),
                        'content': item.get('deal', {}).get('description', '').strip(),
                        'document_type': 'precedent_deal',
                        'relevance_score': item.get('relevance_score', 0.8),
                        'date': item.get('deal', {}).get('date', '').strip(),
                        'deal_value': item.get('deal', {}).get('value', ''),
                        'election_type': item.get('election', {}).get('type', ''),
                        'source': 'function_tool_neo4j',
                        'metadata': {
                            'source': 'neo4j_precedent_search',
                            'parties': item.get('deal', {}).get('parties', []),
                            'election_section': item.get('election', {}).get('section', ''),
                        }
                    })

        elif source == 'brave_search':
            # Convert web search results to precedent format
            for item in data:
                if isinstance(item, dict) and any(term in item.get('title', '').lower() for term in ['deal', 'merger', 'acquisition']):
                    processed_precedents.append({
                        'id': item.get('url', f"url_{len(processed_precedents)}"),
                        'title': item.get('title', 'Deal Precedent'),
                        'content': item.get('description', '').strip(),
                        'document_type': 'web_precedent',
                        'relevance_score': item.get('score', 0.7),
                        'date': item.get('age', '').strip(),
                        'source': 'function_tool_brave_search',
                        'metadata': {
                            'source': 'brave_search',
                            'url': item.get('url', ''),
                            'search_type': 'deal_precedent'
                        }
                    })

        return processed_precedents

    def _merge_and_rank_precedents(self, precedents: List[Dict], state: AgentState) -> List[Dict]:
        """Merge and rank precedents from multiple sources"""
        seen_ids = set()
        merged = []

        # Rank by relevance, recency, and deal size similarity
        for precedent in sorted(precedents, key=self._get_precedent_rank_key, reverse=True):
            doc_id = precedent.get('id', f"prec_{len(merged)}")

            if doc_id not in seen_ids:
                merged.append(precedent)
                seen_ids.add(doc_id)

            if len(merged) >= self.settings.top_k_results:
                break

        return merged

    def _get_precedent_rank_key(self, precedent: Dict) -> tuple:
        """Generate ranking key for precedent"""
        relevance = precedent.get('relevance_score', 0)

        # Date scoring (newer = higher)
        date_str = precedent.get('date', '')
        try:
            date_obj = datetime.fromisoformat(date_str)
            date_score = date_obj.year + date_obj.month / 12
        except:
            date_score = 2020  # Default past date

        # Source type priority (internal > external)
        source_priority = 1 if precedent.get('source', '').startswith('internal') else 0

        # Deal size similarity bonus
        size_similarity = precedent.get('deal_size_similarity', 0)

        return (relevance, date_score, source_priority, size_similarity)
