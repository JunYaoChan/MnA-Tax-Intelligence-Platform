from enum import Enum

class DocumentType(Enum):
    """Document types in the system"""
    REGULATION = "regulation"
    CASE_LAW = "case_law"
    REVENUE_RULING = "revenue_ruling"
    PRIVATE_LETTER_RULING = "private_letter_ruling"
    PRECEDENT = "precedent"
    KNOWLEDGE_BASE = "knowledge_base"
    GUIDE = "guide"
    CHECKLIST = "checklist"
    ANNOTATION = "annotation"

class Priority(Enum):
    """Query priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class QueryStatus(Enum):
    """Query processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"

# System limits
MAX_QUERY_LENGTH = 5000
MAX_RESULTS_PER_AGENT = 50
MAX_PARALLEL_AGENTS = 10
MAX_REQUERY_ATTEMPTS = 2
MAX_SYNTHESIS_TIME = 10  # seconds

# Cache settings
CACHE_TTL = 3600  # 1 hour
MAX_CACHE_SIZE = 1000

# Rate limiting
RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_WINDOW = 60  # seconds