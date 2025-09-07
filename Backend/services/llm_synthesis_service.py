from typing import Dict, List, Any
import logging
from models.state import AgentState
from openai import AsyncOpenAI
import json
import asyncio

logger = logging.getLogger(__name__)

class LLMSynthesisService:
    """LLM-powered service for synthesizing agent outputs into coherent responses"""
    
    def __init__(self, settings):
        self.settings = settings
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = "gpt-4o"  # Use latest GPT-4 model
        
        # Synthesis strategies based on complexity
        self.synthesis_strategies = {
            'simple': self._simple_llm_synthesis,
            'moderate': self._moderate_llm_synthesis,
            'complex': self._complex_llm_synthesis,
            'expert': self._expert_llm_synthesis
        }
    
    async def synthesize(self, state: AgentState) -> Dict[str, Any]:
        """Main synthesis method using LLM"""
        complexity = state.complexity.value.lower()
        strategy = self.synthesis_strategies.get(
            complexity,
            self._moderate_llm_synthesis
        )
        
        return await strategy(state)
    
    async def _simple_llm_synthesis(self, state: AgentState) -> Dict:
        """Simple LLM synthesis for basic queries"""
        
        # Prepare context from documents
        context = self._prepare_document_context(state.retrieved_documents, max_docs=5)
        
        system_prompt = """You are a professional tax research assistant. Provide clear, accurate answers based on the provided documents. 

Guidelines:
- Be concise and direct
- Use bullet points for key findings
- Cite document sources when making claims
- If information is unclear, state limitations
- Focus on practical implications"""

        user_prompt = f"""
Query: {state.query}

Available Documents:
{context}

Please provide a clear response with:
1. A brief summary answering the query
2. 3-5 key findings from the documents
3. 2-3 practical recommendations
4. Citations to source documents
"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,  # Lower temperature for factual accuracy
                max_tokens=1500
            )
            
            content = response.choices[0].message.content
            
            # Parse the structured response
            parsed_response = self._parse_llm_response(content, 'simple')
            
            return {
                'summary': parsed_response.get('summary', content[:500] + '...'),
                'key_findings': parsed_response.get('key_findings', []),
                'recommendations': parsed_response.get('recommendations', []),
                'citations': self._extract_document_citations(state.retrieved_documents),
                'llm_confidence': self._estimate_llm_confidence(response)
            }
            
        except Exception as e:
            logger.error(f"LLM synthesis failed: {e}")
            return self._fallback_synthesis(state)
    
    async def _moderate_llm_synthesis(self, state: AgentState) -> Dict:
        """Moderate LLM synthesis for standard queries"""
        
        # Group documents by source type
        grouped_docs = self._group_documents_by_source(state.retrieved_documents)
        context = self._prepare_grouped_context(grouped_docs)
        
        system_prompt = """You are an expert tax research analyst. Provide comprehensive analysis based on multiple document sources.

Guidelines:
- Synthesize information from regulations, case law, precedents, and expert sources
- Identify any conflicts or inconsistencies between sources
- Provide balanced analysis considering different perspectives
- Include confidence levels for your conclusions
- Structure response for professional use"""

        user_prompt = f"""
Query: {state.query}

Document Sources:
{context}

        Agent Confidence Scores: {dict(getattr(state, 'confidence_scores', {}))}

