from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class TaxQuery(BaseModel):
    """Input query model for API"""
    text: str = Field(..., description="The tax query text")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")
    include_sources: bool = Field(default=True)
    max_results: Optional[int] = Field(default=10, ge=1, le=50)

class QueryResponse(BaseModel):
    """Response model for queries"""
    status: str
    query: str
    response_time: float
    confidence: str
    summary: str
    key_findings: List[str]
    recommendations: List[str]
    citations: List[str]
    metadata: Dict[str, Any]

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: str
    agents: List[str]
    database_connections: Dict[str, bool]

class MetricsResponse(BaseModel):
    """System metrics response"""
    avg_response_time: str
    success_rate: str
    queries_processed: int
    avg_confidence: str
    active_agents: int
    cache_hit_rate: str