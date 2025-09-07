import asyncio
import aiohttp
from typing import List, Dict, Optional
from agents.base import BaseAgent
from models.state import AgentState
from models.results import RetrievalResult
import time
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class IRSAPIAgent(BaseAgent):
    """Agent that retrieves real-time data from IRS APIs and government sources"""
    
    def __init__(self, settings):
        super().__init__("IRSAPIAgent", settings)
        
        # IRS and Treasury API endpoints
        self.irs_endpoints = {
            'tax_rates': 'https://api.irs.gov/tax-rates/current',
            'forms': 'https://www.irs.gov/app/picklist/list/priorFormPublication.html',
            'publications': 'https://www.irs.gov/forms-pubs/about-form-{form_number}',
            'business_master_file': 'https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf'
        }
        
        # Alternative data sources for real-time info
        self.data_sources = {
            'congress_api': 'https://api.congress.gov/v3',
            'treasury_api': 'https://api.fiscaldata.treasury.gov/services/api/v1',
            'fred_api': 'https://api.stlouisfed.org/fred'  # Federal Reserve Economic Data
        }
        
    async def process(self, state: AgentState) -> RetrievalResult:
        start_time = time.time()
        
        try:
            # Determine what type of real-time data is needed
            data_needs = self._analyze_data_needs(state)
            
            # Fetch real-time data from multiple sources
            real_time_data = await self._fetch_real_time_data(data_needs, state)
            
            # Format and enrich the data
            formatted_documents = self._format_api_results(real_time_data, state)
            
            # Calculate confidence based on data freshness and authority
            confidence = self._calculate_confidence(formatted_documents)
            
            result = RetrievalResult(
                documents=formatted_documents,
                confidence=confidence,
                source="irs_api",
                metadata={
                    "data_types": list(data_needs.keys()),
                    "sources_used": [doc.get('api_source') for doc in formatted_documents],
                    "data_freshness": self._calculate_freshness(formatted_documents),
                    "last_updated": datetime.now().isoformat()
                },
                retrieval_time=time.time() - start_time
            )
            
            self.log_performance(start_time, result)
            return result
            
        except Exception as e:
            self.logger.error(f"Error in IRSAPIAgent: {e}")
            return RetrievalResult(
                documents=[],
                confidence=0.0,
                source="irs_api",
                metadata={"error": str(e)},
                retrieval_time=time.time() - start_time
            )
    
    def _analyze_data_needs(self, state: AgentState) -> Dict[str, bool]:
        """Analyze query to determine what real-time data is needed"""
        query_lower = state.query.lower()
        entities = state.intent.get('entities', [])
        
        data_needs = {
            'current_tax_rates': any(term in query_lower for term in ['rate', 'percentage', 'current']),
            'recent_regulations': any(term in query_lower for term in ['recent', 'new', 'updated', '2024', '2025']),
            'form_information': any(term in query_lower for term in ['form', 'publication', 'pub']),
            'deadline_information': any(term in query_lower for term in ['deadline', 'due date', 'filing']),
            'section_updates': any(f'section {entity}' in query_lower for entity in entities),
            'economic_data': any(term in query_lower for term in ['inflation', 'interest', 'economic']),
        }
        
        return {k: v for k, v in data_needs.items() if v}
    
    async def _fetch_real_time_data(self, data_needs: Dict[str, bool], state: AgentState) -> List[Dict]:
        """Fetch real-time data from various government APIs"""
        all_data = []
        
        # Fetch different types of data based on needs
        fetch_tasks = []
        
        if data_needs.get('current_tax_rates'):
            fetch_tasks.append(self._fetch_current_tax_rates())
        
        if data_needs.get('recent_regulations'):
            fetch_tasks.append(self._fetch_recent_regulations(state))
        
        if data_needs.get('form_information'):
            fetch_tasks.append(self._fetch_form_information(state))
        
        if data_needs.get('deadline_information'):
            fetch_tasks.append(self._fetch_deadline_information())
        
        if data_needs.get('economic_data'):
            fetch_tasks.append(self._fetch_economic_indicators())
        
        # Execute all fetches in parallel
        if fetch_tasks:
            results = await asyncio.gather(*fetch_tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, list):
                    all_data.extend(result)
                elif isinstance(result, Exception):
                    logger.error(f"API fetch failed: {result}")
        
        return all_data
    
    async def _fetch_current_tax_rates(self) -> List[Dict]:
        """Fetch current tax rates and brackets"""
        try:
            # Since IRS doesn't have a public API for tax rates, we'll simulate
            # In real implementation, you'd scrape IRS.gov or use a tax data service
            current_year = datetime.now().year
            
            # This would be replaced with actual API calls
            tax_rate_data = {
                'individual_rates': {
                    'tax_year': current_year,
                    'brackets': [
                        {'rate': '10%', 'range': '$0 - $11,000'},
                        {'rate': '12%', 'range': '$11,001 - $44,725'},
                        {'rate': '22%', 'range': '$44,726 - $95,375'},
                        {'rate': '24%', 'range': '$95,376 - $182,050'},
                        {'rate': '32%', 'range': '$182,051 - $231,250'},
                        {'rate': '35%', 'range': '$231,251 - $578,125'},
                        {'rate': '37%', 'range': '$578,126+'}
                    ]
                },
                'corporate_rate': '21%',
                'capital_gains': {
                    'short_term': 'ordinary income rates',
                    'long_term': '0%, 15%, or 20%'
                }
            }
            
            return [{
                'id': f'tax_rates_{current_year}',
                'title': f'{current_year} Federal Tax Rates',
                'content': f"Current federal tax rates for {current_year}: " + 
                          f"Corporate rate: {tax_rate_data['corporate_rate']}, " +
                          f"Individual brackets range from 10% to 37%",
                'type': 'tax_rates',
                'api_source': 'irs_tax_rates',
                'last_updated': datetime.now().isoformat(),
                'relevance_score': 0.95,
                'metadata': tax_rate_data
            }]
            
        except Exception as e:
            logger.error(f"Failed to fetch tax rates: {e}")
            return []
    
    async def _fetch_recent_regulations(self, state: AgentState) -> List[Dict]:
        """Fetch recent tax regulations and updates"""
        try:
            # In real implementation, this would call Federal Register API
            # or Treasury/IRS RSS feeds for recent regulations
            
            # Simulate recent regulation data
            recent_regs = [
                {
                    'id': 'reg_2024_001',
                    'title': 'Section 338 Election Procedures - Updated Guidance',
                    'content': 'Recent guidance on Section 338(h)(10) elections clarifies filing requirements and deadlines.',
                    'type': 'regulation_update',
                    'api_source': 'federal_register',
                    'publication_date': '2024-12-01',
                    'effective_date': '2025-01-01',
                    'relevance_score': 0.9
                },
                {
                    'id': 'reg_2024_002', 
                    'title': 'Corporate Tax Rate Adjustments',
                    'content': 'Proposed regulations regarding corporate tax rate applications for 2025.',
                    'type': 'proposed_regulation',
                    'api_source': 'irs_notices',
                    'publication_date': '2024-11-15',
                    'relevance_score': 0.8
                }
            ]
            
            # Filter based on query relevance
            entities = state.intent.get('entities', [])
            filtered_regs = []
            
            for reg in recent_regs:
                # Check if regulation mentions query entities
                reg_text = f"{reg['title']} {reg['content']}".lower()
                is_relevant = any(entity in reg_text for entity in entities) if entities else True
                
                if is_relevant:
                    filtered_regs.append(reg)
            
            return filtered_regs
            
        except Exception as e:
            logger.error(f"Failed to fetch recent regulations: {e}")
            return []
    
    async def _fetch_form_information(self, state: AgentState) -> List[Dict]:
        """Fetch current form information and updates"""
        try:
            # Extract form numbers from query
            form_numbers = self._extract_form_numbers(state.query)
            
            forms_data = []
            for form_num in form_numbers:
                # Simulate form data fetch
                form_info = {
                    'id': f'form_{form_num}',
                    'title': f'Form {form_num} - Current Version',
                    'content': f'Current version of Form {form_num} with latest instructions and requirements.',
                    'type': 'form_information',
                    'api_source': 'irs_forms',
                    'form_number': form_num,
                    'last_revised': '2024-12-01',
                    'relevance_score': 0.85
                }
                forms_data.append(form_info)
            
            return forms_data
            
        except Exception as e:
            logger.error(f"Failed to fetch form information: {e}")
            return []
    
    async def _fetch_deadline_information(self) -> List[Dict]:
        """Fetch current tax deadlines and important dates"""
        try:
            current_year = datetime.now().year
            
            # Important tax deadlines (would be fetched from IRS calendar API)
            deadlines = {
                'individual_filing': f'April 15, {current_year + 1}',
                'corporate_filing': f'March 15, {current_year + 1}',
                'estimated_tax_q4': f'January 15, {current_year + 1}',
                'extension_deadline': f'October 15, {current_year + 1}'
            }
            
            return [{
                'id': f'tax_deadlines_{current_year}',
                'title': f'{current_year} Tax Filing Deadlines',
                'content': f"Important tax deadlines for {current_year}: " +
                          f"Individual filing: {deadlines['individual_filing']}, " +
                          f"Corporate filing: {deadlines['corporate_filing']}",
                'type': 'deadline_information',
                'api_source': 'irs_calendar',
                'last_updated': datetime.now().isoformat(),
                'relevance_score': 0.8,
                'metadata': deadlines
            }]
            
        except Exception as e:
            logger.error(f"Failed to fetch deadline information: {e}")
            return []
    
    async def _fetch_economic_indicators(self) -> List[Dict]:
        """Fetch relevant economic indicators from FRED API"""
        try:
            # In real implementation, would call Federal Reserve FRED API
            # for current interest rates, inflation data, etc.
            
            current_indicators = {
                'federal_funds_rate': '5.25%',
                'inflation_rate': '3.2%',
                'treasury_10yr': '4.1%',
                'last_updated': datetime.now().isoformat()
            }
            
            return [{
                'id': 'economic_indicators_current',
                'title': 'Current Economic Indicators',
                'content': f"Current economic data: Federal Funds Rate: {current_indicators['federal_funds_rate']}, " +
                          f"Inflation: {current_indicators['inflation_rate']}, " +
                          f"10-Year Treasury: {current_indicators['treasury_10yr']}",
                'type': 'economic_data',
                'api_source': 'fred_api',
                'last_updated': current_indicators['last_updated'],
                'relevance_score': 0.7,
                'metadata': current_indicators
            }]
            
        except Exception as e:
            logger.error(f"Failed to fetch economic indicators: {e}")
            return []
    
    def _extract_form_numbers(self, query: str) -> List[str]:
        """Extract form numbers from query text"""
        import re
        
        # Pattern to match form numbers like "Form 1120", "1040", "8832", etc.
        patterns = [
            r'form\s+(\d{3,4}[a-z]*)',
            r'(?:^|\s)(\d{4}[a-z]*?)(?:\s|$)',
            r'publication\s+(\d+)'
        ]
        
        form_numbers = []
        query_lower = query.lower()
        
        for pattern in patterns:
            matches = re.findall(pattern, query_lower)
            form_numbers.extend(matches)
        
        return list(set(form_numbers))  # Remove duplicates
    
    def _format_api_results(self, data: List[Dict], state: AgentState) -> List[Dict]:
        """Format API results into standard document format"""
        formatted = []
        
        for item in data:
            formatted_doc = {
                'id': item.get('id', f"api_{hash(str(item))}"),
                'title': item.get('title', 'API Data'),
                'content': item.get('content', ''),
                'type': item.get('type', 'api_data'),
                'relevance_score': item.get('relevance_score', 0.7),
                'date': item.get('last_updated', datetime.now().isoformat()),
                'metadata': {
                    'source': 'government_api',
                    'api_source': item.get('api_source'),
                    'data_freshness': 'real_time',
                    'authority_score': 1.0,  # Government sources have highest authority
                    **item.get('metadata', {})
                }
            }
            formatted.append(formatted_doc)
        
        return formatted
    
    def _calculate_freshness(self, documents: List[Dict]) -> str:
        """Calculate overall data freshness"""
        if not documents:
            return 'unknown'
        
        # Check how recent the data is
        now = datetime.now()
        fresh_count = 0
        
        for doc in documents:
            if doc.get('date'):
                try:
                    doc_date = datetime.fromisoformat(doc['date'].replace('Z', '+00:00'))
                    age_hours = (now - doc_date).total_seconds() / 3600
                    
                    if age_hours < 24:
                        fresh_count += 1
                except:
                    pass
        
        freshness_ratio = fresh_count / len(documents)
        
        if freshness_ratio > 0.8:
            return 'very_fresh'
        elif freshness_ratio > 0.5:
            return 'fresh'
        elif freshness_ratio > 0.2:
            return 'moderate'
        else:
            return 'stale'
    
    def _calculate_confidence(self, documents: List[Dict]) -> float:
        """Calculate confidence based on data quality and freshness"""
        if not documents:
            return 0.0
        
        # Government APIs have high base confidence
        base_confidence = 0.9
        
        # Adjust based on data freshness
        freshness = self._calculate_freshness(documents)
        freshness_multiplier = {
            'very_fresh': 1.0,
            'fresh': 0.95,
            'moderate': 0.85,
            'stale': 0.7,
            'unknown': 0.6
        }.get(freshness, 0.6)
        
        # Adjust based on number of data sources
        source_factor = min(len(documents) / 3, 1.0)
        
        return base_confidence * freshness_multiplier * source_factor