Please provide a comprehensive analysis with:
1. Executive summary (2-3 paragraphs)
2. Detailed findings organized by source type
3. Analysis of any conflicting information
4. Strategic recommendations with risk considerations
5. Citations organized by document type
6. Confidence assessment
"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=2500
            )
            
            content = response.choices[0].message.content
            parsed_response = self._parse_llm_response(content, 'moderate')
            
            return {
                'executive_summary': parsed_response.get('executive_summary', ''),
                'detailed_findings': parsed_response.get('detailed_findings', {}),
                'conflict_analysis': parsed_response.get('conflict_analysis', ''),
                'recommendations': parsed_response.get('recommendations', []),
                'citations': self._organize_citations_by_type(grouped_docs),
                'confidence_assessment': parsed_response.get('confidence_assessment', ''),
                'llm_confidence': self._estimate_llm_confidence(response)
            }
            
        except Exception as e:
            logger.error(f"LLM synthesis failed: {e}")
            return self._fallback_synthesis(state)
    
    async def _complex_llm_synthesis(self, state: AgentState) -> Dict:
        """Complex LLM synthesis for detailed queries"""
        
        # Prepare comprehensive context
        context = self._prepare_comprehensive_context(state)
        
        system_prompt = """You are a senior tax research expert providing analysis for complex tax matters. Your analysis will be used for strategic decision-making.

Guidelines:
- Provide multi-layered analysis considering regulatory, legal, and practical aspects
- Identify potential risks and mitigation strategies
- Consider alternative interpretations and approaches
- Provide implementation guidance
- Structure for executive and technical audiences"""

        # Break complex analysis into multiple LLM calls for better results
        analysis_tasks = [
            ("regulatory_analysis", "Analyze regulatory requirements and compliance obligations"),
            ("precedent_analysis", "Analyze relevant precedents and case law"),
            ("risk_assessment", "Assess risks and recommend mitigation strategies"),
            ("implementation_guidance", "Provide step-by-step implementation guidance")
        ]
        
        analysis_results = {}
        
        for task_name, task_description in analysis_tasks:
            task_prompt = f"""
{task_description}

Query: {state.query}
Context: {context}

Focus specifically on {task_name.replace('_', ' ')} aspects.
"""
            
            try:
                task_response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": task_prompt}
                    ],
                    temperature=0.2,
                    max_tokens=1500
                )
                
                analysis_results[task_name] = task_response.choices[0].message.content
                
            except Exception as e:
                logger.error(f"Task {task_name} failed: {e}")
                analysis_results[task_name] = f"Analysis unavailable due to error: {str(e)}"
        
        # Synthesize all analysis into final response
        final_synthesis = await self._synthesize_complex_analysis(state, analysis_results)
        
        return final_synthesis
    
    async def _expert_llm_synthesis(self, state: AgentState) -> Dict:
        """Expert-level LLM synthesis for highly complex queries"""
        
        # Use function calling for structured analysis
        functions = [
            {
                "name": "create_expert_analysis",
                "description": "Create comprehensive expert-level tax analysis",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "executive_summary": {"type": "string"},
                        "regulatory_framework": {"type": "string"},
                        "precedent_analysis": {"type": "string"},
                        "strategic_options": {"type": "array", "items": {"type": "string"}},
                        "risk_matrix": {"type": "object"},
                        "implementation_roadmap": {"type": "array", "items": {"type": "string"}},
                        "expert_opinion": {"type": "string"},
                        "confidence_level": {"type": "number"}
                    },
                    "required": ["executive_summary", "strategic_options", "expert_opinion"]
                }
            }
        ]
        
        context = self._prepare_comprehensive_context(state)
        
        system_prompt = """You are a leading tax expert with 20+ years of experience. Provide expert-level analysis suitable for C-suite decision making and complex tax planning."""

        user_prompt = f"""
Provide expert analysis for this complex tax matter:

Query: {state.query}
Available Research: {context}
Agent Insights: {self._format_agent_insights(state)}

Use your expert judgment to provide comprehensive analysis including regulatory framework, precedent analysis, strategic options, risk assessment, and implementation guidance.
"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                functions=functions,
                function_call={"name": "create_expert_analysis"},
                temperature=0.1,
                max_tokens=3000
            )
            
            if response.choices[0].function_call:
                function_args = json.loads(response.choices[0].function_call.arguments)
                return {
                    **function_args,
                    'citations': self._organize_citations_by_type(
                        self._group_documents_by_source(state.retrieved_documents)
                    ),
                    'llm_confidence': function_args.get('confidence_level', 0.8)
                }
            else:
                # Fallback to regular response parsing
                content = response.choices[0].message.content
                return self._parse_llm_response(content, 'expert')
                
        except Exception as e:
            logger.error(f"Expert LLM synthesis failed: {e}")
            return self._fallback_synthesis(state)
    
    def _prepare_document_context(self, documents: List[Dict], max_docs: int = 10) -> str:
        """Prepare document context for LLM"""
        if not documents:
            return "No documents available."
        
        # Sort by relevance and take top documents
        sorted_docs = sorted(
            documents,
            key=lambda x: x.get('relevance_score', 0),
            reverse=True
        )[:max_docs]
        
        context_parts = []
        for i, doc in enumerate(sorted_docs, 1):
            doc_context = f"""
