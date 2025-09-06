from dataclasses import dataclass, field
from typing import Dict, List, Any
import time
from .enums import QueryComplexity

@dataclass
class AgentState:
    """Shared state for agent communication"""
    query: str
    complexity: QueryComplexity
    intent: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    retrieved_documents: List[Dict] = field(default_factory=list)
    agent_outputs: Dict[str, Any] = field(default_factory=dict)
    confidence_scores: Dict[str, float] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    start_time: float = field(default_factory=time.time)