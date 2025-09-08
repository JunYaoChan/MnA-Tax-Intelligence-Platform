# Backend/utils/query_processor.py
import re
import logging
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class QueryAnalysis:
    """Analysis of a query for optimal processing"""
    original_query: str
    processed_query: str
    complexity: str  # simple, moderate, complex
    requires_splitting: bool
    suggested_sub_queries: List[str]
    estimated_search_count: int
    key_terms: List[str]
    search_strategy: str

class QueryProcessor:
    """Enhanced query processor for optimal Brave Search usage"""
    
    def __init__(self, max_query_length: int = 400):
        self.max_query_length = max_query_length
        self.tax_terms = {
            # Common tax entities
            'entities': ['Section', 'IRC', 'IRS', 'Treasury', 'Regulation', 'Revenue', 'PLR'],
            
            # Transaction types
            'transactions': ['merger', 'acquisition', 'reorganization', 'spin-off', 'split-off'],
            
            # Tax concepts
            'concepts': ['election', 'carryforward', 'NOL', 'GILTI', 'transfer pricing', 'consolidated'],
            
            # Legal terms
            'legal': ['precedent', 'ruling', 'procedure', 'guidance', 'interpretation']
        }
    
    def analyze_query(self, query: str) -> QueryAnalysis:
        """Analyze query and determine optimal processing strategy"""
        
        # Clean and normalize query
        processed_query = self._clean_query(query)
        
        # Determine complexity
        complexity = self._assess_complexity(processed_query)
        
        # Check if splitting is needed
        requires_splitting = len(processed_query) > self.max_query_length
        
        # Extract key terms
        key_terms = self._extract_key_terms(processed_query)
        
        # Generate sub-queries if needed
        sub_queries = []
        if requires_splitting:
            sub_queries = self._generate_sub_queries(processed_query, key_terms)
        
        # Determine search strategy
        search_strategy = self._determine_search_strategy(complexity, requires_splitting)
        
        # Estimate search count needed
        estimated_search_count = len(sub_queries) if sub_queries else 1
        
        return QueryAnalysis(
            original_query=query,
            processed_query=processed_query,
            complexity=complexity,
            requires_splitting=requires_splitting,
            suggested_sub_queries=sub_queries,
            estimated_search_count=estimated_search_count,
            key_terms=key_terms,
            search_strategy=search_strategy
        )
    
    def _clean_query(self, query: str) -> str:
        """Clean and normalize the query"""
        # Remove excessive whitespace
        query = ' '.join(query.split())
        
        # Remove special characters that might cause issues
        query = re.sub(r'[^\w\s\-\(\)\.\,\"\']', ' ', query)
        
        # Normalize common tax terms
        query = self._normalize_tax_terms(query)
        
        return query.strip()
    
    def _normalize_tax_terms(self, query: str) -> str:
        """Normalize common tax terms for better search results"""
        replacements = {
            'Section 338(h)(10)': 'Section 338 h 10',
            'Section 338': 'IRC Section 338',
            'Tax Cuts and Jobs Act': 'TCJA',
            'Net Operating Loss': 'NOL',
            'Private Letter Ruling': 'PLR',
            'Revenue Ruling': 'Rev Rul',
            'Revenue Procedure': 'Rev Proc'
        }
        
        for original, replacement in replacements.items():
            query = re.sub(re.escape(original), replacement, query, flags=re.IGNORECASE)
        
        return query
    
    def _assess_complexity(self, query: str) -> str:
        """Assess query complexity based on length and content"""
        word_count = len(query.split())
        char_count = len(query)
        
        # Count tax-specific terms
        tax_term_count = 0
        for category, terms in self.tax_terms.items():
            for term in terms:
                if term.lower() in query.lower():
                    tax_term_count += 1
        
        # Complexity scoring
        if char_count > 300 or word_count > 50 or tax_term_count > 8:
            return "complex"
        elif char_count > 150 or word_count > 25 or tax_term_count > 4:
            return "moderate"
        else:
            return "simple"
    
    def _extract_key_terms(self, query: str) -> List[str]:
        """Extract key terms for focused searching"""
        # Extract quoted phrases
        quoted_phrases = re.findall(r'"([^"]*)"', query)
        
        # Extract important terms
        words = re.findall(r'\b\w+\b', query)
        key_terms = []
        
        # Add quoted phrases
        key_terms.extend(quoted_phrases)
        
        # Add tax-specific terms
        for word in words:
            if self._is_important_term(word):
                key_terms.append(word)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_terms = []
        for term in key_terms:
            if term.lower() not in seen:
                unique_terms.append(term)
                seen.add(term.lower())
        
        return unique_terms[:15]  # Limit to top 15 terms
    
    def _is_important_term(self, word: str) -> bool:
        """Determine if a word is important for tax research"""
        # Check against tax term categories
        for category, terms in self.tax_terms.items():
            if word.lower() in [term.lower() for term in terms]:
                return True
        
        # Check for numbers (section numbers, years, etc.)
        if re.match(r'\d+', word):
            return True
        
        # Check for capitalized words (proper nouns)
        if word[0].isupper() and len(word) > 3:
            return True
        
        # Check for long words (likely technical terms)
        if len(word) > 8:
            return True
        
        return False
    
    def _generate_sub_queries(self, query: str, key_terms: List[str]) -> List[str]:
        """Generate focused sub-queries from a complex query"""
        sub_queries = []
        
        # Strategy 1: Group related terms
        term_groups = self._group_related_terms(key_terms)
        
        for group in term_groups[:3]:  # Limit to 3 sub-queries
            sub_query = ' '.join(group)
            if len(sub_query) <= self.max_query_length:
                sub_queries.append(sub_query)
        
        # Strategy 2: If grouping doesn't work, create focused queries
        if not sub_queries:
            # Core tax concepts
            tax_concepts = [term for term in key_terms if any(
                tax_term.lower() in term.lower() 
                for tax_term in self.tax_terms['concepts'] + self.tax_terms['entities']
            )]
            
            if tax_concepts:
                core_query = ' '.join(tax_concepts[:5])
                if len(core_query) <= self.max_query_length:
                    sub_queries.append(core_query)
            
            # Transaction-specific terms
            transaction_terms = [term for term in key_terms if any(
                tax_term.lower() in term.lower() 
                for tax_term in self.tax_terms['transactions']
            )]
            
            if transaction_terms:
                transaction_query = ' '.join(transaction_terms[:5])
                if len(transaction_query) <= self.max_query_length:
                    sub_queries.append(transaction_query)
        
        # Fallback: Just split by length
        if not sub_queries:
            words = query.split()
            chunk_size = self.max_query_length // 4  # Conservative chunk size
            
            current_chunk = []
            current_length = 0
            
            for word in words:
                if current_length + len(word) + 1 <= chunk_size:
                    current_chunk.append(word)
                    current_length += len(word) + 1
                else:
                    if current_chunk:
                        sub_queries.append(' '.join(current_chunk))
                    current_chunk = [word]
                    current_length = len(word)
                    
                    if len(sub_queries) >= 3:
                        break
            
            if current_chunk and len(sub_queries) < 3:
                sub_queries.append(' '.join(current_chunk))
        
        return sub_queries
    
    def _group_related_terms(self, terms: List[str]) -> List[List[str]]:
        """Group related terms together"""
        groups = []
        
        # Group by tax categories
        for category, category_terms in self.tax_terms.items():
            group = []
            for term in terms:
                if any(cat_term.lower() in term.lower() for cat_term in category_terms):
                    group.append(term)
            
            if group:
                groups.append(group[:5])  # Limit group size
        
        # Add remaining terms to a general group
        used_terms = set()
        for group in groups:
            used_terms.update(term.lower() for term in group)
        
        remaining_terms = [term for term in terms if term.lower() not in used_terms]
        if remaining_terms:
            groups.append(remaining_terms[:5])
        
        return groups
    
    def _determine_search_strategy(self, complexity: str, requires_splitting: bool) -> str:
        """Determine the optimal search strategy"""
        if requires_splitting:
            return "multi_query"
        elif complexity == "complex":
            return "comprehensive"
        elif complexity == "moderate":
            return "focused"
        else:
            return "simple"

