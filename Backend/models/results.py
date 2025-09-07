from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class RetrievalResult(BaseModel):
    """Enhanced result from agent retrieval operations"""
    
    documents: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Retrieved documents"
    )
    
    confidence: float = Field(
        ..., 
        ge=0.0, 
        le=1.0, 
        description="Confidence in the retrieval results"
    )
    
    source: str = Field(
        ..., 
        description="Source agent or system that produced this result"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the retrieval"
    )
    
    retrieval_time: float = Field(
        ..., 
        ge=0.0, 
        description="Time taken for retrieval in seconds"
    )
    
    # New fields for RAG pipeline
    vector_results_count: int = Field(
        default=0,
        description="Number of results from vector database"
    )
    
    external_results_count: int = Field(
        default=0,
        description="Number of results from external sources"
    )
    
    function_tools_used: List[str] = Field(
        default_factory=list,
        description="Function tools used in retrieval"
    )
    
    llm_enhanced: bool = Field(
        default=False,
        description="Whether documents were enhanced by LLM"
    )
    
    refinement_applied: bool = Field(
        default=False,
        description="Whether agent-driven refinement was applied"
    )
    
    quality_metrics: Optional[Dict[str, float]] = Field(
        None,
        description="Quality metrics for the retrieved documents"
    )
    
    pipeline_step: Optional[str] = Field(
        None,
        description="Which pipeline step produced this result"
    )
    
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="When this result was created"
    )
    
    def add_quality_metrics(self, metrics: Dict[str, float]):
        """Add quality metrics to the result"""
        if self.quality_metrics is None:
            self.quality_metrics = {}
        self.quality_metrics.update(metrics)
    
    def get_top_documents(self, n: int = 5) -> List[Dict[str, Any]]:
        """Get top N documents by relevance score"""
        sorted_docs = sorted(
            self.documents,
            key=lambda x: x.get('relevance_score', 0),
            reverse=True
        )
        return sorted_docs[:n]
    
    def get_documents_by_source(self, source_filter: str) -> List[Dict[str, Any]]:
        """Get documents from a specific source"""
        return [doc for doc in self.documents 
                if doc.get('source') == source_filter]
    
    def get_high_confidence_documents(self, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """Get documents above confidence threshold"""
        return [doc for doc in self.documents 
                if doc.get('relevance_score', 0) >= threshold]
    
    def merge_with(self, other: 'RetrievalResult') -> 'RetrievalResult':
        """Merge this result with another result"""
        merged_docs = self.documents + other.documents
        
        # Remove duplicates based on document ID
        seen_ids = set()
        unique_docs = []
        for doc in merged_docs:
            doc_id = doc.get('id', '')
            if doc_id and doc_id not in seen_ids:
                unique_docs.append(doc)
                seen_ids.add(doc_id)
            elif not doc_id:  # If no ID, keep all
                unique_docs.append(doc)
        
        return RetrievalResult(
            documents=unique_docs,
            confidence=(self.confidence + other.confidence) / 2,
            source=f"{self.source}+{other.source}",
            metadata={**self.metadata, **other.metadata},
            retrieval_time=self.retrieval_time + other.retrieval_time,
            vector_results_count=self.vector_results_count + other.vector_results_count,
            external_results_count=self.external_results_count + other.external_results_count,
            function_tools_used=list(set(self.function_tools_used + other.function_tools_used)),
            llm_enhanced=self.llm_enhanced or other.llm_enhanced,
            refinement_applied=self.refinement_applied or other.refinement_applied
        )
    
    class Config:
        arbitrary_types_allowed = True
        schema_extra = {
            "example": {
                "documents": [
                    {
                        "id": "doc_001",
                        "title": "Section 338 Election Requirements",
                        "content": "A Section 338 election allows...",
                        "source": "irs_api",
                        "relevance_score": 0.92,
                        "url": "https://www.irs.gov/..."
                    }
                ],
                "confidence": 0.87,
                "source": "RegulationAgent",
                "metadata": {
                    "query_refined": True,
                    "external_sources_used": 2
                },
                "retrieval_time": 2.34,
                "vector_results_count": 5,
                "external_results_count": 3,
                "function_tools_used": ["brave_search", "ecfr_api"],
                "llm_enhanced": True,
                "refinement_applied": True,
                "pipeline_step": "step_2_vector_retrieval"
            }
        }

