# Backend/config/settings.py
import os
from typing import Optional, List
from dataclasses import dataclass, field
from dotenv import load_dotenv
from models.enums import QueryComplexity

# Load environment variables from .env file
load_dotenv()

@dataclass
class Settings:
    """Enhanced configuration settings for RAG pipeline"""
    
    # Database Configuration
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_key: str = os.getenv("SUPABASE_KEY", "")
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "")
    
    # API Keys for Function Tools
    brave_search_api_key: str = os.getenv("BRAVE_SEARCH_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    
    # LLM Configuration
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4")
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "2000"))
    
    # RAG Pipeline Configuration
    top_k_results: int = int(os.getenv("TOP_K_RESULTS", "10"))
    min_docs_threshold: int = int(os.getenv("MIN_DOCS_THRESHOLD", "3"))
    quality_threshold: int = int(os.getenv("QUALITY_THRESHOLD", "2"))
    confidence_threshold: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.6"))
    
    # Agent Configuration
    agent_timeout: int = int(os.getenv("AGENT_TIMEOUT", "30"))
    max_parallel_agents: int = int(os.getenv("MAX_PARALLEL_AGENTS", "4"))
    
    # Vector Search Configuration
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")
    vector_similarity_threshold: float = float(os.getenv("VECTOR_SIMILARITY_THRESHOLD", "0.7"))
    use_supabase_rpc: bool = os.getenv("USE_SUPABASE_RPC", "false").lower() == "true"
    # Hybrid Search Configuration
    enable_hybrid_search: bool = os.getenv("ENABLE_HYBRID_SEARCH", "false").lower() == "true"
    hybrid_alpha: float = float(os.getenv("HYBRID_ALPHA", "0.5"))  # weight for vector vs lexical
    hybrid_lexical_top_k: int = int(os.getenv("HYBRID_LEXICAL_TOP_K", "20"))
    
    # Enhanced Brave Search Configuration
    brave_search_count: int = int(os.getenv("BRAVE_SEARCH_COUNT", "10"))
    brave_search_freshness: str = os.getenv("BRAVE_SEARCH_FRESHNESS", "month")
    brave_search_max_query_length: int = int(os.getenv("BRAVE_SEARCH_MAX_QUERY_LENGTH", "400"))
    brave_search_max_retries: int = int(os.getenv("BRAVE_SEARCH_MAX_RETRIES", "3"))
    brave_search_timeout: int = int(os.getenv("BRAVE_SEARCH_TIMEOUT", "30"))
    brave_search_rate_limit: int = int(os.getenv("BRAVE_SEARCH_RATE_LIMIT", "60"))  # per minute
    
    # Function Tools Configuration
    enable_llm_enhancement: bool = os.getenv("ENABLE_LLM_ENHANCEMENT", "true").lower() == "true"
    enable_external_search: bool = os.getenv("ENABLE_EXTERNAL_SEARCH", "true").lower() == "true"
    enable_specialized_tools: bool = os.getenv("ENABLE_SPECIALIZED_TOOLS", "true").lower() == "true"
    
    # Query Processing Configuration
    max_query_length: int = int(os.getenv("MAX_QUERY_LENGTH", "2000"))
    enable_query_splitting: bool = os.getenv("ENABLE_QUERY_SPLITTING", "true").lower() == "true"
    max_split_queries: int = int(os.getenv("MAX_SPLIT_QUERIES", "3"))
    
    # Rate Limiting
    api_rate_limit: int = int(os.getenv("API_RATE_LIMIT", "100"))  # requests per minute
    search_rate_limit: int = int(os.getenv("SEARCH_RATE_LIMIT", "50"))  # searches per minute
    
    # Caching
    enable_caching: bool = os.getenv("ENABLE_CACHING", "true").lower() == "true"
    cache_ttl: int = int(os.getenv("CACHE_TTL", "3600"))  # seconds
    
    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_file: str = os.getenv("LOG_FILE", "logs/tax_rag.log")
    
    # Development and Testing
    debug_mode: bool = os.getenv("DEBUG_MODE", "false").lower() == "true"
    test_mode: bool = os.getenv("TEST_MODE", "false").lower() == "true"
    
    # Health Check Configuration
    health_check_interval: int = int(os.getenv("HEALTH_CHECK_INTERVAL", "300"))  # seconds
    health_check_timeout: int = int(os.getenv("HEALTH_CHECK_TIMEOUT", "10"))  # seconds
    
    def validate(self) -> bool:
        """Enhanced validation of configuration settings"""
        errors = []
        warnings = []
        
        # Required settings
        if not self.supabase_url:
            errors.append("SUPABASE_URL is required")
        
        if not self.supabase_key:
            errors.append("SUPABASE_KEY is required")
        
        if not self.openai_api_key:
            errors.append("OPENAI_API_KEY is required")
        
        # Brave Search validation
        if self.enable_external_search:
            if not self.brave_search_api_key:
                errors.append("BRAVE_SEARCH_API_KEY is required when external search is enabled")
            
            if self.brave_search_max_query_length > 400:
                errors.append("BRAVE_SEARCH_MAX_QUERY_LENGTH cannot exceed 400 characters (API limit)")
            
            if self.brave_search_count > 20:
                warnings.append("BRAVE_SEARCH_COUNT > 20 will be capped at 20 (API limit)")
                self.brave_search_count = 20
            
            valid_freshness = ["all", "day", "week", "month", "year"]
            if self.brave_search_freshness not in valid_freshness:
                warnings.append(f"Invalid BRAVE_SEARCH_FRESHNESS '{self.brave_search_freshness}', using 'month'")
                self.brave_search_freshness = "month"
        
        # Validate numeric ranges
        if not (0.0 <= self.confidence_threshold <= 1.0):
            errors.append("CONFIDENCE_THRESHOLD must be between 0.0 and 1.0")
        
        if not (0.0 <= self.vector_similarity_threshold <= 1.0):
            errors.append("VECTOR_SIMILARITY_THRESHOLD must be between 0.0 and 1.0")
        # Hybrid search validation
        if not (0.0 <= self.hybrid_alpha <= 1.0):
            errors.append("HYBRID_ALPHA must be between 0.0 and 1.0")
        if self.hybrid_lexical_top_k <= 0:
            errors.append("HYBRID_LEXICAL_TOP_K must be positive")
        
        if self.agent_timeout <= 0:
            errors.append("AGENT_TIMEOUT must be positive")
        
        if self.max_query_length < 10:
            errors.append("MAX_QUERY_LENGTH must be at least 10 characters")
        
        if self.max_query_length > 10000:
            warnings.append("MAX_QUERY_LENGTH > 10000 may cause performance issues")
        
        # Rate limiting validation
        if self.api_rate_limit <= 0:
            errors.append("API_RATE_LIMIT must be positive")
        
        if self.search_rate_limit <= 0:
            errors.append("SEARCH_RATE_LIMIT must be positive")
        
        # Log warnings
        for warning in warnings:
            print(f"WARNING: {warning}")
        
        # Raise errors
        if errors:
            raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")
        
        return True
    
    def get_brave_search_config(self) -> dict:
        """Get Brave Search specific configuration"""
        return {
            "api_key": self.brave_search_api_key,
            "max_query_length": self.brave_search_max_query_length,
            "max_retries": self.brave_search_max_retries,
            "timeout": self.brave_search_timeout,
            "default_count": self.brave_search_count,
            "default_freshness": self.brave_search_freshness,
            "rate_limit": self.brave_search_rate_limit
        }
    
    def get_function_tools_config(self) -> dict:
        """Get function tools configuration"""
        return {
            "enable_llm_enhancement": self.enable_llm_enhancement,
            "enable_external_search": self.enable_external_search,
            "enable_specialized_tools": self.enable_specialized_tools,
            "enable_query_splitting": self.enable_query_splitting,
            "max_split_queries": self.max_split_queries
        }
    
    @classmethod
    def from_env_file(cls, env_file: str = ".env"):
        """Create settings from specific env file"""
        load_dotenv(env_file)
        return cls()
    
    def to_dict(self) -> dict:
        """Convert settings to dictionary (excluding sensitive data)"""
        sensitive_fields = {
            "supabase_key", "brave_search_api_key", "openai_api_key", "neo4j_password"
        }
        
        return {
            k: v for k, v in self.__dict__.items() 
            if k not in sensitive_fields
        }

# Global settings instance
settings = Settings()

# Validate settings on import
try:
    settings.validate()
    print("✓ Configuration validation passed")
except ValueError as e:
    print(f"✗ Configuration validation failed: {e}")
    raise