# Example usage and testing
async def example_usage():
    """Example of how to use the enhanced Brave Search system"""
    
    # Initialize processor
    processor = QueryProcessor()
    
    # Your original problematic query
    complex_query = """
    Analyze the tax implications of a complex cross-border merger involving a US parent 
    company acquiring a German subsidiary through a Section 338(h)(10) election, considering 
    the impact on NOL carryforwards, international tax planning strategies, transfer pricing 
    implications, and the interaction with the GILTI provisions under the Tax Cuts and Jobs Act. 
    What are the optimal structuring alternatives and their respective risk profiles?
    """
    
    # Analyze the query
    analysis = processor.analyze_query(complex_query)
    
    print(f"Original query length: {len(analysis.original_query)} characters")
    print(f"Processed query length: {len(analysis.processed_query)} characters")
    print(f"Complexity: {analysis.complexity}")
    print(f"Requires splitting: {analysis.requires_splitting}")
    print(f"Search strategy: {analysis.search_strategy}")
    print(f"Key terms: {analysis.key_terms}")
    print(f"Suggested sub-queries:")
    
    for i, sub_query in enumerate(analysis.suggested_sub_queries, 1):
        print(f"  {i}. {sub_query} ({len(sub_query)} chars)")
    
    # Simulate using the function registry
    # (This would be actual function calls in your system)
    
    print("\n" + "="*50)
    print("EXAMPLE SEARCH EXECUTION")
    print("="*50)
    
    # Example searches that would work
    example_searches = [
        "Section 338 h 10 election cross-border merger",
        "German subsidiary acquisition tax implications", 
        "NOL carryforwards international merger",
        "GILTI provisions TCJA transfer pricing"
    ]
    
    for i, search in enumerate(example_searches, 1):
        print(f"\nSearch {i}: '{search}' ({len(search)} chars)")
        print(f"✓ Under 400 character limit: {len(search) <= 400}")
        
        # This is where you would call your actual Brave Search
        # result = await brave_search(search, count=5)
        print(f"Would execute: brave_search('{search}', count=5)")

if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())