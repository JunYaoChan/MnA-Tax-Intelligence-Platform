# Backend/function_tools/brave_search.py
import aiohttp
import asyncio
from typing import List, Dict, Any, Optional, Union
import logging
import json
from datetime import datetime
import re
import hashlib
import time

logger = logging.getLogger(__name__)

class BraveSearchTool:
    """Enhanced Brave Search API integration with proper session management"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.search.brave.com/res/v1/web/search"):
        self.api_key = api_key
        self.base_url = base_url
        self.session = None
        self._session_lock = asyncio.Lock()
        self.max_query_length = 400
        self.max_retries = 3
        
    async def __aenter__(self):
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._close_session()
    
    async def _ensure_session(self):
        """Ensure we have a valid session"""
        async with self._session_lock:
            if not self.session or self.session.closed:
                if self.session and not self.session.closed:
                    await self.session.close()
                self.session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=30),
                    connector=aiohttp.TCPConnector(limit=10, limit_per_host=5)
                )
    
    async def _close_session(self):
        """Properly close the session"""
        async with self._session_lock:
            if self.session and not self.session.closed:
                await self.session.close()
                self.session = None
    
    def _validate_and_truncate_query(self, query: str) -> str:
        """Validate and truncate query to fit API limits"""
        # Remove extra whitespace
        query = ' '.join(query.split())
        
        if len(query) <= self.max_query_length:
            return query
        
        logger.warning(f"Query too long ({len(query)} chars), truncating to {self.max_query_length}")
        
        # Try to truncate at word boundary
        truncated = query[:self.max_query_length]
        last_space = truncated.rfind(' ')
        if last_space > self.max_query_length * 0.8:  # If we can save 80% of the query
            truncated = truncated[:last_space]
        else:
            truncated = query[:self.max_query_length - 3] + "..."
        
        return truncated
    
    def _split_complex_query(self, query: str, max_splits: int = 3) -> List[str]:
        """Split a complex query into smaller, focused queries"""
        if len(query) <= self.max_query_length:
            return [query]
        
        # Extract key terms and concepts
        key_terms = self._extract_key_terms(query)
        
        # Create focused sub-queries
        sub_queries = []
        current_query = ""
        
        for term in key_terms:
            test_query = f"{current_query} {term}".strip()
            if len(test_query) <= self.max_query_length:
                current_query = test_query
            else:
                if current_query:
                    sub_queries.append(current_query)
                current_query = term
                
                if len(sub_queries) >= max_splits:
                    break
        
        if current_query and len(sub_queries) < max_splits:
            sub_queries.append(current_query)
        
        return sub_queries or [self._validate_and_truncate_query(query)]
    
    def _extract_key_terms(self, query: str) -> List[str]:
        """Extract key terms from a complex query"""
        # Remove common words and extract important terms
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'what', 'how', 'when', 'where', 'why', 'which', 'that', 'this', 'these', 'those'
        }
        
        # Extract phrases in quotes
        quoted_phrases = re.findall(r'"([^"]*)"', query)
        
        # Extract important terms (capitalized, technical terms, numbers)
        words = re.findall(r'\b\w+\b', query)
        key_terms = []
        
        # Add quoted phrases first
        key_terms.extend(quoted_phrases)
        
        # Add important individual terms
        for word in words:
            if (len(word) > 3 and 
                word.lower() not in stop_words and
                (word[0].isupper() or word.isdigit() or len(word) > 6)):
                key_terms.append(word)
        
        return key_terms[:10]  # Limit to top 10 terms
    
    async def search(self, query: str, count: int = 10, **kwargs) -> Dict[str, Any]:
        """
        Perform search using Brave Search API with enhanced error handling
        
        Args:
            query: Search query
            count: Number of results to return
            **kwargs: Additional search parameters
        """
        # Validate query length
        validated_query = self._validate_and_truncate_query(query)
        
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.api_key,
            "User-Agent": "TaxRAG/1.0"
        }
        
        params = {
            "q": validated_query,
            "count": min(count, 20),  # Brave API limit
            "search_lang": "en",
            "country": "us",
            "safesearch": "moderate",
            "freshness": kwargs.get('freshness', 'month'),
            "text_decorations": "false",
            "result_filter": kwargs.get('result_filter', 'web'),
        }
        
        # Add optional parameters
        if kwargs.get('site'):
            params["site"] = kwargs['site']
        
        await self._ensure_session()
        
        for attempt in range(self.max_retries):
            try:
                async with self.session.get(
                    self.base_url, 
                    headers=headers, 
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Brave search successful: {len(data.get('web', {}).get('results', []))} results")
                        return data
                    
                    elif response.status == 422:
                        error_text = await response.text()
                        logger.error(f"Brave Search validation error (422): {error_text}")
                        
                        # Try to extract the actual error
                        try:
                            error_data = json.loads(error_text)
                            if "query" in error_data.get("error", {}).get("meta", {}).get("errors", [{}])[0].get("loc", []):
                                # Query issue - try splitting
                                return await self.search_with_split_query(query, count, **kwargs)
                        except:
                            pass
                        
                        return {"web": {"results": []}}
                    
                    elif response.status == 429:
                        wait_time = 2 ** attempt
                        logger.warning(f"Rate limited, waiting {wait_time} seconds...")
                        await asyncio.sleep(wait_time)
                        continue
                    
                    else:
                        error_text = await response.text()
                        logger.error(f"Brave Search API error {response.status}: {error_text}")
                        
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(1)
                            continue
                        
                        return {"web": {"results": []}}
                        
            except aiohttp.ClientError as e:
                logger.error(f"Client error on attempt {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1)
                    await self._ensure_session()  # Recreate session
                    continue
                return {"web": {"results": []}}
            
            except Exception as e:
                logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1)
                    continue
                return {"web": {"results": []}}
        
        return {"web": {"results": []}}
    
    async def search_with_split_query(self, query: str, count: int = 10, **kwargs) -> Dict[str, Any]:
        """Search using split queries and merge results"""
        sub_queries = self._split_complex_query(query)
        logger.info(f"Splitting complex query into {len(sub_queries)} sub-queries")
        
        all_results = []
        seen_urls = set()
        
        for i, sub_query in enumerate(sub_queries):
            logger.info(f"Searching sub-query {i+1}: {sub_query}")
            
            try:
                result = await self.search(sub_query, count=max(count // len(sub_queries), 3), **kwargs)
                
                for item in result.get('web', {}).get('results', []):
                    url = item.get('url', '')
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_results.append(item)
                        
                        if len(all_results) >= count:
                            break
                
                # Small delay between requests
                if i < len(sub_queries) - 1:
                    await asyncio.sleep(0.5)
                    
            except Exception as e:
                logger.error(f"Error searching sub-query '{sub_query}': {e}")
                continue
        
        return {
            "web": {
                "results": all_results[:count]
            },
            "query_info": {
                "original_query": query,
                "sub_queries": sub_queries,
                "total_results": len(all_results)
            }
        }
    
    async def health_check(self) -> bool:
        """Check if the Brave Search API is accessible"""
        try:
            result = await self.search("test", count=1)
            return len(result.get('web', {}).get('results', [])) >= 0
        except Exception:
            return False
