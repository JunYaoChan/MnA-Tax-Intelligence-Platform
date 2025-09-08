from abc import ABC, abstractmethod
import logging
import time
from typing import Dict, Any, Callable, Optional, List
from models.results import RetrievalResult
from models.state import AgentState
from config.settings import Settings

class BaseAgent(ABC):
    def __init__(self, name: str, settings: Settings, vector_store=None, function_tools: Optional[Dict[str, Callable]] = None):
        self.name = name
        self.settings = settings
        self.vector_store = vector_store
        self.function_tools = function_tools or {}
        self.logger = logging.getLogger(f"{__name__}.{name}")

    @abstractmethod
    async def process(self, state: AgentState) -> RetrievalResult:
        pass

    async def validate_confidence(self, result: RetrievalResult) -> bool:
        return result.confidence >= self.settings.confidence_threshold

    def log_performance(self, start_time: float, result: RetrievalResult):
        duration = time.time() - start_time
        self.logger.info(
            f"Agent {self.name} completed in {duration:.2f}s "
            f"with confidence {result.confidence:.2%}"
        )

    async def should_use_function_tools(self, query: str, internal_results: list) -> bool:
        """
        Determine if function tools should be used based on query and internal results

        Args:
            query: The search query
            internal_results: Results from internal vector search

        Returns:
            bool: Whether to use function tools
        """
        # Use function tools if:
        # 1. No internal results found
        # 2. Internal results have low confidence
        # 3. Query requires recent/external information
        # 4. Internal results don't cover the query sufficiently

        if not internal_results:
            self.logger.info("No internal results found, using function tools")
            return True

        # Check average confidence of internal results
        avg_confidence = sum(doc.get('relevance_score', 0) for doc in internal_results) / len(internal_results)

        if avg_confidence < self.settings.confidence_threshold:
            self.logger.info(f"Internal confidence too low ({avg_confidence:.2f}), using function tools")
            return True

        # Check if query suggests need for external data
        external_keywords = [
            'recent', 'new', 'current', 'latest', 'federal register', 'proposed',
            'pending', 'surrogate', 'status', 'filings', 'court cases'
        ]

        query_lower = query.lower()
        if any(keyword in query_lower for keyword in external_keywords):
            self.logger.info("Query suggests need for external data, using function tools")
            return True

        # Check if we have sufficient coverage
        if len(internal_results) < 2:
            self.logger.info("Insufficient internal results, using function tools")
            return True

        self.logger.info("Using internal results, function tools not needed")
        return False

    async def call_function_tools(self, query: str, context: Dict = None) -> List[Dict]:
        """
        Call relevant function tools to enhance results

        Args:
            query: The search query
            context: Additional context for the query

        Returns:
            List of enhanced results from function tools
        """
        enhanced_results = []
        context = context or {}

        # Determine which tools to use based on agent type
        tool_mapping = {
            'CaseLawAgent': ['brave_search', 'irs_api', 'llm_enhancer'],
            'RegulationAgent': ['federal_register', 'ecfr_api', 'llm_enhancer'],
            'PrecedentAgent': ['neo4j_precedent_search', 'brave_search', 'llm_enhancer'],
            'ExpertAgent': ['brave_search', 'irs_api', 'llm_enhancer']
        }

        agent_tools = tool_mapping.get(self.name, ['llm_enhancer'])

        for tool_name in agent_tools:
            if tool_name not in self.function_tools:
                continue

            try:
                self.logger.info(f"Calling function tool: {tool_name}")

                if tool_name == 'brave_search':
                    # Web search with better query
                    search_query = f"tax {self.name.replace('Agent', '').lower()} {query}"
                    result = await self.function_tools[tool_name](search_query)
                    enhanced_results.append({
                        'source': tool_name,
                        'data': result,
                        'type': 'web_search'
                    })

                elif tool_name == 'llm_enhancer':
                    # LLM enhancement (pass empty list if no internal docs)
                    internal_docs = context.get('internal_documents', [])
                    enhanced_docs = await self.function_tools[tool_name](
                        internal_docs, query, self.name
                    )
                    enhanced_results.append({
                        'source': tool_name,
                        'data': enhanced_docs,
                        'type': 'llm_enhanced'
                    })

                elif tool_name == 'irs_api':
                    result = await self.function_tools[tool_name](query)
                    enhanced_results.append({
                        'source': tool_name,
                        'data': result,
                        'type': 'irs_api'
                    })

                elif tool_name == 'federal_register':
                    result = await self.function_tools[tool_name](query)
                    enhanced_results.append({
                        'source': tool_name,
                        'data': result,
                        'type': 'federal_register'
                    })

                elif tool_name == 'ecfr_api':
                    # Extract title/section from query
                    result = await self.function_tools[tool_name]("26", query)
                    enhanced_results.append({
                        'source': tool_name,
                        'data': result,
                        'type': 'ecfr'
                    })

                elif tool_name == 'neo4j_precedent_search':
                    result = await self.function_tools[tool_name](query)
                    enhanced_results.append({
                        'source': tool_name,
                        'data': result,
                        'type': 'precedent_graph'
                    })

            except Exception as e:
                self.logger.error(f"Error calling function tool {tool_name}: {e}")
                continue

        return enhanced_results
