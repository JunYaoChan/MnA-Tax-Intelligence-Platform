from typing import Dict, List
import logging
from langgraph.graph import StateGraph, END
from models.state import AgentState
from models.enums import QueryComplexity
from agents import (
    QueryPlanningAgent, CaseLawAgent, 
    RegulationAgent, PrecedentAgent, ExpertAgent, BaseAgent
)
from agents.web_search import WebSearchAgent  # NEW
from agents.irs_api import IRSAPIAgent  # NEW
from config.settings import Settings
from database.vector_store import KnowledgeBase
from database.supabase_client import SupabaseVectorStore
from database.neo4j_client import Neo4jClient
from .phases import PhaseExecutor


logger = logging.getLogger(__name__)

class LangGraphOrchestrator:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.agents = self._initialize_agents()
        self.phase_executor = PhaseExecutor(self.agents, self.settings)
        self.workflow = self._build_workflow()
        
    def _initialize_agents(self) -> Dict[str, BaseAgent]:
        """Initialize all agents with their dependencies including external agents."""
        
        # Initialize database connections
        vector_store = SupabaseVectorStore(self.settings)
        neo4j_client = Neo4jClient(self.settings)
        knowledge_base = KnowledgeBase(vector_store)
        
        # Initialize all agents - internal and external
        agents = {
            # Planning agent
            "QueryPlanningAgent": QueryPlanningAgent(self.settings),
            
            # Internal database agents
            "CaseLawAgent": CaseLawAgent(self.settings, vector_store),
            "RegulationAgent": RegulationAgent(self.settings, vector_store),
            "PrecedentAgent": PrecedentAgent(self.settings, neo4j_client),
            "ExpertAgent": ExpertAgent(self.settings, knowledge_base),
            
            # NEW: External data sourcing agents
            "WebSearchAgent": WebSearchAgent(self.settings),
            "IRSAPIAgent": IRSAPIAgent(self.settings)
        }
        
        logger.info(f"Initialized {len(agents)} agents: {list(agents.keys())}")
        return agents
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow with phases and edges."""
        workflow = StateGraph(AgentState)
        
        # Add nodes for each phase
        workflow.add_node("query_processing", self.phase_executor.phase1_query_processing)
        workflow.add_node("agent_coordination", self.phase_executor.phase2_coordination)
        workflow.add_node("parallel_retrieval", self.phase_executor.phase3_retrieval)
        workflow.add_node("quality_check", self.phase_executor.quality_check_node)  # NEW
        workflow.add_node("external_enrichment", self.phase_executor.phase3b_external_enrichment)  # NEW
        workflow.add_node("synthesis", self.phase_executor.phase4_synthesis)
        
        # Define edges - updated flow
        workflow.add_edge("query_processing", "agent_coordination")
        workflow.add_edge("agent_coordination", "parallel_retrieval")
        workflow.add_edge("parallel_retrieval", "quality_check")
        
        # Conditional edge: if insufficient results, try external sources
        workflow.add_conditional_edges(
            "quality_check",
            self._should_use_external_sources,
            {
                "external_enrichment": "external_enrichment",
                "synthesis": "synthesis"
            }
        )
        
        workflow.add_edge("external_enrichment", "synthesis")
        workflow.add_edge("synthesis", END)
        
        # Set entry point
        workflow.set_entry_point("query_processing")
        
        return workflow.compile()
    
    def _should_use_external_sources(self, state: AgentState) -> str:
        """Determine if external sources should be used based on results quality"""
        
        # Check if we have sufficient high-quality results
        sufficient_results = len(state.retrieved_documents) >= 3
        high_confidence = False
        
        if state.confidence_scores:
            avg_confidence = sum(state.confidence_scores.values()) / len(state.confidence_scores)
            high_confidence = avg_confidence >= self.settings.confidence_threshold
        
        # Use external sources if:
        # 1. Insufficient internal results, OR
        # 2. Low confidence from internal sources, OR  
        # 3. Query explicitly asks for recent/current information
        
        query_asks_for_current = any(
            term in state.query.lower() 
            for term in ['current', 'recent', 'latest', '2024', '2025', 'new', 'updated']
        )
        
        if not sufficient_results or not high_confidence or query_asks_for_current:
            logger.info("Using external sources for enrichment")
            return "external_enrichment"
        else:
            logger.info("Sufficient internal results found, skipping external sources")
            return "synthesis"
    
    async def process_query(self, query: str) -> Dict:
        """Main entry point for processing a query."""
        initial_state = AgentState(
            query=query,
            complexity=QueryComplexity.MODERATE  # Initial estimate
        )
        
        try:
            final_state = await self.workflow.ainvoke(initial_state)
            
            # Extract final output
            final_output = final_state.get('metadata', {}).get('final_output', {})
            
            # Add processing metadata
            final_output['processing_metadata'] = {
                'agents_used': list(final_state.get('agent_outputs', {}).keys()),
                'external_sources_used': self._get_external_sources_used(final_state),
                'total_documents': len(final_state.get('retrieved_documents', [])),
                'workflow_path': self._get_workflow_path(final_state)
            }
            
            return final_output
            
        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'query': query,
                'message': 'An error occurred while processing your query. Please try again.'
            }
    
    def _get_external_sources_used(self, state: AgentState) -> List[str]:
        """Get list of external sources that were used"""
        external_sources = []
        
        for agent_name in state.get('agent_outputs', {}):
            if agent_name in ['WebSearchAgent', 'IRSAPIAgent']:
                external_sources.append(agent_name)
        
        return external_sources
    
    def _get_workflow_path(self, state: AgentState) -> List[str]:
        """Get the path taken through the workflow"""
        # This would be more sophisticated in a real implementation
        # For now, return a basic path based on what was executed
        
        path = ['query_processing', 'agent_coordination', 'parallel_retrieval', 'quality_check']
        
        # Check if external enrichment was used
        external_agents_used = self._get_external_sources_used(state)
        if external_agents_used:
            path.append('external_enrichment')
        
        path.append('synthesis')
        
        return path