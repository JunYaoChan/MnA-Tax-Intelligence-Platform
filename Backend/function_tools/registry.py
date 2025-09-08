# Backend/function_tools/registry.py
from typing import Dict, Callable, Any, List
import logging
import asyncio
from datetime import datetime
from .brave_search import BraveSearchTool
from .llm_enhancer import LLMEnhancerTool
from .irs_api import IRSAPITool

logger = logging.getLogger(__name__)

class FunctionToolRegistry:
    """Enhanced registry for managing function tools with proper lifecycle"""
    
    def __init__(self, settings):
        self.settings = settings
        self._tools = {}
        self._tool_instances = {}
        self._initialized = False
        self._cleanup_tasks = []
    
    async def initialize(self):
        """Initialize all function tools"""
        if self._initialized:
            return
        
        try:
            # Initialize Brave Search tool
            if (hasattr(self.settings, 'brave_search_api_key') and 
                self.settings.brave_search_api_key and 
                self.settings.enable_external_search):
                
                brave_tool = BraveSearchTool(self.settings.brave_search_api_key)
                self._tool_instances['brave_search'] = brave_tool
                self._tools['brave_search'] = self._create_brave_search_function(brave_tool)
                logger.info("Initialized Brave Search tool")
            
            # Initialize LLM Enhancer tool
            if (hasattr(self.settings, 'openai_api_key') and 
                self.settings.openai_api_key and 
                self.settings.enable_llm_enhancement):
                
                llm_tool = LLMEnhancerTool(self.settings.openai_api_key)
                self._tool_instances['llm_enhancer'] = llm_tool
                self._tools['llm_enhancer'] = self._create_llm_enhancer_function(llm_tool)
                logger.info("Initialized LLM Enhancer tool")
            
            # Initialize IRS API tool
            irs_tool = IRSAPITool()
            self._tool_instances['irs_api'] = irs_tool
            self._tools['irs_api'] = self._create_irs_api_function(irs_tool)
            logger.info("Initialized IRS API tool")
            
            # Add other specialized tools
            self._add_specialized_tools()
            
            self._initialized = True
            logger.info(f"Initialized {len(self._tools)} function tools")
            
        except Exception as e:
            logger.error(f"Failed to initialize function tools: {e}")
            await self.cleanup()
            raise
    
    def _create_brave_search_function(self, brave_tool: BraveSearchTool) -> Callable:
        """Create Brave Search function with enhanced error handling"""
        
        async def brave_search(
            query: str, 
            count: int = 10, 
            freshness: str = "month",
            site: str = None,
            **kwargs
        ) -> Dict[str, Any]:
            """
            Search the web using Brave Search API
            
            Args:
                query: Search query (max 400 characters)
                count: Number of results (1-20)
                freshness: Time filter (all, day, week, month, year)
                site: Restrict search to specific site
            """
            try:
                # Validate inputs
                if not query or not query.strip():
                    return {"error": "Query cannot be empty", "web": {"results": []}}
                
                if count < 1 or count > 20:
                    count = min(max(count, 1), 20)
                
                valid_freshness = ["all", "day", "week", "month", "year"]
                if freshness not in valid_freshness:
                    freshness = "month"
                
                search_params = {
                    "freshness": freshness,
                    **kwargs
                }
                
                if site:
                    search_params["site"] = site
                
                # Perform search
                result = await brave_tool.search(query, count, **search_params)
                
                # Add metadata
                result["metadata"] = {
                    "tool": "brave_search",
                    "query_length": len(query),
                    "timestamp": datetime.now().isoformat(),
                    "parameters": {
                        "count": count,
                        "freshness": freshness,
                        "site": site
                    }
                }
                
                return result
                
            except Exception as e:
                logger.error(f"Brave search function error: {e}")
                return {
                    "error": str(e),
                    "web": {"results": []},
                    "metadata": {
                        "tool": "brave_search",
                        "error": True,
                        "timestamp": datetime.now().isoformat()
                    }
                }
        
        return brave_search
    
    def _create_llm_enhancer_function(self, llm_tool: LLMEnhancerTool) -> Callable:
        """Create LLM Enhancer function"""
        
        async def llm_enhance(
            documents: List[Dict[str, Any]], 
            query: str,
            enhancement_type: str = "relevance",
            **kwargs
        ) -> List[Dict[str, Any]]:
            """
            Enhance documents using LLM analysis
            
            Args:
                documents: List of documents to enhance
                query: Original query for context
                enhancement_type: Type of enhancement (relevance, summary, extraction)
            """
            try:
                if not documents:
                    return documents
                
                enhanced = await llm_tool.enhance_documents(
                    documents, query, enhancement_type, **kwargs
                )
                
                return enhanced
                
            except Exception as e:
                logger.error(f"LLM enhancer function error: {e}")
                # Return original documents on error
                return documents
        
        return llm_enhance
    
    def _create_irs_api_function(self, irs_tool: IRSAPITool) -> Callable:
        """Create IRS API function"""
        
        async def irs_search(
            query: str,
            document_types: List[str] = None,
            limit: int = 10,
            **kwargs
        ) -> Dict[str, Any]:
            """
            Search IRS documents and regulations
            
            Args:
                query: Search query
                document_types: Types of documents to search
                limit: Maximum number of results
            """
            try:
                result = await irs_tool.search(query, document_types, limit, **kwargs)
                return result
                
            except Exception as e:
                logger.error(f"IRS API function error: {e}")
                return {"documents": [], "error": str(e)}
        
        return irs_search
    
    def _add_specialized_tools(self):
        """Add specialized tools for tax research"""
        
        # Add Federal Register tool
        async def federal_register_search(query: str, **kwargs) -> Dict[str, Any]:
            """Search Federal Register for regulations"""
            # Implementation for Federal Register API
            return {"documents": []}
        
        self._tools['federal_register'] = federal_register_search
        
        # Add SEC EDGAR tool for public company filings
        async def sec_edgar_search(query: str, **kwargs) -> Dict[str, Any]:
            """Search SEC EDGAR database"""
            # Implementation for SEC EDGAR API
            return {"filings": []}
        
        self._tools['sec_edgar'] = sec_edgar_search
    
    def get_tools_for_agent(self, agent_name: str) -> Dict[str, Callable]:
        """Get appropriate tools for a specific agent"""
        if not self._initialized:
            raise RuntimeError("Function tools not initialized")
        
        # Agent-specific tool mappings
        agent_tool_mappings = {
            "CaseLawAgent": [
                "brave_search", "llm_enhancer", "irs_api"
            ],
            "RegulationAgent": [
                "brave_search", "llm_enhancer", "federal_register", "irs_api"
            ],
            "PrecedentAgent": [
                "brave_search", "llm_enhancer", "sec_edgar"
            ],
            "ExpertAgent": [
                "brave_search", "llm_enhancer"
            ]
        }
        
        tool_names = agent_tool_mappings.get(agent_name, ["brave_search"])
        return {name: self._tools[name] for name in tool_names if name in self._tools}
    
    def get_all_tools(self) -> Dict[str, Callable]:
        """Get all available tools"""
        if not self._initialized:
            raise RuntimeError("Function tools not initialized")
        return self._tools.copy()
    
    def get_tool(self, tool_name: str) -> Callable:
        """Get a specific tool by name"""
        if not self._initialized:
            raise RuntimeError("Function tools not initialized")
        return self._tools.get(tool_name)
    
    async def health_check(self) -> Dict[str, bool]:
        """Check health of all tools"""
        health_status = {}
        
        for tool_name, tool_instance in self._tool_instances.items():
            try:
                if hasattr(tool_instance, 'health_check'):
                    health_status[tool_name] = await tool_instance.health_check()
                else:
                    health_status[tool_name] = True
            except Exception as e:
                logger.error(f"Health check failed for {tool_name}: {e}")
                health_status[tool_name] = False
        
        return health_status
    
    async def cleanup(self):
        """Cleanup all tool resources"""
        logger.info("Cleaning up function tools...")
        
        for tool_name, tool_instance in self._tool_instances.items():
            try:
                if hasattr(tool_instance, '_close_session'):
                    await tool_instance._close_session()
                elif hasattr(tool_instance, 'close'):
                    await tool_instance.close()
                logger.debug(f"Cleaned up {tool_name}")
            except Exception as e:
                logger.error(f"Error cleaning up {tool_name}: {e}")
        
        # Cancel any pending tasks
        for task in self._cleanup_tasks:
            if not task.done():
                task.cancel()
        
        self._tool_instances.clear()
        self._tools.clear()
        self._initialized = False
        
        logger.info("Function tools cleanup completed")

# Singleton instance
_registry_instance = None

async def get_function_tool_registry(settings) -> FunctionToolRegistry:
    """Get or create the function tool registry singleton"""
    global _registry_instance
    
    if _registry_instance is None:
        _registry_instance = FunctionToolRegistry(settings)
        await _registry_instance.initialize()
    
    return _registry_instance

async def cleanup_function_tools():
    """Cleanup function tools on shutdown"""
    global _registry_instance
    
    if _registry_instance:
        await _registry_instance.cleanup()
        _registry_instance = None
