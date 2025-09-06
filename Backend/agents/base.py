from abc import ABC, abstractmethod
import logging
import time
from typing import Dict, Any
from models.results import RetrievalResult
from models.state import AgentState
from config.settings import Settings

class BaseAgent(ABC):
    def __init__(self, name: str, settings: Settings):
        self.name = name
        self.settings = settings
        self.logger = logging.getLogger(f"{__name__}.{name}")
        
    @abstractmethod
    async def process(self, state: AgentState) -> RetrievalResult:
        pass
    
    async def validate_confidence(self, result: RetrievalResult) -> bool:
        return result.confidence >= self.settings.confidence_threshold
    
    def log_performance(self, start_time: float, result: RetrievalResult):
        duration = time.time() - start_time
        self.logger.info(
            f"Agent {self.name} completed in {duration:.2f}s "
            f"with confidence {result.confidence:.2%}"
        )