Document {i}:
Title: {doc.get('title', 'Unknown')}
Source: {doc.get('source', 'Unknown')}
Content: {doc.get('content', '')[:800]}...
Relevance: {doc.get('relevance_score', 0):.2f}
"""
            context_parts.append(doc_context)
        
        return "\n".join(context_parts)
    
    def _group_documents_by_source(self, documents: List[Dict]) -> Dict[str, List[Dict]]:
        """Group documents by their source type"""
        grouped = {
            'regulations': [],
            'case_law': [],
            'precedents': [],
            'external_sources': [],
            'expert_knowledge': [],
            'other': []
        }
        
        for doc in documents:
            source = doc.get('source', '').lower()
            
            if 'regulation' in source:
                grouped['regulations'].append(doc)
            elif any(term in source for term in ['case', 'ruling', 'court']):
                grouped['case_law'].append(doc)
            elif 'precedent' in source:
                grouped['precedents'].append(doc)
            elif any(term in source for term in ['web_search', 'irs_api', 'external']):
                grouped['external_sources'].append(doc)
            elif 'expert' in source or 'knowledge' in source:
                grouped['expert_knowledge'].append(doc)
            else:
                grouped['other'].append(doc)
        
        return grouped
    
    def _prepare_grouped_context(self, grouped_docs: Dict[str, List[Dict]]) -> str:
        """Prepare context organized by document source type"""
        context_parts = []
        
        for source_type, docs in grouped_docs.items():
            if docs:
                context_parts.append(f"\n=== {source_type.upper()} ===")
                for doc in docs[:3]:  # Limit docs per type
                    content = f"""
- {doc.get('title', 'Unknown')}
  Content: {doc.get('content', '')[:400]}...
  Relevance: {doc.get('relevance_score', 0):.2f}
"""
                    context_parts.append(content)
        
        return "\n".join(context_parts)
    
    def _prepare_comprehensive_context(self, state: AgentState) -> str:
        """Prepare comprehensive context including all available information"""
        parts = [
            f"Original Query: {state.query}",
            f"Query Complexity: {state.complexity.value}",
            f"Agent Confidence Scores: {dict(getattr(state, 'confidence_scores', {}))}",
            "\n=== RETRIEVED DOCUMENTS ===",
            self._prepare_document_context(state.retrieved_documents, max_docs=15)
        ]
        
        if hasattr(state, 'errors') and state.errors:
            parts.append(f"\n=== PROCESSING NOTES ===\nErrors encountered: {'; '.join(state.errors)}")
        
        return "\n".join(parts)
    
    def _format_agent_insights(self, state: AgentState) -> str:
        """Format insights from different agents"""
        insights = []
        
        for agent_name, confidence in state.confidence_scores.items():
            agent_output = state.agent_outputs.get(agent_name)
            if agent_output:
                insights.append(f"{agent_name}: {confidence:.2f} confidence, {len(agent_output.documents)} documents")
        
        return "; ".join(insights)
    
    async def _synthesize_complex_analysis(self, state: AgentState, analysis_results: Dict) -> Dict:
        """Synthesize complex analysis results into final response"""
        
        synthesis_prompt = f"""
Synthesize the following analysis components into a cohesive expert response:

Query: {state.query}

Analysis Components:
{json.dumps(analysis_results, indent=2)}

