import re
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, validator
from core.constants import MAX_QUERY_LENGTH, Priority

class QueryValidator:
    """Validates and sanitizes query inputs"""
    
    @staticmethod
    def validate_query_text(query: str) -> str:
        """
        Validate and sanitize query text
        
        Args:
            query: Raw query text
            
        Returns:
            Sanitized query text
            
        Raises:
            ValueError: If query is invalid
        """
        if not query:
            raise ValueError("Query cannot be empty")
        
        # Check length
        if len(query) > MAX_QUERY_LENGTH:
            raise ValueError(f"Query exceeds maximum length of {MAX_QUERY_LENGTH} characters")
        
        # Remove potentially harmful characters
        sanitized = QueryValidator._sanitize_text(query)
        
        # Check if query still has content after sanitization
        if not sanitized or len(sanitized.strip()) < 3:
            raise ValueError("Query too short or contains only invalid characters")
        
        return sanitized
    
    @staticmethod
    def validate_section_reference(section: str) -> bool:
        """
        Validate tax code section reference
        
        Args:
            section: Section reference string
            
        Returns:
            True if valid section reference
        """
        # Pattern for valid section references
        patterns = [
            r'^\d+$',  # Simple number (e.g., "338")
            r'^\d+\.\d+$',  # With decimal (e.g., "1.338")
            r'^\d+\([a-z]\)$',  # With subsection (e.g., "338(h)")
            r'^\d+\([a-z]\)\(\d+\)$',  # With paragraph (e.g., "338(h)(10)")
            r'^\d+\.\d+\([a-z]\)$',  # Regulation format (e.g., "1.338(h)")
            r'^\d+\.\d+-\d+$',  # Regulation with suffix (e.g., "1.338-1")
        ]
        
        for pattern in patterns:
            if re.match(pattern, section.lower()):
                return True
        
        return False
    
    @staticmethod
    def validate_date(date_str: str) -> bool:
        """
        Validate date string
        
        Args:
            date_str: Date string
            
        Returns:
            True if valid date
        """
        # Common date patterns
        patterns = [
            r'^\d{4}-\d{2}-\d{2}$',  # ISO format
            r'^\d{1,2}/\d{1,2}/\d{4}$',  # US format
            r'^\d{1,2}-\d{1,2}-\d{4}$',  # Alternative format
        ]
        
        for pattern in patterns:
            if re.match(pattern, date_str):
                return True
        
        return False
    
    @staticmethod
    def validate_priority(priority: str) -> str:
        """
        Validate and normalize priority level
        
        Args:
            priority: Priority string
            
        Returns:
            Normalized priority
        """
        priority_lower = priority.lower()
        
        valid_priorities = [p.value for p in Priority]
        
        if priority_lower not in valid_priorities:
            raise ValueError(f"Invalid priority. Must be one of: {valid_priorities}")
        
        return priority_lower
    
    @staticmethod
    def _sanitize_text(text: str) -> str:
        """Sanitize text input"""
        # Remove control characters
        text = re.sub(r'[\x00-\x1F\x7F]', '', text)
        
        # Remove excessive whitespace
        text = ' '.join(text.split())
        
        # Remove potential SQL injection attempts
        sql_keywords = ['DROP', 'DELETE', 'INSERT', 'UPDATE', 'EXEC', 'EXECUTE']
        for keyword in sql_keywords:
            pattern = r'\b' + keyword + r'\b'
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # Remove potential script tags
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r'<[^>]+>', '', text)  # Remove all HTML tags
        
        return text.strip()

