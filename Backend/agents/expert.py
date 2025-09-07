# Backend/agents/expert.py
import asyncio
from typing import List, Dict
from agents.base import BaseAgent
from models.state import AgentState
from models.results import RetrievalResult
import time
import re

class ExpertAgent(BaseAgent):
    """Specializes in retrieving expert analysis and technical guidance using RAG pipeline"""
    
    def __init__(self, settings, vector_store, function_tools=None):
        super().__init__("ExpertAgent", settings)
        self.vector_store = vector_store
        self.function_tools = function_tools or {}
    
    async def process(self, state: AgentState) -> RetrievalResult:
        """Process query through expert analysis"""
        start_time = time.time()
        
        try:
            # Build expert-specific query
            search_query = self._build_initial_query(state)
            
            # Perform vector search with expert filters
            documents = await self.vector_store.search(
                query=search_query,
                top_k=self.settings.top_k_results,
                filter=self._get_vector_filter()
            )
            
            # Apply domain-specific filtering
            filtered_docs = self._apply_domain_specific_filtering(documents, state)
            
            # Calculate confidence
            confidence = self._calculate_confidence(filtered_docs)
            
            result = RetrievalResult(
                documents=filtered_docs,
                confidence=confidence,
                source="expert",
                metadata={
                    "query": search_query,
                    "total_found": len(documents),
                    "filtered_count": len(filtered_docs),
                    "expert_sources": len([d for d in filtered_docs if d.get('source_credibility', 0) > 0.8])
                },
                retrieval_time=time.time() - start_time
            )
            
            self.log_performance(start_time, result)
            return result
            
        except Exception as e:
            self.logger.error(f"Error in ExpertAgent: {e}")
            return RetrievalResult(
                documents=[],
                confidence=0.0,
                source="expert",
                metadata={"error": str(e)},
                retrieval_time=time.time() - start_time
            )
    
    def _calculate_confidence(self, documents: List[Dict]) -> float:
        """Calculate confidence score for expert documents"""
        if not documents:
            return 0.0
        
        # Calculate based on expert authority scores
        authority_scores = [doc.get('expert_authority_score', 0.5) for doc in documents]
        avg_authority = sum(authority_scores) / len(authority_scores)
        
        # Boost for high credibility sources
        high_credibility = len([d for d in documents if d.get('source_credibility', 0) > 0.8])
        credibility_boost = min(0.2, high_credibility * 0.05)
        
        return min(avg_authority + credibility_boost, 1.0)
        
    def _build_initial_query(self, state: AgentState) -> str:
        """Build expert-specific search query"""
        base_query = state.query
        expert_terms = [
            "analysis", "guidance", "interpretation", "technical advice",
            "expert opinion", "commentary", "best practices", "strategy"
        ]
        enhanced_query = f"{base_query} {' '.join(expert_terms)}"
        return enhanced_query
    
    def _get_vector_filter(self) -> Dict:
        """Get expert specific vector search filter"""
        return {
            "type": "expert_analysis", 
            "document_category": ["analysis", "commentary", "guidance", "opinion"]
        }
    
    def _get_domain_terms(self) -> List[str]:
        """Get expert domain-specific terms"""
        return [
            "tax planning", "strategic advice", "compliance strategy",
            "risk assessment", "technical analysis", "expert interpretation",
            "professional guidance", "best practices", "implementation",
            "advisory opinion", "consultation", "specialized guidance"
        ]
    
    def _get_external_search_queries(self, state: AgentState) -> List[str]:
        """Get expert specific external search queries"""
        base_query = state.query
        
        queries = [
            f"{base_query} expert analysis tax planning",
            f"{base_query} professional guidance best practices",
            f"{base_query} technical interpretation advisory",
            f"{base_query} strategic tax advice commentary",
            f"{base_query} expert opinion compliance strategy"
        ]
        
        # Add complexity-based searches
        if hasattr(state, 'complexity'):
            if state.complexity.value in ['complex', 'expert']:
                queries.extend([
                    f"{base_query} advanced tax strategy expert",
                    f"{base_query} sophisticated planning techniques",
                    f"{base_query} complex transaction analysis"
                ])
        
        return queries
    
    async def _use_specialized_function_tools(self, state: AgentState, existing_docs: List[Dict]) -> List[Dict]:
        """Use expert-specific function tools"""
        additional_results = []
        
        # Professional database function tool
        if 'professional_database' in self.function_tools:
            try:
                prof_results = await self.function_tools['professional_database'](
                    query=state.query,
                    databases=['tax_advisors', 'big4_guidance', 'expert_opinions'],
                    expertise_level='senior'
                )
                additional_results.extend(self._format_professional_results(prof_results))
            except Exception as e:
                self.logger.warning(f"Professional database search failed: {e}")
        
        # Academic database function tool
        if 'academic_database' in self.function_tools:
            try:
                academic_results = await self.function_tools['academic_database'](
                    query=state.query,
                    sources=['tax_journals', 'law_reviews', 'research_papers'],
                    peer_reviewed_only=True
                )
                additional_results.extend(self._format_academic_results(academic_results))
            except Exception as e:
                self.logger.warning(f"Academic database search failed: {e}")
        
        # Industry analysis function tool
        if 'industry_analysis' in self.function_tools:
            try:
                industry_results = await self.function_tools['industry_analysis'](
                    query=state.query,
                    analysis_types=['market_trends', 'compliance_patterns', 'risk_analysis'],
                    time_period='recent'
                )
                additional_results.extend(self._format_industry_results(industry_results))
            except Exception as e:
                self.logger.warning(f"Industry analysis search failed: {e}")
        
        return additional_results
    
    def _apply_domain_specific_filtering(self, documents: List[Dict], state: AgentState) -> List[Dict]:
        """Apply expert-specific filtering logic"""
        filtered_docs = []
        
        for doc in documents:
            # Filter by expertise level and credibility
            if self._is_credible_expert_source(doc):
                # Extract expert analysis indicators
                doc['expertise_level'] = self._assess_expertise_level(doc)
                doc['analysis_depth'] = self._assess_analysis_depth(doc)
                doc['practical_applicability'] = self._assess_practical_applicability(doc, state)
                
                # Calculate expert authority score
                doc['expert_authority_score'] = self._calculate_expert_authority(doc)
                
                # Filter by minimum expertise threshold
                if doc.get('expertise_level', 0) >= 0.6:
                    filtered_docs.append(doc)
        
        return filtered_docs
    
    def _is_credible_expert_source(self, doc: Dict) -> bool:
        """Check if document is from credible expert source"""
        credible_sources = {
            # Professional firms
            'deloitte.com': 0.9,
            'pwc.com': 0.9,
            'ey.com': 0.9,
            'kpmg.com': 0.9,
            # Professional organizations
            'aicpa.org': 0.85,
            'aba.org': 0.8,
            'nysscpa.org': 0.8,
            # Academic institutions
            'edu': 0.8,  # Any .edu domain
            # Tax publications
            'taxnotes.com': 0.85,
            'bna.com': 0.8,
            'tax.thomsonreuters.com': 0.8
        }
        
        url = doc.get('url', '')
        domain = url.split('/')[2] if url else ''
        
        # Check direct domain matches
        for source_domain, credibility in credible_sources.items():
            if source_domain in domain:
                doc['source_credibility'] = credibility
                return True
        
        # Check content for expert indicators
        content = doc.get('content', '').lower()
        title = doc.get('title', '').lower()
        
        expert_indicators = [
            'expert analysis', 'professional guidance', 'advisory opinion',
            'technical interpretation', 'strategic advice', 'best practices',
            'compliance strategy', 'risk assessment'
        ]
        
        indicator_count = sum(1 for indicator in expert_indicators 
                            if indicator in content or indicator in title)
        
        if indicator_count >= 2:
            doc['source_credibility'] = 0.7
            return True
        
        return False
    
    def _assess_expertise_level(self, doc: Dict) -> float:
        """Assess the expertise level of the document"""
        content = doc.get('content', '').lower()
        title = doc.get('title', '').lower()
        
        # Expertise indicators with weights
        expertise_indicators = {
            'senior partner': 0.15,
            'tax director': 0.12,
            'managing director': 0.12,
            'principal': 0.1,
            'expert': 0.08,
            'specialist': 0.06,
            'senior': 0.05,
            'experienced': 0.04,
            'professional': 0.03,
            'certified': 0.03,
            'licensed': 0.02
        }
        
        expertise_score = 0.3  # Base score
        
        for indicator, weight in expertise_indicators.items():
            if indicator in content or indicator in title:
                expertise_score += weight
        
        # Check for advanced degree indicators
        degree_indicators = ['jd', 'llm', 'cpa', 'mba', 'phd', 'masters']
        for indicator in degree_indicators:
            if indicator in content or indicator in title:
                expertise_score += 0.05
        
        return min(expertise_score, 1.0)
    
    def _assess_analysis_depth(self, doc: Dict) -> float:
        """Assess the depth of analysis in the document"""
        content = doc.get('content', '')
        
        # Analysis depth indicators
        depth_indicators = [
            'comprehensive analysis', 'detailed examination', 'in-depth review',
            'thorough assessment', 'extensive evaluation', 'deep dive',
            'analytical framework', 'systematic approach', 'methodology'
        ]
        
        # Technical complexity indicators
        complexity_indicators = [
            'multi-step process', 'complex transaction', 'sophisticated structure',
            'advanced planning', 'technical requirements', 'regulatory framework'
        ]
        
        depth_score = 0.2  # Base score
        
        # Count depth indicators
        depth_count = sum(1 for indicator in depth_indicators if indicator in content.lower())
        depth_score += min(depth_count * 0.1, 0.3)
        
        # Count complexity indicators
        complexity_count = sum(1 for indicator in complexity_indicators if indicator in content.lower())
        depth_score += min(complexity_count * 0.08, 0.25)
        
        # Content length as depth indicator
        word_count = len(content.split())
        if word_count > 1000:
            depth_score += 0.15
        elif word_count > 500:
            depth_score += 0.1
        elif word_count > 200:
            depth_score += 0.05
        
        return min(depth_score, 1.0)
    
    def _assess_practical_applicability(self, doc: Dict, state: AgentState) -> float:
        """Assess how practically applicable the document is to the query"""
        content = doc.get('content', '').lower()
        query = state.query.lower()
        
        # Practical applicability indicators
        practical_indicators = [
            'implementation', 'step-by-step', 'how to', 'procedure',
            'process', 'checklist', 'requirements', 'compliance',
            'practical', 'actionable', 'specific guidance'
        ]
        
        applicability_score = 0.2  # Base score
        
        # Check for practical indicators
        practical_count = sum(1 for indicator in practical_indicators if indicator in content)
        applicability_score += min(practical_count * 0.08, 0.3)
        
        # Check query-content alignment
        query_words = set(query.split())
        content_words = set(content.split())
        overlap = len(query_words.intersection(content_words))
        
        if query_words:
            overlap_ratio = overlap / len(query_words)
            applicability_score += overlap_ratio * 0.4
        
        # Check for specific examples or case studies
        example_indicators = ['example', 'case study', 'illustration', 'scenario']
        example_count = sum(1 for indicator in example_indicators if indicator in content)
        if example_count > 0:
            applicability_score += 0.1
        
        return min(applicability_score, 1.0)
    
    def _calculate_expert_authority(self, doc: Dict) -> float:
        """Calculate overall expert authority score"""
        source_credibility = doc.get('source_credibility', 0.5)
        expertise_level = doc.get('expertise_level', 0.5)
        analysis_depth = doc.get('analysis_depth', 0.5)
        practical_applicability = doc.get('practical_applicability', 0.5)
        
        # Weighted combination
        authority_score = (
            source_credibility * 0.3 +
            expertise_level * 0.25 +
            analysis_depth * 0.25 +
            practical_applicability * 0.2
        )
        
        return authority_score
    
    def _format_professional_results(self, prof_results: List[Dict]) -> List[Dict]:
        """Format professional database results to standard document format"""
        formatted_docs = []
        
        for result in prof_results:
            doc = {
                'id': f"prof_{result.get('document_id', '')}",
                'title': result.get('title', ''),
                'content': result.get('content', ''),
                'url': result.get('url', ''),
                'type': 'professional_guidance',
                'source': 'professional_database',
                'relevance_score': 0.85,
                'expertise_level': 0.8,
                'source_credibility': 0.9,
                'metadata': {
                    'author': result.get('author'),
                    'firm': result.get('firm'),
                    'practice_area': result.get('practice_area'),
                    'publication_date': result.get('publication_date'),
                    'expertise_level': result.get('author_level', 'senior')
                }
            }
            formatted_docs.append(doc)
        
        return formatted_docs
    
    def _format_academic_results(self, academic_results: List[Dict]) -> List[Dict]:
        """Format academic database results to standard document format"""
        formatted_docs = []
        
        for result in academic_results:
            doc = {
                'id': f"academic_{result.get('paper_id', '')}",
                'title': result.get('title', ''),
                'content': result.get('abstract', ''),
                'url': result.get('url', ''),
                'type': 'academic_research',
                'source': 'academic_database',
                'relevance_score': 0.8,
                'expertise_level': 0.85,
                'analysis_depth': 0.9,
                'metadata': {
                    'authors': result.get('authors', []),
                    'journal': result.get('journal'),
                    'publication_year': result.get('publication_year'),
                    'citation_count': result.get('citations', 0),
                    'peer_reviewed': result.get('peer_reviewed', True)
                }
            }
            formatted_docs.append(doc)
        
        return formatted_docs
    
    def _format_industry_results(self, industry_results: List[Dict]) -> List[Dict]:
        """Format industry analysis results to standard document format"""
        formatted_docs = []
        
        for result in industry_results:
            doc = {
                'id': f"industry_{result.get('analysis_id', '')}",
                'title': result.get('title', ''),
                'content': result.get('summary', ''),
                'url': result.get('url', ''),
                'type': 'industry_analysis',
                'source': 'industry_database',
                'relevance_score': 0.75,
                'practical_applicability': 0.8,
                'metadata': {
                    'analysis_type': result.get('analysis_type'),
                    'industry_sector': result.get('sector'),
                    'report_date': result.get('report_date'),
                    'analyst': result.get('analyst'),
                    'time_period_covered': result.get('time_period')
                }
            }
            formatted_docs.append(doc)
        
        return formatted_docs
