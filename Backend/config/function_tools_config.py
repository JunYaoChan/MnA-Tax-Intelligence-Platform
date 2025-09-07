from typing import Dict, List, Any
from dataclasses import dataclass

@dataclass
class FunctionToolConfig:
    """Configuration for function tools"""
    
    # Brave Search Configuration
    brave_search_config = {
        "default_count": 10,
        "max_count": 50,
        "supported_freshness": ["all", "day", "week", "month", "year"],
        "supported_countries": ["US", "UK", "CA", "AU"],
        "rate_limit_per_minute": 60
    }
    
    # LLM Enhancer Configuration
    llm_enhancer_config = {
        "batch_size": 3,
        "max_tokens_per_batch": 2000,
        "temperature": 0.3,
        "enhancement_timeout": 30
    }
    
    # IRS API Configuration
    irs_api_config = {
        "supported_document_types": [
            "revenue_ruling",
            "private_letter_ruling", 
            "revenue_procedure",
            "technical_advice_memorandum",
            "chief_counsel_advice"
        ],
        "rate_limit_per_minute": 30
    }
    
    # Federal Register Configuration
    federal_register_config = {
        "base_url": "https://www.federalregister.gov/api/v1",
        "supported_document_types": ["rule", "proposed_rule", "notice"],
        "supported_agencies": ["treasury", "irs", "internal-revenue-service"]
    }
    
    # Agent Tool Mappings
    agent_tool_mappings = {
        "CaseLawAgent": [
            "brave_search",
            "llm_enhancer", 
            "irs_api",
            "legal_database"
        ],
        "RegulationAgent": [
            "brave_search",
            "llm_enhancer",
            "federal_register",
            "ecfr_api",
            "tax_law_database"
        ],
        "PrecedentAgent": [
            "brave_search",
            "llm_enhancer",
            "neo4j_precedent_search",
            "sec_filings",
            "ma_database"
        ],
        "ExpertAgent": [
            "brave_search",
            "llm_enhancer",
            "professional_database",
            "academic_database",
            "industry_analysis"
        ]
    }

