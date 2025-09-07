import asyncio
import aiohttp
from typing import List, Dict
from agents.base import BaseAgent
from models.state import AgentState
from models.results import RetrievalResult
import time
import logging

logger = logging.getLogger(__name__)

class WebSearchAgent(BaseAgent):
    """Agent that searches external web sources for real-time tax information"""
    
    def __init__(self, settings):
        super().__init__("WebSearchAgent", settings)
        self.google_api_key = settings.google_search_api_key
        self.google_cse_id = settings.google_cse_id
        self.search_base_url = "https://www.googleapis.com/customsearch/v1"
        
    async def process(self, state: AgentState) -> RetrievalResult:
        start_time = time.time()
        
        try:
            # Build search queries for tax-specific sources
            search_queries = self._build_search_queries(state)
            
            # Perform parallel searches
            all_results = []
            for query in search_queries:
                results = await self._search_web(query)
                all_results.extend(results)
            
            # Filter and rank results
            filtered_results = self._filter_tax_sources(all_results)
            ranked_results = self._rank_by_authority(filtered_results)
            
            # Calculate confidence
            confidence = self._calculate_confidence(ranked_results)
            
            result = RetrievalResult(
                documents=ranked_results,
                confidence=confidence,
                source="web_search",
                metadata={
                    "queries_used": search_queries,
                    "total_found": len(all_results),
                    "filtered_count": len(ranked_results),
                    "sources": list(set([r.get('domain') for r in ranked_results]))
                },
                retrieval_time=time.time() - start_time
            )
            
            self.log_performance(start_time, result)
            return result
            
        except Exception as e:
            self.logger.error(f"Error in WebSearchAgent: {e}")
            return RetrievalResult(
                documents=[],
                confidence=0.0,
                source="web_search",
                metadata={"error": str(e)},
                retrieval_time=time.time() - start_time
            )
    
    def _build_search_queries(self, state: AgentState) -> List[str]:
        """Build targeted search queries for tax information"""
        base_query = state.query
        
        # Tax-specific search queries
        queries = [
            f"{base_query} site:irs.gov",  # Official IRS source
            f"{base_query} site:treasury.gov",  # Treasury Department
            f"{base_query} \"Internal Revenue Code\"",  # IRC references
            f"{base_query} \"tax code\" recent",  # Recent tax code changes
            f"{base_query} \"revenue ruling\" OR \"private letter ruling\"",  # Tax rulings
        ]
        
        # Add entity-specific searches
        entities = state.intent.get('entities', [])
        for entity in entities:
            queries.append(f"Section {entity} tax requirements 2024 2025")
        
        return queries[:3]  # Limit to avoid rate limits
    
    async def _search_web(self, query: str) -> List[Dict]:
        """Perform web search using Google Custom Search API"""
        try:
            params = {
                'key': self.google_api_key,
                'cx': self.google_cse_id,
                'q': query,
                'num': 10,
                'dateRestrict': 'y2',  # Last 2 years for current info
                'sort': 'date',  # Prefer recent content
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(self.search_base_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._format_search_results(data.get('items', []))
                    else:
                        logger.error(f"Search API error: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return []
    
    def _format_search_results(self, items: List[Dict]) -> List[Dict]:
        """Format Google search results into standard document format"""
        formatted = []
        
        for item in items:
            formatted_doc = {
                'id': f"web_{hash(item.get('link', ''))}",
                'title': item.get('title', ''),
                'content': item.get('snippet', ''),
                'url': item.get('link', ''),
                'domain': self._extract_domain(item.get('link', '')),
                'type': 'web_search',
                'date': item.get('pagemap', {}).get('metatags', [{}])[0].get('date'),
                'relevance_score': 0.8,  # Default, will be refined
                'metadata': {
                    'source': 'google_search',
                    'display_link': item.get('displayLink', ''),
                    'formatted_url': item.get('formattedUrl', '')
                }
            }
            formatted.append(formatted_doc)
        
        return formatted
    
    def _filter_tax_sources(self, results: List[Dict]) -> List[Dict]:
        """Filter results to prioritize authoritative tax sources"""
        
        # Authoritative domains (highest priority)
        authoritative_domains = {
            'irs.gov': 1.0,
            'treasury.gov': 0.95,
            'congress.gov': 0.9,
            'supremecourt.gov': 0.9,
        }
        
        # Professional tax sources (high priority)
        professional_domains = {
            'taxnotes.com': 0.85,
            'bna.com': 0.8,
            'checkpoint.riag.com': 0.8,
            'tax.thomsonreuters.com': 0.8,
        }
        
        # Legal databases (medium-high priority)
        legal_domains = {
            'westlaw.com': 0.75,
            'lexis.com': 0.75,
            'justia.com': 0.7,
        }
        
        filtered = []
        for result in results:
            domain = result.get('domain', '')
            
            # Assign authority score
            if domain in authoritative_domains:
                result['authority_score'] = authoritative_domains[domain]
                filtered.append(result)
            elif domain in professional_domains:
                result['authority_score'] = professional_domains[domain]
                filtered.append(result)
            elif domain in legal_domains:
                result['authority_score'] = legal_domains[domain]
                filtered.append(result)
            elif any(term in domain for term in ['tax', 'accounting', 'legal']):
                result['authority_score'] = 0.6
                filtered.append(result)
        
        return filtered
    
    def _rank_by_authority(self, results: List[Dict]) -> List[Dict]:
        """Rank results by authority and relevance"""
        
        # Calculate combined score
        for result in results:
            authority = result.get('authority_score', 0.5)
            relevance = result.get('relevance_score', 0.5)
            
            # Boost recent content
            date_boost = 1.0
            if result.get('date'):
                # Simple date boost logic
                date_boost = 1.1
            
            result['combined_score'] = (authority * 0.6 + relevance * 0.4) * date_boost
        
        # Sort by combined score
        return sorted(results, key=lambda x: x.get('combined_score', 0), reverse=True)
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc.lower()
        except:
            return ""
    
    def _calculate_confidence(self, documents: List[Dict]) -> float:
        """Calculate confidence based on source authority and result count"""
        if not documents:
            return 0.0
        
        # Average authority score
        authority_scores = [doc.get('authority_score', 0.5) for doc in documents]
        avg_authority = sum(authority_scores) / len(authority_scores)
        
        # Document count factor
        count_factor = min(len(documents) / 5, 1.0)
        
        return avg_authority * count_factor