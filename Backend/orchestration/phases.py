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
from agents.web_search import WebSearchAgent  # NEW
from agents.irs_api import IRSAPIAgent  # NEW
from services.llm_synthesis_service import LLMSynthesisService  # NEW - replaces SynthesisService
from config.settings import Settings

logger = logging.getLogger(__name__)

class PhaseExecutor:
    """Executes workflow phases with external data sourcing and LLM synthesis"""
    
    def __init__(self, agents: Dict[str, Any], settings: Settings):
        self.agents = agents
        self.settings = settings
        # NEW: Use LLM-powered synthesis instead of rule-based
        self.synthesis_service = LLMSynthesisService(settings)
        
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
        - Select appropriate agents (internal first)
        - Configure agent parameters
        - Prepare parallel execution
        """
        phase_start = time.time()
        logger.info("Phase 2: Coordinating agents")
        
        try:
            strategy = state.metadata.get('strategy', {})
            
            # Select INTERNAL agents first (external agents handled in phase 3b)
            selected_agents = self._select_internal_agents(strategy, state)
            
            # Configure agent parameters
            agent_configs = self._configure_agents(selected_agents, state)
            
            # Prepare execution plan
            execution_plan = self._create_execution_plan(selected_agents, agent_configs)
            
            # Update state
            state.metadata['selected_internal_agents'] = selected_agents
            state.metadata['agent_configs'] = agent_configs
            state.metadata['execution_plan'] = execution_plan
            state.metadata['coordination_complete'] = True
            
            # Validate coordination
            if not selected_agents:
                logger.warning("No internal agents selected, using default set")
                state.metadata['selected_internal_agents'] = ["RegulationAgent", "CaseLawAgent"]
            
            # Log phase metrics
            phase_time = time.time() - phase_start
            state.metadata['phase2_time'] = phase_time
            logger.info(f"Phase 2 completed in {phase_time:.2f}s with {len(selected_agents)} internal agents")
            
        except Exception as e:
            logger.error(f"Error in Phase 2: {e}")
            state.errors.append(f"Coordination error: {str(e)}")
            # Use minimal agent set
            state.metadata['selected_internal_agents'] = ["RegulationAgent"]
        
        return state
    
    async def phase3_retrieval(self, state: AgentState) -> AgentState:
        """
        Phase 3: Parallel Retrieval from Internal Sources (~8 seconds)
        - Execute internal agents in parallel
        - Collect and validate results
        - Handle timeouts and failures
        """
        phase_start = time.time()
        logger.info("Phase 3: Starting parallel retrieval from internal sources")
        
        selected_agents = state.metadata.get('selected_internal_agents', [])
        agent_configs = state.metadata.get('agent_configs', {})
        
        # Create parallel tasks with proper error handling for INTERNAL agents only
        tasks = []
        agent_map = {}
        
        for agent_name in selected_agents:
            if agent_name in self.agents and agent_name not in ['WebSearchAgent', 'IRSAPIAgent']:
                agent = self.agents[agent_name]
                config = agent_configs.get(agent_name, {})
                
                task = asyncio.create_task(
                    self._run_agent_with_timeout(agent, state, config)
                )
                tasks.append(task)
                agent_map[task] = agent_name
        
        # Execute all internal agents in parallel
        if tasks:
            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                all_documents = []
                for i, result in enumerate(results):
                    agent_name = agent_map[tasks[i]]
                    
                    if isinstance(result, RetrievalResult):
                        state.agent_outputs[agent_name] = result
                        state.confidence_scores[agent_name] = result.confidence
                        all_documents.extend(result.documents)
                        logger.info(f"Agent {agent_name} returned {len(result.documents)} documents")
                    else:
                        error_msg = str(result) if isinstance(result, Exception) else "Unknown error"
                        logger.error(f"Agent {agent_name} failed: {error_msg}")
                        state.errors.append(f"{agent_name}: {error_msg}")
                        # Create empty result for failed agent
                        state.agent_outputs[agent_name] = RetrievalResult(
                            documents=[], confidence=0.0, source=agent_name,
                            metadata={"error": error_msg}, retrieval_time=0
                        )
                        state.confidence_scores[agent_name] = 0.0
                
                # Deduplicate documents
                state.retrieved_documents = self._deduplicate_documents(all_documents)
                
            except Exception as e:
                logger.error(f"Critical error in internal retrieval: {e}")
                state.errors.append(f"Internal retrieval phase error: {str(e)}")
        
        # Log phase metrics
        phase_time = time.time() - phase_start
        state.metadata['phase3_time'] = phase_time
        state.metadata['internal_documents_retrieved'] = len(state.retrieved_documents)
        logger.info(
            f"Phase 3 completed in {phase_time:.2f}s - "
            f"Retrieved {len(state.retrieved_documents)} unique documents from internal sources"
        )
        
        return state
    
    async def quality_check_node(self, state: AgentState) -> AgentState:
        """
        NEW: Quality Check Node
        - Assess quality of internal retrieval results
        - Determine if external sources are needed
        """
        logger.info("Quality Check: Assessing internal retrieval results")
        
        try:
            # Check document count
            doc_count = len(state.retrieved_documents)
            
            # Check average confidence
            avg_confidence = 0.0
            if state.confidence_scores:
                internal_scores = {k: v for k, v in state.confidence_scores.items() 
                                 if k not in ['WebSearchAgent', 'IRSAPIAgent']}
                if internal_scores:
                    avg_confidence = sum(internal_scores.values()) / len(internal_scores)
            
            # Quality assessment
            sufficient_docs = doc_count >= 3
            high_confidence = avg_confidence >= self.settings.confidence_threshold
            
            # Store quality metrics
            state.metadata['quality_check'] = {
                'sufficient_documents': sufficient_docs,
                'high_confidence': high_confidence,
                'document_count': doc_count,
                'average_confidence': avg_confidence,
                'needs_external_enrichment': not (sufficient_docs and high_confidence)
            }
            
            logger.info(
                f"Quality Check: {doc_count} docs, {avg_confidence:.2%} confidence, "
                f"Sufficient: {sufficient_docs}, High confidence: {high_confidence}"
            )
            
        except Exception as e:
            logger.error(f"Error in quality check: {e}")
            state.errors.append(f"Quality check error: {str(e)}")
            # Default to needing external enrichment on error
            state.metadata['quality_check'] = {'needs_external_enrichment': True}
        
        return state
    
    async def phase3b_external_enrichment(self, state: AgentState) -> AgentState:
        """
        NEW: Phase 3b: External Data Enrichment (~5 seconds)
        - Use external agents to gather real-time data
        - Enhance internal results with external sources
        """
        phase_start = time.time()
        logger.info("Phase 3b: Starting external data enrichment")
        
        try:
            # Select external agents based on query characteristics
            external_agents = self._select_external_agents(state)
            
            if not external_agents:
                logger.info("No external agents selected for this query")
                return state
            
            # Run external agents in parallel
            external_tasks = []
            external_agent_map = {}
            
            for agent_name in external_agents:
                if agent_name in self.agents:
                    agent = self.agents[agent_name]
                    task = asyncio.create_task(
                        self._run_agent_with_timeout(agent, state, {})
                    )
                    external_tasks.append(task)
                    external_agent_map[task] = agent_name
            
            # Execute external agents
            if external_tasks:
                external_results = await asyncio.gather(*external_tasks, return_exceptions=True)
                
                # Process external results
                external_documents = []
                for i, result in enumerate(external_results):
                    agent_name = external_agent_map[external_tasks[i]]
                    
                    if isinstance(result, RetrievalResult):
                        state.agent_outputs[agent_name] = result
                        state.confidence_scores[agent_name] = result.confidence
                        external_documents.extend(result.documents)
                        logger.info(f"External agent {agent_name} returned {len(result.documents)} documents")
                    else:
                        error_msg = str(result) if isinstance(result, Exception) else "Unknown error"
                        logger.error(f"External agent {agent_name} failed: {error_msg}")
                        state.errors.append(f"{agent_name}: {error_msg}")
                
                # Merge external documents with internal ones
                if external_documents:
                    all_documents = state.retrieved_documents + external_documents
                    state.retrieved_documents = self._deduplicate_documents(all_documents)
                    
                    logger.info(f"Added {len(external_documents)} external documents")
            
            # Log phase metrics
            phase_time = time.time() - phase_start
            state.metadata['phase3b_time'] = phase_time
            state.metadata['external_agents_used'] = external_agents
            state.metadata['total_documents_with_external'] = len(state.retrieved_documents)
            
            logger.info(
                f"Phase 3b completed in {phase_time:.2f}s - "
                f"Total documents after external enrichment: {len(state.retrieved_documents)}"
            )
            
        except Exception as e:
            logger.error(f"Error in external enrichment: {e}")
            state.errors.append(f"External enrichment error: {str(e)}")
        
        return state
    
    async def phase4_synthesis(self, state: AgentState) -> AgentState:
        """
        Phase 4: LLM-Powered Synthesis & Output Generation (~5 seconds)
        - Use LLM to synthesize all retrieved data
        - Generate comprehensive analysis
        - Create structured output
        """
        phase_start = time.time()
        logger.info("Phase 4: Synthesizing results with LLM")
        
        try:
            # Check if we have sufficient results
            if not state.retrieved_documents:
                logger.warning("No documents to synthesize")
                state.metadata['final_output'] = self._generate_no_results_output(state)
                return state
            
            # NEW: Perform LLM-powered synthesis
            synthesis_result = await self.synthesis_service.synthesize(state)
            
            # Generate final structured output
            final_output = self._generate_final_output(synthesis_result, state)
            
            # Add comprehensive metadata
            final_output['metadata'] = {
                'processing_time': time.time() - state.start_time,
                'agents_used': list(state.agent_outputs.keys()),
                'internal_agents': [a for a in state.agent_outputs.keys() 
                                  if a not in ['WebSearchAgent', 'IRSAPIAgent']],
                'external_agents': [a for a in state.agent_outputs.keys() 
                                  if a in ['WebSearchAgent', 'IRSAPIAgent']],
                'documents_retrieved': len(state.retrieved_documents),
                'confidence_scores': state.confidence_scores,
                'errors': state.errors,
                'complexity': state.complexity.value,
                'quality_check': state.metadata.get('quality_check', {}),
                'llm_confidence': synthesis_result.get('llm_confidence', 0.0),
                'phases_timing': {
                    'phase1': state.metadata.get('phase1_time', 0),
                    'phase2': state.metadata.get('phase2_time', 0),
                    'phase3': state.metadata.get('phase3_time', 0),
                    'phase3b': state.metadata.get('phase3b_time', 0),
                    'phase4': time.time() - phase_start
                }
            }
            
            state.metadata['final_output'] = final_output
            
            # Log final metrics
            total_time = time.time() - state.start_time
            logger.info(
                f"Phase 4 completed in {time.time() - phase_start:.2f}s - "
                f"Total processing time: {total_time:.2f}s, "
                f"LLM Confidence: {synthesis_result.get('llm_confidence', 'N/A')}"
            )
            
        except Exception as e:
            logger.error(f"Error in Phase 4: {e}")
            state.errors.append(f"Synthesis error: {str(e)}")
            state.metadata['final_output'] = self._generate_error_output(state)
        
        return state
    
    def _select_internal_agents(self, strategy: Dict, state: AgentState) -> List[str]:
        """Select internal agents only (excludes external agents)"""
        # Get base agents from strategy
        agents = strategy.get('parallel_agents', [])
        
        # Filter to only internal agents
        internal_agents = ['CaseLawAgent', 'RegulationAgent', 'PrecedentAgent', 'ExpertAgent']
        selected_internal = [agent for agent in agents if agent in internal_agents]
        
        # Add agents based on query content
        query_lower = state.query.lower()
        
        if 'regulation' in query_lower or 'section' in query_lower:
            if 'RegulationAgent' not in selected_internal:
                selected_internal.append('RegulationAgent')
        
        if 'case' in query_lower or 'ruling' in query_lower:
            if 'CaseLawAgent' not in selected_internal:
                selected_internal.append('CaseLawAgent')
        
        if 'precedent' in query_lower or 'similar' in query_lower:
            if 'PrecedentAgent' not in selected_internal:
                selected_internal.append('PrecedentAgent')
        
        # Always include expert agent for complex queries
        if state.complexity in [QueryComplexity.COMPLEX, QueryComplexity.EXPERT]:
            if 'ExpertAgent' not in selected_internal:
                selected_internal.append('ExpertAgent')
        
        # Ensure we have at least one agent
        if not selected_internal:
            selected_internal = ['RegulationAgent']
        
        return selected_internal
    
    def _select_external_agents(self, state: AgentState) -> List[str]:
        """NEW: Select external agents based on query characteristics"""
        external_agents = []
        query_lower = state.query.lower()
        
        # Use WebSearchAgent for recent/current information
        if any(term in query_lower for term in ['current', 'recent', 'latest', 'new', '2024', '2025']):
            external_agents.append('WebSearchAgent')
        
        # Use IRSAPIAgent for rates, deadlines, forms
        if any(term in query_lower for term in ['rate', 'deadline', 'form', 'publication', 'due date']):
            external_agents.append('IRSAPIAgent')
        
        # Use WebSearchAgent for broad queries that might benefit from authoritative sources
        if state.complexity in [QueryComplexity.COMPLEX, QueryComplexity.EXPERT]:
            if 'WebSearchAgent' not in external_agents:
                external_agents.append('WebSearchAgent')
        
        # Always try web search if internal results were insufficient
        quality_check = state.metadata.get('quality_check', {})
        if not quality_check.get('sufficient_documents', True):
            if 'WebSearchAgent' not in external_agents:
                external_agents.append('WebSearchAgent')
        
        return external_agents
    
    def _generate_final_output(self, synthesis_result: Dict, state: AgentState) -> Dict:
        """Generate final structured output with LLM synthesis results"""
        
        # Calculate overall confidence (combine agent confidence and LLM confidence)
        overall_confidence = 0.0
        if state.confidence_scores:
            agent_confidence = sum(state.confidence_scores.values()) / len(state.confidence_scores)
            llm_confidence = synthesis_result.get('llm_confidence', 0.0)
            overall_confidence = (agent_confidence * 0.6) + (llm_confidence * 0.4)  # Weight toward agent confidence
        
        # Extract synthesis content based on complexity
        if 'comprehensive_analysis' in synthesis_result:
            # Complex/Expert synthesis
            return {
                'status': 'success' if not state.errors else 'partial',
                'query': state.query,
                'response_time': time.time() - state.start_time,
                'confidence': f"{overall_confidence:.1%}",
                'comprehensive_analysis': synthesis_result['comprehensive_analysis'],
                'component_analysis': synthesis_result.get('component_analysis', {}),
                'citations': synthesis_result.get('citations', []),
                'warnings': state.errors if state.errors else None
            }
        elif 'executive_summary' in synthesis_result:
            # Moderate synthesis
            return {
                'status': 'success' if not state.errors else 'partial',
                'query': state.query,
                'response_time': time.time() - state.start_time,
                'confidence': f"{overall_confidence:.1%}",
                'executive_summary': synthesis_result['executive_summary'],
                'detailed_findings': synthesis_result.get('detailed_findings', {}),
                'recommendations': synthesis_result.get('recommendations', []),
                'citations': synthesis_result.get('citations', []),
                'warnings': state.errors if state.errors else None
            }
        else:
            # Simple synthesis
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
    
    # ... (keeping existing helper methods but updating as needed)
    
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
        
        # External agents might return more results
        if agent_name in ['WebSearchAgent', 'IRSAPIAgent']:
            base_results = 15
        
        # Adjust based on complexity
        if state.complexity == QueryComplexity.SIMPLE:
            return base_results // 2
        elif state.complexity == QueryComplexity.EXPERT:
            return base_results * 2
        
        return base_results
    
    def _get_confidence_threshold(self, agent_name: str, state: AgentState) -> float:
        """Determine confidence threshold for an agent"""
        base_threshold = self.settings.confidence_threshold
        
        # External agents might have different thresholds
        if agent_name == 'WebSearchAgent':
            return base_threshold * 0.7  # Lower threshold for web results
        
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
    
    def _create_execution_plan(self, agents: List[str], configs: Dict) -> Dict:
        """Create execution plan for agents"""
        return {
            'parallel_groups': [agents],  # All agents run in parallel
            'timeout_strategy': 'soft',  # Continue with partial results on timeout
            'failure_strategy': 'continue',  # Continue with other agents on failure
            'configs': configs
        }
    
    def _deduplicate_documents(self, documents: List[Dict]) -> List[Dict]:
        """Remove duplicate documents based on ID and content"""
        seen_ids = set()
        seen_content_hashes = set()
        unique_docs = []
        
        for doc in documents:
            doc_id = doc.get('id')
            content = doc.get('content', '')
            content_hash = hash(content[:200])  # Hash first 200 chars
            
            # Check for ID-based duplicates
            if doc_id and doc_id in seen_ids:
                continue
            
            # Check for content-based duplicates
            if content_hash in seen_content_hashes:
                continue
            
            # Add to unique documents
            unique_docs.append(doc)
            
            if doc_id:
                seen_ids.add(doc_id)
            seen_content_hashes.add(content_hash)
        
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