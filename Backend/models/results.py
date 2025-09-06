from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class RetrievalResult:
    """Result from retrieval operations"""
    documents: List[Dict[str, Any]]
    confidence: float
    source: str
    metadata: Dict[str, Any]
    retrieval_time: float