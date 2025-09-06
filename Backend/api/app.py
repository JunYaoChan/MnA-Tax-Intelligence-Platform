from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import time
from typing import Dict, Any

from api.routes import query, health, metrics
from api.middleware.error_handler import error_handler_middleware
from database.supabase_client import SupabaseVectorStore
from database.neo4j_client import Neo4jClient
from orchestration.orchestrator import LangGraphOrchestrator
from config.settings import Settings
from config.logging_config import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Global instances
settings = Settings()
orchestrator = None
vector_store = None
neo4j_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle - startup and shutdown
    """
    # Startup
    logger.info("Starting Tax Research RAG System")
    
    global orchestrator, vector_store, neo4j_client
    
    try:
        # Initialize database connections
        logger.info("Initializing database connections...")
        vector_store = SupabaseVectorStore(settings)
        
        neo4j_client = Neo4jClient(settings)
        await neo4j_client.connect()
        
        # Initialize orchestrator
        logger.info("Initializing orchestrator...")
        orchestrator = LangGraphOrchestrator(settings)
        
        # Store in app state for access in routes
        app.state.orchestrator = orchestrator
        app.state.vector_store = vector_store
        app.state.neo4j_client = neo4j_client
        app.state.settings = settings
        
        logger.info("System initialization complete")
        
    except Exception as e:
        logger.error(f"Failed to initialize system: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Tax Research RAG System")
    
    try:
        if neo4j_client:
            await neo4j_client.close()
            logger.info("Neo4j connection closed")
    except Exception as e:
        logger.error(f"Error closing Neo4j connection: {e}")

# Create FastAPI app
app = FastAPI(
    title="Tax Research Multi-Agent RAG System",
    description="Advanced multi-agent system for tax research and analysis",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins if hasattr(settings, 'cors_origins') else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Processing-Time"]
)

# Add trusted host middleware for security
if hasattr(settings, 'allowed_hosts'):
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_hosts
    )

# Add gzip compression for responses
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add custom error handler middleware
app.middleware("http")(error_handler_middleware)

# Add request ID and timing middleware
@app.middleware("http")
async def add_request_metadata(request: Request, call_next):
    """Add request ID and measure processing time"""
    import uuid
    
    # Generate request ID if not present
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    
    # Start timing
    start_time = time.time()
    
    # Process request
    response = await call_next(request)
    
    # Add headers
    process_time = time.time() - start_time
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Processing-Time"] = str(process_time)
    
    # Log request
    logger.info(
        f"Request {request_id}: {request.method} {request.url.path} "
        f"- Status: {response.status_code} - Time: {process_time:.3f}s"
    )
    
    return response

# Include routers
app.include_router(
    query.router,
    tags=["Query"]
)

app.include_router(
    health.router,
    tags=["Health"]
)

app.include_router(
    metrics.router,
    tags=["Metrics"]
)

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Tax Research Multi-Agent RAG System",
        "version": "1.0.0",
        "docs": "/api/docs",
        "health": "/api/v1/health"
    }

# Custom 404 handler
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Custom 404 handler"""
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": f"The path {request.url.path} was not found",
            "request_id": request.headers.get("X-Request-ID", "unknown")
        }
    )

# Custom 422 handler for validation errors
@app.exception_handler(422)
async def validation_error_handler(request: Request, exc):
    """Custom validation error handler"""
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation Error",
            "message": "Invalid request data",
            "details": exc.errors() if hasattr(exc, 'errors') else str(exc),
            "request_id": request.headers.get("X-Request-ID", "unknown")
        }
    )