import os
from typing import Optional
from dataclasses import dataclass
from dotenv import load_dotenv
from models.enums import QueryComplexity

# Load environment variables from .env file
load_dotenv()

@dataclass
class Settings:
    """Configuration settings for RAG pipeline"""
    
    # Database Configuration
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_key: str = os.getenv("SUPABASE_KEY", "")
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "")
    
    # API Keys for Function Tools
    brave_search_api_key: str = os.getenv("BRAVE_SEARCH_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    
    # Remove old Google Search configuration
    # google_search_api_key: str = os.getenv("GOOGLE_SEARCH_API_KEY", "")
    # google_cse_id: str = os.getenv("GOOGLE_CSE_ID", "")
    
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
    
    # External Search Configuration
    brave_search_count: int = int(os.getenv("BRAVE_SEARCH_COUNT", "10"))
    brave_search_freshness: str = os.getenv("BRAVE_SEARCH_FRESHNESS", "month")  # all, day, week, month, year
    
    # Function Tools Configuration
    enable_llm_enhancement: bool = os.getenv("ENABLE_LLM_ENHANCEMENT", "true").lower() == "true"
    enable_external_search: bool = os.getenv("ENABLE_EXTERNAL_SEARCH", "true").lower() == "true"
    enable_specialized_tools: bool = os.getenv("ENABLE_SPECIALIZED_TOOLS", "true").lower() == "true"
    
    # Rate Limiting
    api_rate_limit: int = int(os.getenv("API_RATE_LIMIT", "100"))  # requests per minute
    search_rate_limit: int = int(os.getenv("SEARCH_RATE_LIMIT", "50"))  # searches per minute
    
    # Caching
    enable_caching: bool = os.getenv("ENABLE_CACHING", "true").lower() == "true"
    cache_ttl: int = int(os.getenv("CACHE_TTL", "3600"))  # seconds
    
    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_file: str = os.getenv("LOG_FILE", "logs/tax_rag.log")
    
    def validate(self) -> bool:
        """Validate configuration settings"""
        errors = []
        
        # Required settings
        if not self.supabase_url:
            errors.append("SUPABASE_URL is required")
        
        if not self.supabase_key:
            errors.append("SUPABASE_KEY is required")
        
        if not self.openai_api_key:
            errors.append("OPENAI_API_KEY is required")
        
        # Brave Search is required if external search is enabled
        if self.enable_external_search and not self.brave_search_api_key:
            errors.append("BRAVE_SEARCH_API_KEY is required when external search is enabled")
        
        # Validate numeric ranges
        if not (0.0 <= self.confidence_threshold <= 1.0):
            errors.append("CONFIDENCE_THRESHOLD must be between 0.0 and 1.0")
        
        if not (0.0 <= self.vector_similarity_threshold <= 1.0):
            errors.append("VECTOR_SIMILARITY_THRESHOLD must be between 0.0 and 1.0")
        
        if self.agent_timeout <= 0:
            errors.append("AGENT_TIMEOUT must be positive")
        
        if errors:
            raise ValueError(f"Configuration validation failed: {', '.join(errors)}")
        
        return True