class FilterValidator:
    """Validates search filters"""
    
    @staticmethod
    def validate_filters(filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and sanitize search filters
        
        Args:
            filters: Raw filters dictionary
            
        Returns:
            Validated filters
        """
        validated = {}
        
        # Define allowed filter keys and their types
        allowed_filters = {
            'type': (list, str),
            'date_from': str,
            'date_to': str,
            'section': (list, str),
            'confidence_min': float,
            'author': str,
            'source': str
        }
        
        for key, value in filters.items():
            if key not in allowed_filters:
                continue  # Skip unknown filters
            
            expected_type = allowed_filters[key]
            
            # Validate type
            if not isinstance(value, expected_type):
                if isinstance(expected_type, tuple):
                    # Multiple allowed types
                    if not any(isinstance(value, t) for t in expected_type):
                        continue
                else:
                    continue
            
            # Validate specific filter values
            if key == 'type' and isinstance(value, list):
                # Validate document types
                validated[key] = [
                    v for v in value
                    if v in ['regulation', 'case_law', 'precedent', 'knowledge_base']
                ]
            
            elif key in ['date_from', 'date_to']:
                # Validate dates
                if QueryValidator.validate_date(value):
                    validated[key] = value
            
            elif key == 'section':
                # Validate section references
                if isinstance(value, list):
                    validated[key] = [
                        v for v in value
                        if QueryValidator.validate_section_reference(v)
                    ]
                elif QueryValidator.validate_section_reference(value):
                    validated[key] = value
            
            elif key == 'confidence_min':
                # Validate confidence threshold
                if 0 <= value <= 1:
                    validated[key] = value
            
            else:
                # For other filters, sanitize text
                if isinstance(value, str):
                    validated[key] = QueryValidator._sanitize_text(value)
                else:
                    validated[key] = value
        
        return validated

class ResponseValidator:
    """Validates API responses"""
    
    @staticmethod
    def validate_agent_result(result: Dict[str, Any]) -> bool:
        """
        Validate agent result structure
        
        Args:
            result: Agent result dictionary
            
        Returns:
            True if valid result
        """
        required_fields = ['documents', 'confidence', 'source', 'metadata', 'retrieval_time']
        
        # Check required fields
        for field in required_fields:
            if field not in result:
                return False
        
        # Validate types
        if not isinstance(result['documents'], list):
            return False
        
        if not isinstance(result['confidence'], (int, float)):
            return False
        
        if not 0 <= result['confidence'] <= 1:
            return False
        
        if not isinstance(result['source'], str):
            return False
        
        if not isinstance(result['metadata'], dict):
            return False
        
        if not isinstance(result['retrieval_time'], (int, float)):
            return False
        
        return True
    
    @staticmethod
    def validate_document(document: Dict[str, Any]) -> bool:
        """
        Validate document structure
        
        Args:
            document: Document dictionary
            
        Returns:
            True if valid document
        """
        required_fields = ['id', 'title', 'content']
        
        # Check required fields
        for field in required_fields:
            if field not in document:
                return False
        
        # Validate non-empty content
        if not document['content'] or not document['title']:
            return False
        
        return True
    
    @staticmethod
    def sanitize_response(response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize response before sending to client
        
        Args:
            response: Raw response dictionary
            
        Returns:
            Sanitized response
        """
        # Remove any sensitive information
        sensitive_keys = ['api_key', 'password', 'secret', 'token']
        
        def remove_sensitive(obj):
            if isinstance(obj, dict):
                return {
                    k: remove_sensitive(v)
                    for k, v in obj.items()
                    if not any(sensitive in k.lower() for sensitive in sensitive_keys)
                }
            elif isinstance(obj, list):
                return [remove_sensitive(item) for item in obj]
            else:
                return obj
        
        return remove_sensitive(response)

# Pydantic models for additional validation
class QueryRequestModel(BaseModel):
    """Pydantic model for query request validation"""
    
    text: str = Field(..., min_length=3, max_length=MAX_QUERY_LENGTH)
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    priority: str = Field(default="normal", regex="^(low|normal|high|urgent)$")
    include_sources: bool = Field(default=True)
    max_results: Optional[int] = Field(default=10, ge=1, le=50)
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    @validator('text')
    def validate_text(cls, v):
        """Validate and sanitize query text"""
        return QueryValidator.validate_query_text(v)
    
    @validator('filters')
    def validate_filters(cls, v):
        """Validate filters"""
        if v:
            return FilterValidator.validate_filters(v)
        return v

class ConfigValidator:
    """Validates configuration settings"""
    
    @staticmethod
    def validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate configuration settings
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Validated configuration
            
        Raises:
            ValueError: If configuration is invalid
        """
        required_fields = [
            'supabase_url',
            'supabase_key',
            'neo4j_uri',
            'openai_api_key'
        ]
        
        # Check required fields
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required configuration: {field}")
        
        # Validate URLs
        url_fields = ['supabase_url', 'neo4j_uri']
        for field in url_fields:
            if field in config:
                if not config[field].startswith(('http://', 'https://', 'bolt://')):
                    raise ValueError(f"Invalid URL format for {field}")
        
        # Validate numeric values
        numeric_fields = {
            'confidence_threshold': (0.0, 1.0),
            'max_query_time': (1, 300),
            'agent_timeout': (1, 60),
            'top_k_results': (1, 100),
            'similarity_threshold': (0.0, 1.0)
        }
        
        for field, (min_val, max_val) in numeric_fields.items():
            if field in config:
                value = config[field]
                if not isinstance(value, (int, float)):
                    raise ValueError(f"{field} must be numeric")
                if not min_val <= value <= max_val:
                    raise ValueError(f"{field} must be between {min_val} and {max_val}")
        
        return config