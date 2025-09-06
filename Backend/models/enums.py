from enum import Enum

class QueryComplexity(Enum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    EXPERT = "expert"

class AgentType(Enum):
    QUERY_PLANNING = "query_planning"
    CASE_LAW = "case_law"
    REGULATION = "regulation"
    PRECEDENT = "precedent"
    EXPERT = "expert"