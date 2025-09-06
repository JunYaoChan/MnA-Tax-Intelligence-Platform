from typing import Dict
from fastapi import APIRouter, HTTPException, BackgroundTasks
from models.api_models import TaxQuery
from orchestration.orchestrator import LangGraphOrchestrator
from config.settings import Settings
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

settings = Settings()
orchestrator = LangGraphOrchestrator(settings)

@router.post("/query")
async def process_tax_query(query: TaxQuery, background_tasks: BackgroundTasks):
    try:
        result = await orchestrator.process_query(query.text)
        background_tasks.add_task(log_metrics, query.text, result)
        return result
    except Exception as e:
        logger.error(f"Query processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def log_metrics(query: str, result: Dict):
    # Log metrics implementation
    pass