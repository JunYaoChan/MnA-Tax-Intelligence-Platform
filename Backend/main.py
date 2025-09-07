from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from config.settings import Settings
from orchestration.orchestrator import RAGOrchestrator
from database.supabase_client import SupabaseVectorStore
from database.neo4j_client import Neo4jClient
from models.requests import QueryRequest
from models.responses import QueryResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s [%(filename)s:%(lineno)d]: %(message)s',
    handlers=[
        logging.FileHandler('logs/tax_rag.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Global variables
settings = Settings()
orchestrator: RAGOrchestrator | None = None
vector_store: SupabaseVectorStore | None = None
neo4j_client: Neo4jClient | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the application"""
    global orchestrator, vector_store, neo4j_client
    
    logger.info("Initializing RAG Pipeline API...")
    try:
        # Load and validate settings
        settings.validate()
        logger.info("Settings loaded and validated successfully")
        
        # Initialize database connections
        vector_store = SupabaseVectorStore(settings)
        
        neo4j_client = Neo4jClient(settings)
        await neo4j_client.connect()
        
        # Initialize RAG orchestrator
        orchestrator = RAGOrchestrator(settings, vector_store, neo4j_client)
        await orchestrator.initialize()
        
        logger.info("RAG Pipeline API initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise

    yield

    # Cleanup on shutdown
    logger.info("Application shutdown complete")


# Initialize FastAPI app
app = FastAPI(
    title="Tax RAG Pipeline API",
    description="Advanced RAG pipeline for tax research and analysis",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    """
    Process a query through the RAG pipeline
    
    Implements the 5-step RAG process:
    1. User Query Submission
    2. Data Retrieval from Vector Database  
    3. External Data Sourcing with Function Tools
    4. LLM Response Generation
    5. Agent-Driven Refinement
    """
    try:
        if not orchestrator:
            raise HTTPException(status_code=500, detail="Orchestrator not initialized")
        
        logger.info(f"Processing query: {request.query[:100]}...")
        
        # Process through RAG pipeline
        result = await orchestrator.process_query(request.query, request.context)
        
        # Convert to response model
        response = QueryResponse(
            answer=result.answer,
            confidence=result.confidence,
            sources=result.sources,
            metadata=result.metadata,
            processing_time=result.processing_time
        )
        
        logger.info(f"Query processed successfully in {result.processing_time:.2f}s")
        return response
        
    except Exception as e:
        logger.error(f"Query processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "pipeline": "RAG",
        "components": {
            "orchestrator": orchestrator is not None,
            "vector_store": vector_store is not None,
            "neo4j": neo4j_client is not None
        }
    }

@app.get("/config")
async def get_config():
    """Get current configuration (excluding sensitive data)"""
    if not settings:
        raise HTTPException(status_code=500, detail="Settings not initialized")
    
    return {
        "rag_pipeline": {
            "top_k_results": settings.top_k_results,
            "min_docs_threshold": settings.min_docs_threshold,
            "confidence_threshold": settings.confidence_threshold,
            "agent_timeout": settings.agent_timeout
        },
        "function_tools": {
            "llm_enhancement_enabled": settings.enable_llm_enhancement,
            "external_search_enabled": settings.enable_external_search,
            "specialized_tools_enabled": settings.enable_specialized_tools
        },
        "search": {
            "brave_search_configured": bool(settings.brave_search_api_key),
            "embedding_model": settings.embedding_model
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
