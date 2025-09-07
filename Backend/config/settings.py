from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # App config
    app_env: str = "development"
    log_level: str = "INFO"
    
    # Database
    supabase_url: str
    supabase_key: str
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    
    # API Keys
    openai_api_key: str
    
    # Performance
    confidence_threshold: float = 0.80
    max_query_time: int = 20
    agent_timeout: int = 8
    
    google_search_api_key: str 
    google_cse_id: str 
    web_search_enabled: bool 
    irs_api_enabled: bool 
    
    # Vector Search
    embedding_dim: int = 1536
    top_k_results: int = 10
    similarity_threshold: float = 0.75
    
    class Config:
        env_file = ".env"