from fastapi import APIRouter, Depends
from models.api_models import HealthResponse
from database.supabase_client import SupabaseVectorStore
from database.neo4j_client import Neo4jClient
from config.settings import Settings
from datetime import datetime
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/health", response_model=HealthResponse)
async def health_check(settings: Settings = Depends(lambda: Settings())):
    """System health check endpoint"""
    
    # Check database connections
    db_status = await check_database_connections(settings)
    
    # Get active agents
    active_agents = [
        "QueryPlanningAgent",
        "CaseLawAgent",
        "RegulationAgent",
        "PrecedentAgent",
        "ExpertAgent"
    ]
    
    return HealthResponse(
        status="healthy" if all(db_status.values()) else "degraded",
        timestamp=datetime.now().isoformat(),
        agents=active_agents,
        database_connections=db_status
    )

async def check_database_connections(settings: Settings) -> dict:
    """Check all database connections"""
    status = {}
    
    # Check Supabase
    try:
        vector_store = SupabaseVectorStore(settings)
        # Perform a simple query
        await vector_store.search("test", top_k=1)
        status["supabase"] = True
    except Exception as e:
        logger.error(f"Supabase connection failed: {e}")
        status["supabase"] = False
    
    # Check Neo4j
    try:
        neo4j = Neo4jClient(settings)
        await neo4j.connect()
        await neo4j.verify_connectivity()
        await neo4j.close()
        status["neo4j"] = True
    except Exception as e:
        logger.error(f"Neo4j connection failed: {e}")
        status["neo4j"] = False
    
    return status

@router.get("/readiness")
async def readiness_check():
    """Kubernetes readiness probe"""
    # Check if system is ready to accept traffic
    return {"status": "ready"}

@router.get("/liveness")
async def liveness_check():
    """Kubernetes liveness probe"""
    # Check if system is alive
    return {"status": "alive"}