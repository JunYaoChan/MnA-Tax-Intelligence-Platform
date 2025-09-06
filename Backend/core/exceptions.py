class TaxRAGException(Exception):
    """Base exception for Tax RAG system"""
    pass

class QueryProcessingError(TaxRAGException):
    """Error during query processing"""
    pass

class AgentExecutionError(TaxRAGException):
    """Error during agent execution"""
    pass

class DatabaseConnectionError(TaxRAGException):
    """Database connection error"""
    pass

class VectorSearchError(TaxRAGException):
    """Vector search error"""
    pass

class SynthesisError(TaxRAGException):
    """Error during result synthesis"""
    pass

class ConfigurationError(TaxRAGException):
    """Configuration error"""
    pass

class RateLimitError(TaxRAGException):
    """Rate limit exceeded"""
    pass

class TimeoutError(TaxRAGException):
    """Operation timeout"""
    pass