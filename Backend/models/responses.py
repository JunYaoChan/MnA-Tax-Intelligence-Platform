from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class DocumentSource(BaseModel):
    """Model for document source information"""
    
    id: str = Field(..., description="Unique document identifier")
    title: str = Field(..., description="Document title")
    url: Optional[str] = Field(None, description="Document URL if available")
    source: str = Field(..., description="Source system or database")
    document_type: str = Field(..., description="Type of document")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="Relevance score")
    authority_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Authority score")
    excerpt: Optional[str] = Field(None, description="Relevant excerpt from document")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

class AgentResult(BaseModel):
    """Model for individual agent results"""
    
    agent_name: str = Field(..., description="Name of the agent")
    documents_found: int = Field(..., ge=0, description="Number of documents found")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Agent confidence score")
    retrieval_time: float = Field(..., ge=0.0, description="Time taken for retrieval in seconds")
    function_tools_used: List[str] = Field(default_factory=list, description="Function tools used")
    external_sources_accessed: int = Field(default=0, description="Number of external sources accessed")

class QueryResponse(BaseModel):
    """Response model for query processing"""
    
    answer: str = Field(..., description="Generated answer to the query")
    
    confidence: float = Field(
        ..., 
        ge=0.0, 
        le=1.0, 
        description="Overall confidence in the answer"
    )
    
    sources: List[DocumentSource] = Field(
        default_factory=list,
        description="List of sources used to generate the answer"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the response"
    )
    
    processing_time: float = Field(
        ..., 
        ge=0.0, 
        description="Total processing time in seconds"
    )
    
    agent_results: Optional[List[AgentResult]] = Field(
        None,
        description="Detailed results from each agent"
    )
    
    pipeline_steps: Optional[Dict[str, Any]] = Field(
        None,
        description="Details about each pipeline step"
    )
    
    query_analysis: Optional[Dict[str, Any]] = Field(
        None,
        description="Analysis of the original query"
    )
    
    suggestions: Optional[List[str]] = Field(
        None,
        description="Related queries or suggestions"
    )
    
    warnings: Optional[List[str]] = Field(
        None,
        description="Any warnings about the response"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "answer": "A Section 338(h)(10) election allows the target corporation and its shareholders to treat the transaction as an asset sale for tax purposes...",
                "confidence": 0.92,
                "sources": [
                    {
                        "id": "irs_rev_rul_2008_25",
                        "title": "Revenue Ruling 2008-25",
                        "url": "https://www.irs.gov/irb/2008-25_IRB",
                        "source": "irs_api",
                        "document_type": "revenue_ruling",
                        "relevance_score": 0.95,
                        "authority_score": 0.98,
                        "excerpt": "Section 338(h)(10) election requirements...",
                        "metadata": {
                            "ruling_number": "Rev. Rul. 2008-25",
                            "issue_date": "2008-06-23"
                        }
                    }
                ],
                "metadata": {
                    "total_documents_processed": 25,
                    "pipeline_version": "RAG_v2.0",
                    "function_tools_used": ["brave_search", "irs_api", "llm_enhancer"]
                },
                "processing_time": 4.25,
                "agent_results": [
                    {
                        "agent_name": "RegulationAgent",
                        "documents_found": 8,
                        "confidence": 0.89,
                        "retrieval_time": 1.23,
                        "function_tools_used": ["brave_search", "ecfr_api"],
                        "external_sources_accessed": 3
                    }
                ],
                "query_analysis": {
                    "complexity": "moderate",
                    "entities": ["338", "h)(10"],
                    "intent": "regulatory_guidance"
                }
            }
        }