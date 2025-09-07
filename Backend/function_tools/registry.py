from typing import Dict, Callable, Any
import logging
from .brave_search import BraveSearchTool
from .llm_enhancer import LLMEnhancerTool
from .irs_api import IRSAPITool

logger = logging.getLogger(__name__)

class FunctionToolRegistry:
    """Registry for managing function tools"""
    
    def __init__(self, settings):
        self.settings = settings
        self._tools = {}
        self._initialized = False
    
    async def initialize(self):
        """Initialize all function tools"""
        if self._initialized:
            return
        
        try:
            # Initialize Brave Search tool
            if hasattr(self.settings, 'brave_search_api_key') and self.settings.brave_search_api_key:
                brave_tool = BraveSearchTool(self.settings.brave_search_api_key)
                self._tools['brave_search'] = self._create_brave_search_function(brave_tool)
            
            # Initialize LLM Enhancer tool
            if hasattr(self.settings, 'openai_api_key') and self.settings.openai_api_key:
                llm_tool = LLMEnhancerTool(self.settings.openai_api_key)
                self._tools['llm_enhancer'] = self._create_llm_enhancer_function(llm_tool)
            
            # Initialize IRS API tool
            irs_tool = IRSAPITool()
            self._tools['irs_api'] = self._create_irs_api_function(irs_tool)
            
            # Add other specialized tools as needed
            self._add_specialized_tools()
            
            self._initialized = True
            logger.info(f"Initialized {len(self._tools)} function tools")
            
        except Exception as e:
            logger.error(f"Failed to initialize function tools: {e}")
            raise
    
    def get_tools_for_agent(self, agent_name: str) -> Dict[str, Callable]:
        """Get relevant function tools for a specific agent"""
        if not self._initialized:
            raise RuntimeError("Function tools not initialized")
        
        # Return all tools for now, but this could be customized per agent
        return self._tools.copy()
    
    def _create_brave_search_function(self, brave_tool: BraveSearchTool) -> Callable:
        """Create Brave search function"""
        async def brave_search(query: str, **kwargs) -> Dict[str, Any]:
            async with brave_tool:
                return await brave_tool.search(query, **kwargs)
        
        return brave_search
    
    def _create_llm_enhancer_function(self, llm_tool: LLMEnhancerTool) -> Callable:
        """Create LLM enhancer function"""
        async def llm_enhancer(documents: list, query: str, agent_type: str) -> list:
            return await llm_tool.enhance_documents(documents, query, agent_type)
        
        return llm_enhancer
    
    def _create_irs_api_function(self, irs_tool: IRSAPITool) -> Callable:
        """Create IRS API function"""
        async def irs_api(query: str, document_types: list = None) -> Dict[str, Any]:
            async with irs_tool:
                return await irs_tool.search_rulings(query, document_types)
        
        return irs_api
    
    def _add_specialized_tools(self):
        """Add additional specialized function tools"""
        
        # Mock Federal Register tool
        async def federal_register(query: str, document_types: list = None, agencies: list = None):
            # Mock implementation
            return [{
                "document_number": "2024-00123",
                "title": f"Federal Register document for {query}",
                "abstract": f"This document addresses {query}...",
                "html_url": "https://federalregister.gov/documents/2024/01/15/2024-00123",
                "publication_date": "2024-01-15",
                "effective_on": "2024-03-15",
                "type": "final_rule",
                "agency_names": ["Internal Revenue Service"]
            }]
        
        self._tools['federal_register'] = federal_register
        
        # Mock eCFR API tool
        async def ecfr_api(title: str, query: str, sections: list = None):
            # Mock implementation
            return [{
                "section_number": "1.338-1",
                "subject": "General principles",
                "content": f"Content related to {query}...",
                "url": f"https://ecfr.gov/current/title-{title}/section-1.338-1",
                "title": title,
                "part": "1",
                "last_updated": "2024-01-01"
            }]
        
        self._tools['ecfr_api'] = ecfr_api
        
        # Mock Neo4j precedent search
        async def neo4j_precedent_search(query: str, entities: list = None, deal_size_range: dict = None):
            # Mock implementation
            return [{
                "deal": {
                    "id": "deal_001",
                    "title": f"Transaction involving {query}",
                    "description": f"This deal involved {query}...",
                    "value": "500M",
                    "type": "acquisition",
                    "date": "2023-06-15",
                    "parties": ["Company A", "Company B"]
                },
                "election": {
                    "section": entities[0] if entities else "338",
                    "type": "338(h)(10) election"
                }
            }]
        
        self._tools['neo4j_precedent_search'] = neo4j_precedent_search