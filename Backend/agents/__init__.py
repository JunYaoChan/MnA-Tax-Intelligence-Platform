
"""Initialize the agents package and expose agent classes."""
from .base import BaseAgent
from .query_planning import QueryPlanningAgent
from .case_law import CaseLawAgent
from .regulation import RegulationAgent
from .precedent import PrecedentAgent
from .expert import ExpertAgent
from .web_search import WebSearchAgent  # NEW
from .irs_api import IRSAPIAgent  # NEW

__all__ = [
    "BaseAgent",
    "QueryPlanningAgent",
    "CaseLawAgent",
    "RegulationAgent",
    "PrecedentAgent",
    "ExpertAgent",
    "WebSearchAgent",  # NEW
    "IRSAPIAgent",     # NEW
]
