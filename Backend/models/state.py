from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from models.enums import QueryComplexity
from datetime import datetime

class AgentState(BaseModel):
    """Enhanced state object passed between agents"""
    
    query: str = Field(..., description="Original user query")
    
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context information"
    )
    
    intent: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parsed intent from query analysis"
    )
    
    complexity: QueryComplexity = Field(
        default=QueryComplexity.MODERATE,
        description="Determined query complexity"
    )
    
    retrieved_documents: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Documents retrieved so far"
    )
    
    agent_results: Dict[str, Any] = Field(
        default_factory=dict,
        description="Results from individual agents"
    )
    
    pipeline_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata from pipeline execution"
    )
    
    session_id: Optional[str] = Field(
        None,
        description="Session identifier"
    )
    
    user_preferences: Optional[Dict[str, Any]] = Field(
        None,
        description="User preferences for search and results"
    )
    
    start_time: datetime = Field(
        default_factory=datetime.now,
        description="When processing started"
    )
    
    def add_documents(self, documents: List[Dict[str, Any]], agent_name: str):
        """Add documents from an agent"""
        for doc in documents:
            doc['retrieved_by'] = agent_name
            doc['retrieval_timestamp'] = datetime.now().isoformat()
        
        self.retrieved_documents.extend(documents)
    
    def get_documents_by_agent(self, agent_name: str) -> List[Dict[str, Any]]:
        """Get documents retrieved by a specific agent"""
        return [doc for doc in self.retrieved_documents 
                if doc.get('retrieved_by') == agent_name]
    
    def get_documents_by_source(self, source: str) -> List[Dict[str, Any]]:
        """Get documents from a specific source"""
        return [doc for doc in self.retrieved_documents 
                if doc.get('source') == source]
    
    def get_total_processing_time(self) -> float:
        """Get total processing time so far"""
        return (datetime.now() - self.start_time).total_seconds()
    
    class Config:
        arbitrary_types_allowed = True
        json_schema_extra = {
            "example": {
                "query": "Section 338(h)(10) election requirements",
                "context": {
                    "deal_size": {"min": 100, "max": 1000},
                    "urgency": "high"
                },
                "intent": {
                    "entities": ["338", "h)(10)"],
                    "keywords": ["election", "requirements"],
                    "intent_type": "regulatory_guidance"
                },
                "complexity": "moderate",
                "retrieved_documents": [],
                "agent_results": {},
                "pipeline_metadata": {
                    "pipeline_version": "RAG_v2.0",
                    "steps_completed": []
                }
            }
        }
