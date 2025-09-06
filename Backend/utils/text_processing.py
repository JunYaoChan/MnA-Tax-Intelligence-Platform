import re
from typing import List, Dict, Any
import string

class TextProcessor:
    """Utilities for text processing"""
    
    @staticmethod
    def clean_query(query: str) -> str:
        """Clean and normalize query text"""
        # Remove extra whitespace
        query = ' '.join(query.split())
        
        # Remove special characters except essential ones
        query = re.sub(r'[^\w\s\-§().,]', '', query)
        
        return query.strip()
    
    @staticmethod
    def extract_section_references(text: str) -> List[str]:
        """Extract tax code section references"""
        patterns = [
            r'(?:section|§)\s*(\d+(?:\.\d+)?(?:\([a-z]\))?(?:\(\d+\))?)',
            r'26\s*(?:USC|U\.S\.C\.)\s*§?\s*(\d+)',
            r'(?:reg|regulation)\s*(\d+(?:\.\d+)?(?:-\d+)?)',
            r'IRC\s*§?\s*(\d+)'
        ]
        
        references = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            references.extend(matches)
        
        return list(set(references))
    
    @staticmethod
    def extract_dates(text: str) -> List[str]:
        """Extract dates from text"""
        date_patterns = [
            r'\d{1,2}/\d{1,2}/\d{2,4}',
            r'\d{4}-\d{2}-\d{2}',
            r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}'
        ]
        
        dates = []
        for pattern in date_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            dates.extend(matches)
        
        return dates
    
    @staticmethod
    def extract_monetary_values(text: str) -> List[Dict[str, Any]]:
        """Extract monetary values from text"""
        pattern = r'\$\s*(\d+(?:,\d{3})*(?:\.\d{2})?)\s*([MB])?(?:illion)?'
        
        values = []
        for match in re.finditer(pattern, text):
            amount = float(match.group(1).replace(',', ''))
            
            # Handle millions/billions
            if match.group(2):
                if match.group(2).upper() == 'M':
                    amount *= 1_000_000
                elif match.group(2).upper() == 'B':
                    amount *= 1_000_000_000
            
            values.append({
                'raw': match.group(0),
                'amount': amount,
                'formatted': f"${amount:,.2f}"
            })
        
        return values
    
    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Simple tokenization"""
        # Remove punctuation and convert to lowercase
        text = text.translate(str.maketrans('', '', string.punctuation))
        tokens = text.lower().split()
        
        # Remove stop words (simplified)
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for'}
        tokens = [t for t in tokens if t not in stop_words]
        
        return tokens
    
    @staticmethod
    def calculate_similarity(text1: str, text2: str) -> float:
        """Calculate simple text similarity"""
        tokens1 = set(TextProcessor.tokenize(text1))
        tokens2 = set(TextProcessor.tokenize(text2))
        
        if not tokens1 or not tokens2:
            return 0.0
        
        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)
        
        return len(intersection) / len(union)
