# Backend/orchestration/orchestrator.py
import asyncio
import time
import logging
from typing import List, Dict, Any, Optional
from models.state import AgentState, QueryComplexity
from models.results import RetrievalResult
from models.synthesis import SynthesisResult
from agents.query_planning import QueryPlanningAgent
from agents.case_law import CaseLawAgent
from agents.regulation import RegulationAgent
from agents.precedent import PrecedentAgent
from agents.expert import ExpertAgent
from function_tools.registry import FunctionToolRegistry
from services.llm_synthesis_service import LLMSynthesisService
from database.supabase_client import SupabaseVectorStore
from database.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)

class RAGOrchestrator:
    """
    Orchestrator implementing the 5-step RAG pipeline:
    1. User Query Submission
    2. Data Retrieval from Vector Database
    3. External Data Sourcing with Function Tools
    4. LLM Response Generation
    5. Agent-Driven Refinement
    """
    
    def __init__(self, settings, vector_store: SupabaseVectorStore, neo4j_client: Neo4jClient):
        self.settings = settings
        self.vector_store = vector_store
        self.neo4j = neo4j_client
        self.function_tools = FunctionToolRegistry(settings)
        self.llm_synthesis = LLMSynthesisService(settings)
        
        # Initialize agents with function tools
        self.agents = {}
        
    async def initialize(self):
        """Initialize the orchestrator and all components"""
        try:
            # Initialize function tools first
            await self.function_tools.initialize()
            
            # Initialize agents with function tools
            await self._initialize_agents()
            
            logger.info("RAG Orchestrator initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize RAG Orchestrator: {e}")
            raise
    
    async def _initialize_agents(self):
        """Initialize all agents with function tools"""
        # Get function tools for each agent type
        case_law_tools = self.function_tools.get_tools_for_agent("CaseLawAgent")
        regulation_tools = self.function_tools.get_tools_for_agent("RegulationAgent")
        precedent_tools = self.function_tools.get_tools_for_agent("PrecedentAgent")
        expert_tools = self.function_tools.get_tools_for_agent("ExpertAgent")
        
        # Initialize agents
        self.agents = {
            "QueryPlanningAgent": QueryPlanningAgent(self.settings),
            "CaseLawAgent": CaseLawAgent(self.settings, self.vector_store, case_law_tools),
            "RegulationAgent": RegulationAgent(self.settings, self.vector_store, regulation_tools),
            "PrecedentAgent": PrecedentAgent(self.settings, self.vector_store, self.neo4j, precedent_tools),
            "ExpertAgent": ExpertAgent(self.settings, self.vector_store, expert_tools)
        }
    
    async def process_query(self, query: str, context: Optional[Dict] = None) -> SynthesisResult:
        """
        Process query through the 5-step RAG pipeline
        
        Args:
            query: User query
            context: Optional context information
            
        Returns:
            SynthesisResult: Complete synthesis of retrieved and processed information
        """
        start_time = time.time()
        
        try:
            # Step 1: User Query Submission & Planning
            logger.info(f"Step 1: Processing query - {query[:100]}...")
            state = await self._step1_query_submission(query, context)
            
            # Step 2: Data Retrieval from Vector Database (parallel across agents)
            logger.info("Step 2: Vector database retrieval across agents")
            vector_results = await self._step2_vector_retrieval(state)
            
            # Step 3: External Data Sourcing with Function Tools (if needed)
            logger.info("Step 3: External data sourcing evaluation")
            all_results = await self._step3_external_sourcing(state, vector_results)
            
            # Step 4: LLM Response Generation
            logger.info("Step 4: LLM response generation and enhancement")
            enhanced_results = await self._step4_llm_generation(state, all_results)
            
            # Step 5: Agent-Driven Refinement and Final Synthesis
            logger.info("Step 5: Agent-driven refinement and synthesis")
            final_result = await self._step5_refinement_synthesis(state, enhanced_results)
            
            # Log completion
            total_time = time.time() - start_time
            logger.info(f"RAG pipeline completed in {total_time:.2f}s")
            
            return final_result
            
        except Exception as e:
            logger.error(f"RAG pipeline failed: {e}")
            # Return fallback result
            return SynthesisResult(
                answer="I apologize, but I encountered an error processing your query. Please try again.",
                confidence=0.0,
                sources=[],
                metadata={"error": str(e), "pipeline_step": "unknown"},
                processing_time=time.time() - start_time
            )
    
    async def _step1_query_submission(self, query: str, context: Optional[Dict]) -> AgentState:
        """Step 1: Process and plan the user query"""
        query_agent = self.agents["QueryPlanningAgent"]
        
        # Create initial state
        state = AgentState(
            query=query,
            context=context or {},
            intent={},
            complexity=QueryComplexity.MODERATE,
            retrieved_documents=[]
        )
        
        # Analyze query and create execution plan
        planning_result = await query_agent.process(state)
        
        # Update state with planning results
        state.intent = planning_result.metadata.get('intent', {})
        
        # Convert complexity string back to enum
        complexity_str = planning_result.metadata.get('complexity', 'moderate')
        if isinstance(complexity_str, str):
            complexity_map = {
                'simple': QueryComplexity.SIMPLE,
                'moderate': QueryComplexity.MODERATE,
                'complex': QueryComplexity.COMPLEX,
                'expert': QueryComplexity.EXPERT
            }
            state.complexity = complexity_map.get(complexity_str, QueryComplexity.MODERATE)
        else:
            state.complexity = complexity_str
        
        return state
    
    async def _step2_vector_retrieval(self, state: AgentState) -> Dict[str, RetrievalResult]:
        """Step 2: Perform vector database retrieval with REFINED queries"""
        
        # Get strategy from query planning
        strategy = state.pipeline_metadata.get('strategy', {})
        refined_queries = strategy.get('refined_queries', {})
        
        # Determine which agents to use
        active_agents = strategy.get('recommended_agents', self._select_agents_for_query(state))
        
        # Run vector retrieval in parallel with REFINED queries
        tasks = []
        for agent_name in active_agents:
            agent = self.agents[agent_name]
            
            # Create agent-specific state with refined query
            agent_state = self._create_state_for_agent(state, agent_name, refined_queries)
            
            task = asyncio.create_task(agent.process(agent_state))
            tasks.append((agent_name, task))
        
        # Collect results
        vector_results = {}
        for agent_name, task in tasks:
            try:
                result = await asyncio.wait_for(task, timeout=30.0)
                vector_results[agent_name] = result
                logger.info(f"Agent {agent_name} completed with {len(result.documents)} documents")
            except asyncio.TimeoutError:
                logger.warning(f"Agent {agent_name} timed out")
                vector_results[agent_name] = RetrievalResult(
                    documents=[], confidence=0.0, source=agent_name,
                    metadata={"error": "timeout"}, retrieval_time=30.0
                )
            except Exception as e:
                logger.error(f"Agent {agent_name} failed: {e}")
                vector_results[agent_name] = RetrievalResult(
                    documents=[], confidence=0.0, source=agent_name,
                    metadata={"error": str(e)}, retrieval_time=0.0
                )
        
        return vector_results

    def _create_state_for_agent(self, original_state: AgentState, agent_name: str, refined_queries: Dict) -> AgentState:
        """Create agent-specific state with refined query"""
        
        # Get refined query for this agent, fallback to original if not found
        refined_query = refined_queries.get(agent_name, original_state.query)
        
        # Log the query being used
        logger.info(f"Agent {agent_name} using query: '{refined_query}' (len={len(refined_query)})")
        
        # Create new state with refined query
        agent_state = AgentState(
            query=refined_query,  # USE REFINED QUERY HERE
            context=original_state.context.copy(),
            intent=original_state.intent.copy(),
            complexity=original_state.complexity,
            retrieved_documents=[],  # Fresh start for each agent
            confidence_scores={},
            agent_outputs={},
            pipeline_metadata=original_state.pipeline_metadata.copy(),
            errors=[]
        )

        # Add original query to metadata for reference
        agent_state.pipeline_metadata['original_query'] = original_state.query
        agent_state.pipeline_metadata['agent_name'] = agent_name
        
        return agent_state
    
    async def _step3_external_sourcing(self, state: AgentState, vector_results: Dict[str, RetrievalResult]) -> Dict[str, RetrievalResult]:
        """Step 3: Evaluate need for external data sourcing and execute if necessary"""
        
        # Assess quality of vector results
        total_docs = sum(len(result.documents) for result in vector_results.values())
        avg_confidence = sum(result.confidence for result in vector_results.values()) / len(vector_results) if vector_results else 0
        
        logger.info(f"Vector retrieval summary: {total_docs} docs, {avg_confidence:.2f} confidence")
        
        # Determine if external sourcing is needed
        needs_external = self._needs_external_sourcing(total_docs, avg_confidence, state)
        
        if needs_external:
            logger.info("Initiating external data sourcing")
            
            # External sourcing is already handled by individual agents through function tools
            # The agents have already performed external sourcing in their process() method
            # So vector_results already contains both vector and external results
            
            # Log external sourcing summary
            external_docs = sum(
                len([doc for doc in result.documents if doc.get('source') != 'vector'])
                for result in vector_results.values()
            )
            logger.info(f"External sourcing added {external_docs} additional documents")
        
        return vector_results
    
    async def _step4_llm_generation(self, state: AgentState, results: Dict[str, RetrievalResult]) -> Dict[str, RetrievalResult]:
        """Step 4: LLM-based response generation and document enhancement"""
        
        # LLM enhancement is already handled by individual agents through function tools
        # Each agent that has the 'llm_enhancer' tool has already enhanced its documents
        
        # Collect all documents for state update
        all_documents = []
        for result in results.values():
            all_documents.extend(result.documents)
        
        state.retrieved_documents = all_documents
        
        logger.info(f"LLM enhancement completed for {len(all_documents)} total documents")
        
        return results
    
    async def _step5_refinement_synthesis(self, state: AgentState, results: Dict[str, RetrievalResult]) -> SynthesisResult:
        """Step 5: Final agent-driven refinement and synthesis"""
        
        # Consolidate all results
        consolidated_documents = self._consolidate_results(results)
        
        # Apply final refinement
        refined_documents = self._apply_final_refinement(consolidated_documents, state)
        
        # Update state with refined documents
        state.retrieved_documents = refined_documents
        
        # Generate final synthesis using LLM
        synthesis_data = await self.llm_synthesis.synthesize(state)
        
        # Convert to SynthesisResult object
        synthesis_result = self._create_synthesis_result(synthesis_data, state, results)
        
        return synthesis_result
    
    def _create_synthesis_result(self, synthesis_data: Dict, state: AgentState, results: Dict[str, RetrievalResult]) -> SynthesisResult:
        """Convert synthesis data to SynthesisResult object"""
        
        # Extract answer from synthesis data
        answer = synthesis_data.get('summary', synthesis_data.get('comprehensive_analysis', 'No synthesis available'))
        
        # Calculate confidence
        confidence = synthesis_data.get('llm_confidence', 0.7)
        
        # Prepare sources
        sources = []
        for doc in state.retrieved_documents[:10]:  # Limit to top 10
            sources.append({
                'title': doc.get('title', 'Unknown'),
                'source': doc.get('source', 'Unknown'),
                'relevance_score': doc.get('relevance_score', 0)
            })
        
        # Prepare metadata
        metadata = {
            'query_complexity': state.complexity.value,
            'total_documents': len(state.retrieved_documents),
            'agent_results': {
                agent_name: {
                    'documents_count': len(result.documents),
                    'confidence': result.confidence
                }
                for agent_name, result in results.items()
            },
            'synthesis_method': synthesis_data.get('synthesis_method', 'llm_guided'),
            'pipeline_version': 'RAG_v2.0'
        }
        
        return SynthesisResult(
            answer=answer,
            confidence=confidence,
            sources=sources,
            key_findings=synthesis_data.get('key_findings', []),
            recommendations=synthesis_data.get('recommendations', []),
            metadata=metadata,
            processing_time=time.time() - state.start_time.timestamp() if hasattr(state, 'start_time') else 0.0
        )
    
    def _select_agents_for_query(self, state: AgentState) -> List[str]:
        """Select which agents to use based on query analysis"""
        
        # Default agents for most queries
        base_agents = ["CaseLawAgent", "RegulationAgent"]
        
        # Add agents based on complexity
        if state.complexity in [QueryComplexity.MODERATE, QueryComplexity.COMPLEX]:
            base_agents.extend(["PrecedentAgent", "ExpertAgent"])
        elif state.complexity == QueryComplexity.EXPERT:
            base_agents.extend(["PrecedentAgent", "ExpertAgent"])
        
        # Add agents based on intent
        intent_keywords = state.intent.get('keywords', [])
        if any(keyword in ['precedent', 'deal', 'transaction', 'election'] for keyword in intent_keywords):
            if "PrecedentAgent" not in base_agents:
                base_agents.append("PrecedentAgent")
        
        return base_agents
    
    def _needs_external_sourcing(self, total_docs: int, avg_confidence: float, state: AgentState) -> bool:
        """Determine if external data sourcing is needed"""
        
        # External sourcing criteria
        min_docs_threshold = self.settings.min_docs_threshold
        min_confidence_threshold = self.settings.confidence_threshold
        
        if total_docs < min_docs_threshold:
            return True
        
        if avg_confidence < min_confidence_threshold:
            return True
        
        # Always use external for expert-level queries
        if state.complexity == QueryComplexity.EXPERT:
            return True
        
        return False
    
    def _consolidate_results(self, results: Dict[str, RetrievalResult]) -> List[Dict]:
        """Consolidate results from all agents"""
        consolidated = []
        seen_ids = set()
        
        # Sort agents by priority (case law and regulations first)
        agent_priority = {
            "RegulationAgent": 1,
            "CaseLawAgent": 2,
            "ExpertAgent": 3,
            "PrecedentAgent": 4
        }
        
        sorted_agents = sorted(results.keys(), key=lambda x: agent_priority.get(x, 5))
        
        for agent_name in sorted_agents:
            result = results[agent_name]
            for doc in result.documents:
                doc_id = doc.get('id', '')
                if doc_id and doc_id not in seen_ids:
                    # Add agent source information
                    doc['retrieved_by'] = agent_name
                    doc['agent_confidence'] = result.confidence
                    consolidated.append(doc)
                    seen_ids.add(doc_id)
        
        return consolidated
    
    def _apply_final_refinement(self, documents: List[Dict], state: AgentState) -> List[Dict]:
        """Apply final cross-agent refinement"""
        
        # Sort by relevance and authority
        refined = sorted(
            documents,
            key=lambda x: (
                x.get('relevance_score', 0) * 0.4 +
                x.get('authority_score', x.get('authority_weight', 0.5)) * 0.3 +
                x.get('quality_score', 0.5) * 0.2 +
                x.get('coherence_score', 0.5) * 0.1
            ),
            reverse=True
        )
        
        # Limit to top results based on query complexity
        max_docs = {
            QueryComplexity.SIMPLE: 10,
            QueryComplexity.MODERATE: 15,
            QueryComplexity.COMPLEX: 20,
            QueryComplexity.EXPERT: 25
        }
        
        limit = max_docs.get(state.complexity, 15)
        refined = refined[:limit]
        
        logger.info(f"Final refinement: {len(refined)} documents selected")
        
        return refined
    
    def _apply_post_processing(self, synthesis_result: SynthesisResult, state: AgentState, agent_results: Dict[str, RetrievalResult]) -> SynthesisResult:
        """Apply final post-processing to synthesis result"""
        
        # Add agent metadata
        agent_summary = {}
        for agent_name, result in agent_results.items():
            agent_summary[agent_name] = {
                'documents_count': len(result.documents),
                'confidence': result.confidence,
                'retrieval_time': result.retrieval_time
            }
        
        # Update metadata
        synthesis_result.metadata.update({
            'agent_summary': agent_summary,
            'total_documents_processed': len(state.retrieved_documents),
            'pipeline_version': 'RAG_v2.0',
            'function_tools_used': list(self.function_tools._tools.keys()) if hasattr(self.function_tools, '_tools') else []
        })
        
        # Adjust confidence based on agent consensus
        agent_confidences = [result.confidence for result in agent_results.values() if result.confidence > 0]
        if agent_confidences:
            consensus_confidence = sum(agent_confidences) / len(agent_confidences)
            # Blend synthesis confidence with agent consensus
            synthesis_result.confidence = (synthesis_result.confidence * 0.7) + (consensus_confidence * 0.3)
        
        return synthesis_result
