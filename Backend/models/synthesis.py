from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class Citation(BaseModel):
    """Model for citations in synthesized responses"""
    
    document_id: str = Field(..., description="Reference to source document")
    page_number: Optional[int] = Field(None, description="Page number if applicable")
    section: Optional[str] = Field(None, description="Section reference")
    quote: Optional[str] = Field(None, description="Quoted text")
    context: Optional[str] = Field(None, description="Context around the citation")

class SynthesisResult(BaseModel):
    """Model for LLM synthesis results"""
    
    answer: str = Field(..., description="Synthesized answer")
    
    confidence: float = Field(
        ..., 
        ge=0.0, 
        le=1.0, 
        description="Confidence in the synthesis"
    )
    
    sources: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Source documents used in synthesis"
    )
    
    citations: List[Citation] = Field(
        default_factory=list,
        description="Specific citations within the answer"
    )
    
    key_findings: Optional[List[str]] = Field(
        None,
        description="Key findings from the analysis"
    )
    
    recommendations: Optional[List[str]] = Field(
        None,
        description="Recommendations based on the analysis"
    )
    
    limitations: Optional[List[str]] = Field(
        None,
        description="Limitations or caveats in the analysis"
    )
    
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional synthesis metadata"
    )
    
    processing_time: float = Field(
        ..., 
        ge=0.0, 
        description="Time taken for synthesis"
    )
    
    synthesis_method: str = Field(
        default="llm_guided",
        description="Method used for synthesis"
    )
    
    quality_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Quality score of the synthesis"
    )

