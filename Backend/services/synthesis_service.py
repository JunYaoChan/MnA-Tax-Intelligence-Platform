from typing import Dict, List, Any
import logging
from models.state import AgentState

logger = logging.getLogger(__name__)

class SynthesisService:
    """Service for synthesizing agent outputs into coherent responses"""
    
    def __init__(self):
        self.synthesis_strategies = {
            'simple': self._simple_synthesis,
            'moderate': self._moderate_synthesis,
            'complex': self._complex_synthesis,
            'expert': self._expert_synthesis
        }
    
    async def synthesize(self, state: AgentState) -> Dict[str, Any]:
        """Main synthesis method"""
        complexity = state.complexity.value
        strategy = self.synthesis_strategies.get(
            complexity,
            self._moderate_synthesis
        )
        
        return await strategy(state)
    
    async def _simple_synthesis(self, state: AgentState) -> Dict:
        """Simple synthesis for basic queries"""
        # Gather all documents
        all_docs = state.retrieved_documents
        
        # Sort by relevance
        sorted_docs = sorted(
            all_docs,
            key=lambda x: x.get('relevance_score', 0),
            reverse=True
        )
        
        # Take top results
        top_docs = sorted_docs[:5]
        
        return {
            'summary': self._generate_simple_summary(top_docs),
            'key_findings': self._extract_simple_findings(top_docs),
            'recommendations': self._generate_simple_recommendations(top_docs),
            'citations': [doc.get('title', '') for doc in top_docs]
        }
    
    async def _moderate_synthesis(self, state: AgentState) -> Dict:
        """Moderate synthesis for standard queries"""
        # Group documents by source
        grouped_docs = self._group_by_source(state.retrieved_documents)
        
        # Generate cross-referenced summary
        summary = self._generate_cross_referenced_summary(grouped_docs)
        
        # Extract comprehensive findings
        findings = self._extract_comprehensive_findings(grouped_docs, state)
        
        # Generate prioritized recommendations
        recommendations = self._generate_prioritized_recommendations(
            grouped_docs,
            state
        )
        
        # Compile citations with categories
        citations = self._compile_categorized_citations(grouped_docs)
        
        return {
            'summary': summary,
            'key_findings': findings,
            'recommendations': recommendations,
            'citations': citations,
            'confidence_breakdown': self._generate_confidence_breakdown(state)
        }
    
    async def _complex_synthesis(self, state: AgentState) -> Dict:
        """Complex synthesis for detailed queries"""
        # Perform deep analysis
        analysis = await self._deep_analysis(state)
        
        # Generate executive summary
        executive_summary = self._generate_executive_summary(analysis)
        
        # Create detailed findings with evidence
        detailed_findings = self._create_detailed_findings(analysis, state)
        
        # Generate action plan
        action_plan = self._generate_action_plan(analysis, state)
        
        # Risk assessment
        risk_assessment = self._assess_risks(analysis, state)
        
        return {
            'executive_summary': executive_summary,
            'detailed_analysis': analysis,
            'key_findings': detailed_findings,
            'action_plan': action_plan,
            'risk_assessment': risk_assessment,
            'citations': self._compile_comprehensive_citations(state),
            'metadata': self._generate_metadata(state)
        }
    
    async def _expert_synthesis(self, state: AgentState) -> Dict:
        """Expert synthesis for highly complex queries"""
        # Multi-dimensional analysis
        multi_analysis = await self._multi_dimensional_analysis(state)
        
        # Generate comprehensive report
        report = self._generate_comprehensive_report(multi_analysis, state)
        
        # Create decision matrix
        decision_matrix = self._create_decision_matrix(multi_analysis)
        
        # Generate scenario analysis
        scenarios = self._generate_scenarios(multi_analysis, state)
        
        return {
            'comprehensive_report': report,
            'decision_matrix': decision_matrix,
            'scenario_analysis': scenarios,
            'expert_opinions': self._consolidate_expert_opinions(state),
            'citations': self._compile_comprehensive_citations(state),
            'confidence_analysis': self._detailed_confidence_analysis(state)
        }
    
    def _group_by_source(self, documents: List[Dict]) -> Dict[str, List[Dict]]:
        """Group documents by their source"""
        grouped = {
            'regulations': [],
            'case_law': [],
            'precedents': [],
            'expert_knowledge': [],
            'other': []
        }
        
        for doc in documents:
            source = doc.get('source', doc.get('type', 'other'))
            
            if 'regulation' in source.lower():
                grouped['regulations'].append(doc)
            elif any(term in source.lower() for term in ['case', 'ruling', 'plr']):
                grouped['case_law'].append(doc)
            elif 'precedent' in source.lower():
                grouped['precedents'].append(doc)
            elif any(term in source.lower() for term in ['expert', 'knowledge', 'guide']):
                grouped['expert_knowledge'].append(doc)
            else:
                grouped['other'].append(doc)
        
        return grouped
    
    def _generate_simple_summary(self, docs: List[Dict]) -> str:
        """Generate a simple summary"""
        if not docs:
            return "No relevant documents found for the query."
        
        top_doc = docs[0]
        return f"Based on {len(docs)} relevant sources, the primary finding relates to {top_doc.get('title', 'the query')}. {top_doc.get('content', '')[:200]}..."
    
    def _extract_simple_findings(self, docs: List[Dict]) -> List[str]:
        """Extract simple key findings"""
        findings = []
        
        for doc in docs[:3]:
            title = doc.get('title', '')
            if title:
                findings.append(f"✓ {title}")
        
        return findings
    
    def _generate_simple_recommendations(self, docs: List[Dict]) -> List[str]:
        """Generate simple recommendations"""
        recommendations = []
        
        # Extract recommendations from documents
        for doc in docs:
            if 'recommendation' in doc.get('content', '').lower():
                # Simple extraction logic
                recommendations.append("Review relevant tax regulations")
                break
        
        if not recommendations:
            recommendations.append("Consult with tax advisor for specific guidance")
        
        return recommendations
    
    def _generate_cross_referenced_summary(self, grouped_docs: Dict) -> str:
        """Generate summary with cross-references"""
        parts = []
        
        if grouped_docs['regulations']:
            parts.append(
                f"Found {len(grouped_docs['regulations'])} relevant regulations"
            )
        
        if grouped_docs['case_law']:
            parts.append(
                f"{len(grouped_docs['case_law'])} supporting case law references"
            )
        
        if grouped_docs['precedents']:
            parts.append(
                f"{len(grouped_docs['precedents'])} similar precedent transactions"
            )
        
        if grouped_docs['expert_knowledge']:
            parts.append(
                f"{len(grouped_docs['expert_knowledge'])} expert insights"
            )
        
        return f"Analysis complete: {', '.join(parts)}."
    
    def _extract_comprehensive_findings(
        self,
        grouped_docs: Dict,
        state: AgentState
    ) -> List[str]:
        """Extract comprehensive findings from grouped documents"""
        findings = []
        
        # Add findings from each category
        for category, docs in grouped_docs.items():
            if docs and category != 'other':
                category_finding = f"From {category.replace('_', ' ')}: "
                # Add top finding from category
                if docs[0].get('title'):
                    category_finding += docs[0]['title']
                    findings.append(category_finding)
        
        return findings[:10]  # Limit to top 10 findings
    
    def _generate_prioritized_recommendations(
        self,
        grouped_docs: Dict,
        state: AgentState
    ) -> List[str]:
        """Generate prioritized recommendations"""
        recommendations = []
        priority_scores = {}
        
        # Extract and score recommendations
        for category, docs in grouped_docs.items():
            for doc in docs:
                # Extract recommendations from document
                if 'expert_annotations' in doc:
                    for ann in doc['expert_annotations']:
                        if 'recommendation' in ann:
                            rec = ann['recommendation']
                            # Score based on confidence and source
                            score = ann.get('confidence', 0.5)
                            if category == 'expert_knowledge':
                                score *= 1.2
                            priority_scores[rec] = max(
                                priority_scores.get(rec, 0),
                                score
                            )
        
        # Sort by priority
        sorted_recs = sorted(
            priority_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Format recommendations
        for i, (rec, score) in enumerate(sorted_recs[:5], 1):
            recommendations.append(f"{i}. {rec}")
        
        return recommendations
    
    def _compile_categorized_citations(self, grouped_docs: Dict) -> List[str]:
        """Compile citations organized by category"""
        citations = []
        
        for category, docs in grouped_docs.items():
            if docs and category != 'other':
                citations.append(f"[{category.upper()}]")
                for doc in docs[:3]:  # Limit citations per category
                    if doc.get('title'):
                        citations.append(f"  • {doc['title']}")
        
        return citations
    
    def _generate_confidence_breakdown(self, state: AgentState) -> Dict:
        """Generate confidence breakdown by agent"""
        breakdown = {}
        
        for agent, score in state.confidence_scores.items():
            breakdown[agent] = f"{score:.1%}"
        
        # Add overall confidence
        if state.confidence_scores:
            avg_confidence = sum(state.confidence_scores.values()) / len(state.confidence_scores)
            breakdown['overall'] = f"{avg_confidence:.1%}"
        
        return breakdown
    
    async def _deep_analysis(self, state: AgentState) -> Dict:
        """Perform deep analysis of retrieved information"""
        # Placeholder for complex analysis logic
        return {
            'regulatory_analysis': self._analyze_regulations(state),
            'case_law_analysis': self._analyze_case_law(state),
            'precedent_analysis': self._analyze_precedents(state),
            'expert_analysis': self._analyze_expert_knowledge(state)
        }
    
    def _analyze_regulations(self, state: AgentState) -> Dict:
        """Analyze regulatory documents"""
        reg_docs = [
            doc for doc in state.retrieved_documents
            if doc.get('type') == 'regulation'
        ]
        
        return {
            'primary_sections': self._extract_sections(reg_docs),
            'requirements': self._extract_requirements(reg_docs),
            'deadlines': self._extract_deadlines(reg_docs)
        }
    
    def _extract_sections(self, docs: List[Dict]) -> List[str]:
        """Extract regulation sections"""
        sections = set()
        for doc in docs:
            # Extract section numbers from title or content
            import re
            pattern = r'(?:section|§)\s*(\d+(?:\.\d+)?)'
            matches = re.findall(pattern, doc.get('title', '') + doc.get('content', ''))
            sections.update(matches)
        return list(sections)
    
    def _extract_requirements(self, docs: List[Dict]) -> List[str]:
        """Extract requirements from documents"""
        requirements = []
        for doc in docs:
            content = doc.get('content', '').lower()
            if 'must' in content or 'require' in content or 'shall' in content:
                # Simple extraction of requirement sentences
                requirements.append("Compliance requirement identified")
        return requirements
    
    def _extract_deadlines(self, docs: List[Dict]) -> List[str]:
        """Extract deadlines from documents"""
        deadlines = []
        for doc in docs:
            content = doc.get('content', '').lower()
            if 'deadline' in content or 'within' in content or 'days' in content:
                deadlines.append("Time-sensitive deadline identified")
        return deadlines
    
    def _analyze_case_law(self, state: AgentState) -> Dict:
        """Analyze case law documents"""
        return {
            'relevant_cases': [],
            'supporting_rulings': [],
            'conflicting_rulings': []
        }
    
    def _analyze_precedents(self, state: AgentState) -> Dict:
        """Analyze precedent transactions"""
        return {
            'similar_deals': [],
            'deal_structures': [],
            'success_patterns': []
        }
    
    def _analyze_expert_knowledge(self, state: AgentState) -> Dict:
        """Analyze expert knowledge"""
        return {
            'expert_consensus': [],
            'best_practices': [],
            'common_pitfalls': []
        }
    
    def _generate_executive_summary(self, analysis: Dict) -> str:
        """Generate executive summary from analysis"""
        return "Executive Summary: Comprehensive analysis of tax implications..."
    
    def _create_detailed_findings(self, analysis: Dict, state: AgentState) -> List[Dict]:
        """Create detailed findings with evidence"""
        return [
            {
                'finding': "Primary finding",
                'evidence': ["Evidence 1", "Evidence 2"],
                'confidence': 0.9
            }
        ]
    
    def _generate_action_plan(self, analysis: Dict, state: AgentState) -> List[Dict]:
        """Generate action plan"""
        return [
            {
                'action': "File Form 8023",
                'deadline': "Within 8.5 months",
                'priority': "High",
                'responsible_party': "Tax Team"
            }
        ]
    
    def _assess_risks(self, analysis: Dict, state: AgentState) -> Dict:
        """Assess risks"""
        return {
            'high_risks': [],
            'medium_risks': [],
            'low_risks': [],
            'mitigation_strategies': []
        }
    
    def _compile_comprehensive_citations(self, state: AgentState) -> List[str]:
        """Compile comprehensive citations"""
        citations = []
        for doc in state.retrieved_documents:
            if doc.get('title'):
                citations.append(doc['title'])
        return citations
    
    def _generate_metadata(self, state: AgentState) -> Dict:
        """Generate metadata for the response"""
        return {
            'processing_time': time.time() - state.start_time,
            'agents_used': list(state.agent_outputs.keys()),
            'documents_analyzed': len(state.retrieved_documents),
            'confidence_level': self._calculate_overall_confidence(state),
            'complexity': state.complexity.value
        }
    
    def _calculate_overall_confidence(self, state: AgentState) -> float:
        """Calculate overall confidence"""
        if not state.confidence_scores:
            return 0.0
        return sum(state.confidence_scores.values()) / len(state.confidence_scores)
    
    async def _multi_dimensional_analysis(self, state: AgentState) -> Dict:
        """Multi-dimensional analysis for expert queries"""
        return {
            'temporal_analysis': {},
            'regulatory_landscape': {},
            'precedent_patterns': {},
            'risk_matrix': {}
        }
    
    def _generate_comprehensive_report(self, analysis: Dict, state: AgentState) -> Dict:
        """Generate comprehensive report"""
        return {
            'executive_summary': "",
            'detailed_findings': [],
            'recommendations': [],
            'appendices': []
        }
    
    def _create_decision_matrix(self, analysis: Dict) -> Dict:
        """Create decision matrix"""
        return {
            'options': [],
            'criteria': [],
            'scores': {},
            'recommendation': ""
        }
    
    def _generate_scenarios(self, analysis: Dict, state: AgentState) -> List[Dict]:
        """Generate scenario analysis"""
        return [
            {
                'scenario': "Best case",
                'probability': 0.3,
                'impact': "Positive",
                'recommendations': []
            }
        ]
    
    def _consolidate_expert_opinions(self, state: AgentState) -> List[Dict]:
        """Consolidate expert opinions"""
        return []
    
    def _detailed_confidence_analysis(self, state: AgentState) -> Dict:
        """Detailed confidence analysis"""
        return {
            'overall_confidence': 0.0,
            'confidence_factors': {},
            'uncertainty_areas': []
        }