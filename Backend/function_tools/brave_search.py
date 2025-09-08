import aiohttp
import asyncio
from typing import List, Dict, Any, Optional
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class BraveSearchTool:
    """Function tool for Brave Search API integration"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.search.brave.com/res/v1/web/search"):
        self.api_key = api_key
        self.base_url = base_url
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def search(self, query: str, count: int = 10, **kwargs) -> Dict[str, Any]:
        """
        Perform search using Brave Search API
        
        Args:
            query: Search query
            count: Number of results to return
            **kwargs: Additional search parameters
        """
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.api_key
        }
        
        params = {
            "q": query,
            "count": count,
            "search_lang": "en",
            "country": "us",
            "safesearch": "moderate",
            "freshness": kwargs.get('freshness', 'all'),  # all, day, week, month, year
            "text_decorations": "false",
            "result_filter": kwargs.get('result_filter', 'web'),  # web, news, images
        }
        
        # Add optional parameters
        if kwargs.get('site'):
            params["site"] = kwargs['site']
        
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            async with self.session.get(self.base_url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    logger.error(f"Brave Search API error: {response.status}")
                    error_text = await response.text()
                    logger.error(f"Error details: {error_text}")
                    return {"web": {"results": []}}
                    
        except Exception as e:
            logger.error(f"Brave search failed: {e}")
            return {"web": {"results": []}}
