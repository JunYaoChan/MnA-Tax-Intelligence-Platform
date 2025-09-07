# Backend/models/requests.py
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
from models.enums import QueryComplexity

class QueryRequest(BaseModel):
    """Request model for query processing"""
    
    query: str = Field(
        ..., 
        min_length=1, 
        max_length=2000,
        description="The user's query or question"
    )
    
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional context information for the query"
    )
    
    complexity_hint: Optional[QueryComplexity] = Field(
        default=None,
        description="Optional hint about query complexity"
    )
    
    preferred_agents: Optional[List[str]] = Field(
        default=None,
        description="Optional list of preferred agents to use"
    )
    
    max_results: Optional[int] = Field(
        default=None,
        ge=1,
        le=50,
        description="Maximum number of results to return"
    )
    
    confidence_threshold: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for results"
    )
    
    enable_external_search: Optional[bool] = Field(
        default=True,
        description="Whether to enable external search via function tools"
    )
    
    enable_llm_enhancement: Optional[bool] = Field(
        default=True,
        description="Whether to enable LLM-based document enhancement"
    )
    
    @validator('query')
    def validate_query(cls, v):
        """Validate query content"""
        if not v or not v.strip():
            raise ValueError('Query cannot be empty')
        
        # Remove excessive whitespace
        v = ' '.join(v.split())
        
        return v
    
    @validator('preferred_agents')
    def validate_preferred_agents(cls, v):
        """Validate preferred agents list"""
        if v is not None:
            valid_agents = {
                'CaseLawAgent', 'RegulationAgent', 
                'PrecedentAgent', 'ExpertAgent'
            }
            
            invalid_agents = set(v) - valid_agents
            if invalid_agents:
                raise ValueError(f'Invalid agents: {invalid_agents}')
        
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "query": "What are the requirements for a Section 338(h)(10) election?",
                "context": {
                    "deal_size": {"min": 100, "max": 1000},
                    "urgency": "high"
                },
                "complexity_hint": "moderate",
                "max_results": 15,
                "confidence_threshold": 0.7,
                "enable_external_search": True,
                "enable_llm_enhancement": True
            }
        }
