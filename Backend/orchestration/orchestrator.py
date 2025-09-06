from typing import Dict
import logging
from langgraph.graph import StateGraph, END
from models.state import AgentState
from models.enums import QueryComplexity
from agents import (
    QueryPlanningAgent, CaseLawAgent, 
    RegulationAgent, PrecedentAgent, ExpertAgent, BaseAgent
)
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
        """Initialize all agents with their dependencies."""
        vector_store = SupabaseVectorStore(self.settings)
        neo4j_client = Neo4jClient(self.settings)
        knowledge_base = KnowledgeBase(vector_store)
        
        return {
            "QueryPlanningAgent": QueryPlanningAgent(self.settings),
            "CaseLawAgent": CaseLawAgent(self.settings, vector_store),
            "RegulationAgent": RegulationAgent(self.settings, vector_store),
            "PrecedentAgent": PrecedentAgent(self.settings, neo4j_client),
            "ExpertAgent": ExpertAgent(self.settings, knowledge_base)
        }
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow with phases and edges."""
        workflow = StateGraph(AgentState)
        
        # Add nodes for each phase
        workflow.add_node("query_processing", self.phase_executor.phase1_query_processing)
        workflow.add_node("agent_coordination", self.phase_executor.phase2_coordination)
        workflow.add_node("parallel_retrieval", self.phase_executor.phase3_retrieval)
        workflow.add_node("synthesis", self.phase_executor.phase4_synthesis)
        
        # Define edges
        workflow.add_edge("query_processing", "agent_coordination")
        workflow.add_edge("agent_coordination", "parallel_retrieval")
        workflow.add_edge("parallel_retrieval", "synthesis")
        workflow.add_edge("synthesis", END)
        
        # Set entry point
        workflow.set_entry_point("query_processing")
        
        return workflow.compile()
    
    async def process_query(self, query: str) -> Dict:
        """Main entry point for processing a query."""
        initial_state = AgentState(
            query=query,
            complexity=QueryComplexity.MODERATE  # Initial estimate
        )
        
        final_state = await self.workflow.ainvoke(initial_state)
        
        return final_state.get('metadata', {}).get('final_output', {})