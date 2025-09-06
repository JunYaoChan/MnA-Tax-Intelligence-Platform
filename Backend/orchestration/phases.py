import asyncio
import time
from typing import Dict, List, Any, Optional
import logging
from models.state import AgentState
from models.enums import QueryComplexity
from models.results import RetrievalResult
from agents import (
    QueryPlanningAgent,
    CaseLawAgent,
    RegulationAgent,
    PrecedentAgent,
    ExpertAgent
)
from services.synthesis_service import SynthesisService
from config.settings import Settings

logger = logging.getLogger(__name__)

class PhaseExecutor:
    """Executes workflow phases"""
    
    def __init__(self, agents: Dict[str, Any], settings: Settings):
        self.agents = agents
        self.settings = settings
        self.synthesis_service = SynthesisService()
        
    async def phase1_query_processing(self, state: AgentState) -> AgentState:
        """
        Phase 1: Query Processing and Analysis (~2 seconds)
        - Analyze query intent
        - Determine complexity
        - Create retrieval strategy
        """
        phase_start = time.time()
        logger.info(f"Phase 1: Processing query - {state.query[:100]}...")
        
        try:
            # Run query planning agent
            planning_agent = self.agents["QueryPlanningAgent"]
            result = await planning_agent.process(state)
            
            # Store results in state
            state.agent_outputs["query_planning"] = result
            state.confidence_scores["query_planning"] = result.confidence
            
            # Validate strategy
            if not state.metadata.get('strategy'):
                logger.warning("No strategy generated, using default")
                state.metadata['strategy'] = self._get_default_strategy(state.complexity)
            
            # Log phase metrics
            phase_time = time.time() - phase_start
            state.metadata['phase1_time'] = phase_time
            logger.info(f"Phase 1 completed in {phase_time:.2f}s")
            
        except Exception as e:
            logger.error(f"Error in Phase 1: {e}")
            state.errors.append(f"Query processing error: {str(e)}")
            # Set fallback strategy
            state.metadata['strategy'] = self._get_fallback_strategy()
        
        return state
    
    async def phase2_coordination(self, state: AgentState) -> AgentState:
        """
        Phase 2: Agent Coordination (~3 seconds)
        - Select appropriate agents
        - Configure agent parameters
        - Prepare parallel execution
        """
        phase_start = time.time()
        logger.info("Phase 2: Coordinating agents")
        
        try:
            strategy = state.metadata.get('strategy', {})
            
            # Select agents based on strategy
            selected_agents = self._select_agents(strategy, state)
            
            # Configure agent parameters
            agent_configs = self._configure_agents(selected_agents, state)
            
            # Prepare execution plan
            execution_plan = self._create_execution_plan(selected_agents, agent_configs)
            
            # Update state
            state.metadata['selected_agents'] = selected_agents
            state.metadata['agent_configs'] = agent_configs
            state.metadata['execution_plan'] = execution_plan
            state.metadata['coordination_complete'] = True
            
            # Validate coordination
            if not selected_agents:
                logger.warning("No agents selected, using default set")
                state.metadata['selected_agents'] = ["RegulationAgent", "CaseLawAgent"]
            
            # Log phase metrics
            phase_time = time.time() - phase_start
            state.metadata['phase2_time'] = phase_time
            logger.info(f"Phase 2 completed in {phase_time:.2f}s with {len(selected_agents)} agents")
            
        except Exception as e:
            logger.error(f"Error in Phase 2: {e}")
            state.errors.append(f"Coordination error: {str(e)}")
            # Use minimal agent set
            state.metadata['selected_agents'] = ["RegulationAgent"]
        
        return state
    
    async def phase3_retrieval(self, state: AgentState) -> AgentState:
        """
        Phase 3: Parallel Retrieval (~8 seconds)
        - Execute agents in parallel
        - Collect and validate results
        - Handle timeouts and failures
        """
        phase_start = time.time()
        logger.info("Phase 3: Starting parallel retrieval")
        
        selected_agents = state.metadata.get('selected_agents', [])
        agent_configs = state.metadata.get('agent_configs', {})
        
        # Create parallel tasks with proper error handling
        tasks = []
        agent_map = {}
        
        for agent_name in selected_agents:
            if agent_name in self.agents:
                agent = self.agents[agent_name]
                # Create task with timeout and error handling
                task = asyncio.create_task(
                    self._run_agent_with_timeout(
                        agent, 
                        state, 
                        agent_configs.get(agent_name, {})
                    )
                )
                tasks.append(task)
                agent_map[task] = agent_name
        
        if not tasks:
            logger.error("No valid agents to execute")
            state.errors.append("No agents available for retrieval")
            return state
        
        # Execute agents in parallel with monitoring
        try:
            # Wait for all tasks with overall timeout
            done, pending = await asyncio.wait(
                tasks,
                timeout=self.settings.max_query_time,
                return_when=asyncio.ALL_COMPLETED
            )
            
            # Cancel any pending tasks
            for task in pending:
                task.cancel()
                agent_name = agent_map[task]
                logger.warning(f"Agent {agent_name} cancelled due to overall timeout")
                state.errors.append(f"Agent {agent_name} timed out")
            
            # Process completed tasks
            for task in done:
                agent_name = agent_map[task]
                try:
                    result = await task
                    if result:
                        state.agent_outputs[agent_name] = result
                        state.confidence_scores[agent_name] = result.confidence
                        state.retrieved_documents.extend(result.documents)
                        logger.info(f"Agent {agent_name} returned {len(result.documents)} documents")
                except Exception as e:
                    logger.error(f"Error processing result from {agent_name}: {e}")
                    state.errors.append(f"Agent {agent_name} failed: {str(e)}")
            
            # Deduplicate documents
            state.retrieved_documents = self._deduplicate_documents(state.retrieved_documents)
            
            # Quality check
            await self._quality_check(state)
            
            # Log phase metrics
            phase_time = time.time() - phase_start
            state.metadata['phase3_time'] = phase_time
            state.metadata['documents_retrieved'] = len(state.retrieved_documents)
            logger.info(
                f"Phase 3 completed in {phase_time:.2f}s - "
                f"Retrieved {len(state.retrieved_documents)} unique documents"
            )
            
        except Exception as e:
            logger.error(f"Critical error in Phase 3: {e}")
            state.errors.append(f"Retrieval phase error: {str(e)}")
        
        return state
    
    async def phase4_synthesis(self, state: AgentState) -> AgentState:
        """
        Phase 4: Synthesis & Output Generation (~5 seconds)
        - Fuse contexts from all agents
        - Generate comprehensive analysis
        - Create structured output
        """
        phase_start = time.time()
        logger.info("Phase 4: Synthesizing results")
        
        try:
            # Check if we have sufficient results
            if not state.retrieved_documents:
                logger.warning("No documents to synthesize")
                state.metadata['final_output'] = self._generate_no_results_output(state)
                return state
            
            # Perform synthesis based on complexity
            synthesis_result = await self.synthesis_service.synthesize(state)
            
            # Generate final structured output
            final_output = self._generate_final_output(synthesis_result, state)
            
            # Add metadata
            final_output['metadata'] = {
                'processing_time': time.time() - state.start_time,
                'agents_used': list(state.agent_outputs.keys()),
                'documents_retrieved': len(state.retrieved_documents),
                'confidence_scores': state.confidence_scores,
                'errors': state.errors,
                'complexity': state.complexity.value,
                'phases_timing': {
                    'phase1': state.metadata.get('phase1_time', 0),
                    'phase2': state.metadata.get('phase2_time', 0),
                    'phase3': state.metadata.get('phase3_time', 0),
                    'phase4': time.time() - phase_start
                }
            }
            
            state.metadata['final_output'] = final_output
            
            # Log final metrics
            total_time = time.time() - state.start_time
            logger.info(
                f"Phase 4 completed - Total processing time: {total_time:.2f}s, "
                f"Confidence: {final_output.get('confidence', 'N/A')}"
            )
            
        except Exception as e:
            logger.error(f"Error in Phase 4: {e}")
            state.errors.append(f"Synthesis error: {str(e)}")
            state.metadata['final_output'] = self._generate_error_output(state)
        
        return state
    
    async def _run_agent_with_timeout(
        self,
        agent: Any,
        state: AgentState,
        config: Dict
    ) -> Optional[RetrievalResult]:
        """Run an agent with timeout and error handling"""
        try:
            # Apply agent-specific configuration
            if config:
                logger.debug(f"Running {agent.name} with config: {config}")
            
            # Execute with timeout
            result = await asyncio.wait_for(
                agent.process(state),
                timeout=self.settings.agent_timeout
            )
            
            # Validate result
            if not isinstance(result, RetrievalResult):
                logger.error(f"Invalid result type from {agent.name}")
                return None
            
            return result
            
        except asyncio.TimeoutError:
            logger.warning(f"Agent {agent.name} timed out after {self.settings.agent_timeout}s")
            return RetrievalResult(
                documents=[],
                confidence=0.0,
                source=agent.name,
                metadata={"error": "timeout"},
                retrieval_time=self.settings.agent_timeout
            )
        except Exception as e:
            logger.error(f"Agent {agent.name} failed: {e}")
            return RetrievalResult(
                documents=[],
                confidence=0.0,
                source=agent.name,
                metadata={"error": str(e)},
                retrieval_time=0
            )
    
    async def _quality_check(self, state: AgentState):
        """Perform quality check on retrieved results"""
        if not state.confidence_scores:
            state.metadata['needs_requery'] = True
            return
        
        # Calculate average confidence
        avg_confidence = sum(state.confidence_scores.values()) / len(state.confidence_scores)
        
        # Check against threshold
        if avg_confidence < self.settings.confidence_threshold:
            logger.warning(f"Low average confidence: {avg_confidence:.2%}")
            
            # Determine if requery would help
            if state.metadata.get('requery_count', 0) < 2:
                state.metadata['needs_requery'] = True
                state.metadata['low_confidence_reason'] = 'below_threshold'
            else:
                logger.info("Max requery attempts reached")
        
        # Check for sufficient documents
        if len(state.retrieved_documents) < 3:
            logger.warning(f"Insufficient documents: {len(state.retrieved_documents)}")
            if state.metadata.get('requery_count', 0) < 1:
                state.metadata['needs_requery'] = True
                state.metadata['low_confidence_reason'] = 'insufficient_documents'
    
    def _select_agents(self, strategy: Dict, state: AgentState) -> List[str]:
        """Select agents based on strategy and query analysis"""
        # Get base agents from strategy
        agents = strategy.get('parallel_agents', [])
        
        # Add agents based on query content
        query_lower = state.query.lower()
        
        # Add specific agents based on keywords
        if 'regulation' in query_lower or 'section' in query_lower:
            if 'RegulationAgent' not in agents:
                agents.append('RegulationAgent')
        
        if 'case' in query_lower or 'ruling' in query_lower:
            if 'CaseLawAgent' not in agents:
                agents.append('CaseLawAgent')
        
        if 'precedent' in query_lower or 'similar' in query_lower:
            if 'PrecedentAgent' not in agents:
                agents.append('PrecedentAgent')
        
        # Always include expert agent for complex queries
        if state.complexity in [QueryComplexity.COMPLEX, QueryComplexity.EXPERT]:
            if 'ExpertAgent' not in agents:
                agents.append('ExpertAgent')
        
        return agents
    
    def _configure_agents(self, agents: List[str], state: AgentState) -> Dict:
        """Configure parameters for each agent"""
        configs = {}
        
        for agent_name in agents:
            config = {
                'max_results': self._get_max_results(agent_name, state),
                'confidence_threshold': self._get_confidence_threshold(agent_name, state),
                'search_depth': self._get_search_depth(agent_name, state)
            }
            configs[agent_name] = config
        
        return configs
    
    def _get_max_results(self, agent_name: str, state: AgentState) -> int:
        """Determine max results for an agent"""
        base_results = 10
        
        # Adjust based on complexity
        if state.complexity == QueryComplexity.SIMPLE:
            return base_results // 2
        elif state.complexity == QueryComplexity.EXPERT:
            return base_results * 2
        
        return base_results
    
    def _get_confidence_threshold(self, agent_name: str, state: AgentState) -> float:
        """Determine confidence threshold for an agent"""
        base_threshold = self.settings.confidence_threshold
        
        # Lower threshold for expert queries to get more results
        if state.complexity == QueryComplexity.EXPERT:
            return base_threshold * 0.8
        
        return base_threshold
    
    def _get_search_depth(self, agent_name: str, state: AgentState) -> str:
        """Determine search depth for an agent"""
        if state.complexity in [QueryComplexity.SIMPLE, QueryComplexity.MODERATE]:
            return "shallow"
        else:
            return "deep"
    
    def _create_execution_plan(
        self,
        agents: List[str],
        configs: Dict
    ) -> Dict:
        """Create execution plan for agents"""
        return {
            'parallel_groups': [agents],  # All agents run in parallel
            'timeout_strategy': 'soft',  # Continue with partial results on timeout
            'failure_strategy': 'continue',  # Continue with other agents on failure
            'configs': configs
        }
    
    def _deduplicate_documents(self, documents: List[Dict]) -> List[Dict]:
        """Remove duplicate documents based on ID"""
        seen_ids = set()
        unique_docs = []
        
        for doc in documents:
            doc_id = doc.get('id')
            if doc_id and doc_id not in seen_ids:
                seen_ids.add(doc_id)
                unique_docs.append(doc)
            elif not doc_id:
                # Keep documents without IDs (assume unique)
                unique_docs.append(doc)
        
        return unique_docs
    
    def _get_default_strategy(self, complexity: QueryComplexity) -> Dict:
        """Get default strategy based on complexity"""
        if complexity == QueryComplexity.SIMPLE:
            return {
                'parallel_agents': ['RegulationAgent'],
                'priority_order': ['RegulationAgent'],
                'fallback_options': []
            }
        elif complexity == QueryComplexity.MODERATE:
            return {
                'parallel_agents': ['RegulationAgent', 'CaseLawAgent'],
                'priority_order': ['RegulationAgent', 'CaseLawAgent'],
                'fallback_options': ['ExpertAgent']
            }
        else:
            return {
                'parallel_agents': [
                    'RegulationAgent', 'CaseLawAgent',
                    'PrecedentAgent', 'ExpertAgent'
                ],
                'priority_order': ['RegulationAgent', 'CaseLawAgent'],
                'fallback_options': []
            }
    
    def _get_fallback_strategy(self) -> Dict:
        """Get minimal fallback strategy"""
        return {
            'parallel_agents': ['RegulationAgent'],
            'priority_order': ['RegulationAgent'],
            'fallback_options': []
        }
    
    def _generate_final_output(
        self,
        synthesis_result: Dict,
        state: AgentState
    ) -> Dict:
        """Generate final structured output"""
        # Calculate overall confidence
        overall_confidence = 0.0
        if state.confidence_scores:
            overall_confidence = sum(state.confidence_scores.values()) / len(state.confidence_scores)
        
        return {
            'status': 'success' if not state.errors else 'partial',
            'query': state.query,
            'response_time': time.time() - state.start_time,
            'confidence': f"{overall_confidence:.1%}",
            'summary': synthesis_result.get('summary', ''),
            'key_findings': synthesis_result.get('key_findings', []),
            'recommendations': synthesis_result.get('recommendations', []),
            'citations': synthesis_result.get('citations', []),
            'warnings': state.errors if state.errors else None
        }
    
    def _generate_no_results_output(self, state: AgentState) -> Dict:
        """Generate output when no results are found"""
        return {
            'status': 'no_results',
            'query': state.query,
            'response_time': time.time() - state.start_time,
            'confidence': '0%',
            'summary': 'No relevant information found for your query.',
            'key_findings': [],
            'recommendations': [
                'Try rephrasing your query',
                'Check for typos in section numbers',
                'Consult with a tax professional'
            ],
            'citations': [],
            'errors': state.errors
        }
    
    def _generate_error_output(self, state: AgentState) -> Dict:
        """Generate output for error cases"""
        return {
            'status': 'error',
            'query': state.query,
            'response_time': time.time() - state.start_time,
            'confidence': 'N/A',
            'summary': 'An error occurred while processing your query.',
            'key_findings': [],
            'recommendations': ['Please try again or contact support'],
            'citations': [],
            'errors': state.errors
        }