Create a comprehensive response with executive summary, detailed analysis, strategic recommendations, risk assessment, and implementation guidance.
"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Synthesize complex analysis into executive-ready format."},
                    {"role": "user", "content": synthesis_prompt}
                ],
                temperature=0.15,
                max_tokens=2500
            )
            
            synthesized_content = response.choices[0].message.content
            
            return {
                'comprehensive_analysis': synthesized_content,
                'component_analysis': analysis_results,
                'citations': self._extract_document_citations(state.retrieved_documents),
                'llm_confidence': self._estimate_llm_confidence(response)
            }
            
        except Exception as e:
            logger.error(f"Complex synthesis failed: {e}")
            return {
                'comprehensive_analysis': "Synthesis temporarily unavailable",
                'component_analysis': analysis_results,
                'citations': [],
                'llm_confidence': 0.5
            }
    
    def _parse_llm_response(self, content: str, complexity: str) -> Dict:
        """Parse LLM response into structured format"""
        # Simple parsing logic - in production, you might use more sophisticated parsing
        parsed = {}
        
        # Split content into sections
        sections = content.split('\n\n')
        
        # Extract different parts based on complexity
        if complexity == 'simple':
            parsed['summary'] = sections[0] if sections else content
            parsed['key_findings'] = self._extract_bullet_points(content, 'findings')
            parsed['recommendations'] = self._extract_bullet_points(content, 'recommendations')
        elif complexity == 'moderate':
            parsed['executive_summary'] = sections[0] if sections else content[:500]
            parsed['detailed_findings'] = self._extract_detailed_findings(content)
            parsed['recommendations'] = self._extract_bullet_points(content, 'recommendations')
            parsed['confidence_assessment'] = self._extract_confidence_section(content)
        
        return parsed
    
    def _extract_bullet_points(self, content: str, section_type: str) -> List[str]:
        """Extract bullet points for specific sections"""
        lines = content.split('\n')
        bullet_points = []
        
        in_section = False
        for line in lines:
            if section_type.lower() in line.lower():
                in_section = True
                continue
            
            if in_section:
                if line.strip().startswith(('•', '-', '*', '1.', '2.', '3.')):
                    bullet_points.append(line.strip().lstrip('•-*123456789. '))
                elif line.strip() == '':
                    continue
                else:
                    break
        
        return bullet_points[:5]  # Limit to 5 points
    
    def _extract_detailed_findings(self, content: str) -> Dict:
        """Extract detailed findings organized by type"""
        # Simple implementation - could be enhanced with NLP
        return {
            'regulatory': self._extract_section(content, 'regulatory'),
            'case_law': self._extract_section(content, 'case law'),
            'precedents': self._extract_section(content, 'precedent'),
            'external': self._extract_section(content, 'external')
        }
    
    def _extract_section(self, content: str, section_name: str) -> str:
        """Extract specific section from content"""
        lines = content.split('\n')
        section_content = []
        in_section = False
        
        for line in lines:
            if section_name.lower() in line.lower():
                in_section = True
                continue
            
            if in_section:
                if line.strip():
                    section_content.append(line.strip())
                else:
                    break
        
        return ' '.join(section_content)
    
    def _extract_confidence_section(self, content: str) -> str:
        """Extract confidence assessment from content"""
        return self._extract_section(content, 'confidence')
    
    def _extract_document_citations(self, documents: List[Dict]) -> List[str]:
        """Extract citations from documents"""
        citations = []
        for doc in documents:
            title = doc.get('title', 'Unknown Document')
            source = doc.get('source', 'Unknown Source')
            citations.append(f"{title} ({source})")
        
        return citations[:10]  # Limit citations
    
    def _organize_citations_by_type(self, grouped_docs: Dict[str, List[Dict]]) -> Dict[str, List[str]]:
        """Organize citations by document type"""
        organized_citations = {}
        
        for doc_type, docs in grouped_docs.items():
            citations = []
            for doc in docs:
                title = doc.get('title', 'Unknown Document')
                citations.append(title)
            organized_citations[doc_type] = citations
        
        return organized_citations
    
    def _estimate_llm_confidence(self, response) -> float:
        """Estimate confidence in LLM response"""
        # Simple confidence estimation based on response characteristics
        content = response.choices[0].message.content
        
        # Factors that increase confidence
        confidence = 0.7  # Base confidence
        
        if len(content) > 500:  # Detailed response
            confidence += 0.1
        
        if any(phrase in content.lower() for phrase in ['according to', 'based on', 'regulation states']):
            confidence += 0.1  # Source-based reasoning
        
        if any(phrase in content.lower() for phrase in ['however', 'but', 'consideration']):
            confidence += 0.05  # Nuanced thinking
        
        # Factors that decrease confidence
        if any(phrase in content.lower() for phrase in ['unclear', 'uncertain', 'may vary']):
            confidence -= 0.1
        
        return min(max(confidence, 0.0), 1.0)  # Clamp between 0 and 1
    
    def _fallback_synthesis(self, state: AgentState) -> Dict:
        """Fallback synthesis when LLM fails"""
        if not state.retrieved_documents:
            return {
                'summary': 'No documents available for synthesis.',
                'key_findings': [],
                'recommendations': ['Please try rephrasing your query', 'Contact a tax professional'],
                'citations': [],
                'llm_confidence': 0.0
            }
        
        # Simple rule-based fallback
        top_doc = max(state.retrieved_documents, key=lambda x: x.get('relevance_score', 0))
        
        return {
            'summary': f"Based on available documents, particularly '{top_doc.get('title', 'primary source')}', " +
                      f"the query relates to {state.query}. LLM synthesis temporarily unavailable.",
            'key_findings': [f"Document found: {top_doc.get('title', 'Unknown')}"],
            'recommendations': ['Review primary documents', 'Consult with tax advisor'],
            'citations': [doc.get('title', 'Unknown') for doc in state.retrieved_documents[:5]],
            'llm_confidence': 0.3
        }
