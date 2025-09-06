from fastapi import APIRouter
from models.api_models import MetricsResponse
from utils.metrics import MetricsCollector
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize metrics collector
metrics_collector = MetricsCollector()

@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics():
    """Get system metrics"""
    
    metrics = await metrics_collector.get_current_metrics()
    
    return MetricsResponse(
        avg_response_time=f"{metrics['avg_response_time']:.2f}s",
        success_rate=f"{metrics['success_rate']:.1%}",
        queries_processed=metrics['total_queries'],
        avg_confidence=f"{metrics['avg_confidence']:.1%}",
        active_agents=metrics['active_agents'],
        cache_hit_rate=f"{metrics['cache_hit_rate']:.1%}"
    )

@router.get("/metrics/detailed")
async def get_detailed_metrics():
    """Get detailed system metrics"""
    
    return await metrics_collector.get_detailed_metrics()

@router.post("/metrics/reset")
async def reset_metrics():
    """Reset metrics (admin only)"""
    
    await metrics_collector.reset()
    return {"status": "metrics reset"}

