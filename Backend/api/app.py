# Backend/api/app.py
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import time
import uuid
import logging
import asyncio
from contextlib import asynccontextmanager

from config.settings import settings
from function_tools.registry import get_function_tool_registry, cleanup_function_tools
from api.routes import query, health, metrics

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(settings.log_file),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Global variables for application state
function_registry = None
background_tasks = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    global function_registry
    
    # Startup
    logger.info("Starting Tax Research Multi-Agent RAG System...")
    
    try:
        # Initialize function tools registry
        function_registry = await get_function_tool_registry(settings)
        logger.info("✓ Function tools initialized")
        
        # Perform health check
        health_status = await function_registry.health_check()
        logger.info(f"✓ Health check completed: {health_status}")
        
        # Start background health monitoring if enabled
        if not settings.test_mode:
            health_task = asyncio.create_task(periodic_health_check())
            background_tasks.append(health_task)
            logger.info("✓ Background health monitoring started")
        
        logger.info("🚀 Application startup completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize application: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Tax Research Multi-Agent RAG System...")
    
    try:
        # Cancel background tasks
        for task in background_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # Cleanup function tools
        await cleanup_function_tools()
        logger.info("✓ Function tools cleaned up")
        
        logger.info("✓ Application shutdown completed")
        
    except Exception as e:
        logger.error(f"❌ Error during shutdown: {e}")

# Create FastAPI app with lifespan management
app = FastAPI(
    title="Tax Research Multi-Agent RAG System",
    description="Advanced tax research system with multi-agent architecture and function tools",
    version="1.0.0",
    docs_url="/api/docs" if settings.debug_mode else None,
    redoc_url="/api/redoc" if settings.debug_mode else None,
    lifespan=lifespan
)

# Middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug_mode else ["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if not settings.debug_mode:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["yourdomain.com", "*.yourdomain.com"]
    )

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time and request ID headers"""
    start_time = time.time()
    request_id = str(uuid.uuid4())
    
    # Add request ID to request state
    request.state.request_id = request_id
    
    # Process request
    try:
        response = await call_next(request)
    except Exception as e:
        logger.error(f"Request {request_id} failed: {str(e)}")
        raise
    
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
    """Root endpoint with system status"""
    global function_registry
    
    status = {
        "message": "Tax Research Multi-Agent RAG System",
        "version": "1.0.0",
        "status": "healthy",
        "docs": "/api/docs" if settings.debug_mode else "disabled",
        "health": "/api/v1/health"
    }
    
    # Add function tools status if available
    if function_registry:
        try:
            health_status = await function_registry.health_check()
            status["function_tools"] = {
                "available": list(health_status.keys()),
                "healthy": [k for k, v in health_status.items() if v],
                "unhealthy": [k for k, v in health_status.items() if not v]
            }
        except Exception as e:
            logger.error(f"Failed to get function tools status: {e}")
            status["function_tools"] = {"error": "Status check failed"}
    
    return status

# Enhanced health check endpoint
@app.get("/api/v1/health/detailed")
async def detailed_health_check():
    """Detailed health check including function tools"""
    global function_registry
    
    health_data = {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "1.0.0",
        "components": {}
    }
    
    # Check function tools
    if function_registry:
        try:
            tools_health = await function_registry.health_check()
            health_data["components"]["function_tools"] = {
                "status": "healthy" if all(tools_health.values()) else "degraded",
                "details": tools_health
            }
        except Exception as e:
            health_data["components"]["function_tools"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_data["status"] = "degraded"
    else:
        health_data["components"]["function_tools"] = {
            "status": "not_initialized"
        }
        health_data["status"] = "degraded"
    
    # Check database connections (add your database health checks here)
    health_data["components"]["database"] = {
        "status": "healthy"  # Implement actual database health check
    }
    
    # Determine overall status
    component_statuses = [comp["status"] for comp in health_data["components"].values()]
    if "unhealthy" in component_statuses:
        health_data["status"] = "unhealthy"
    elif "degraded" in component_statuses or "not_initialized" in component_statuses:
        health_data["status"] = "degraded"
    
    status_code = 200 if health_data["status"] == "healthy" else 503
    return JSONResponse(content=health_data, status_code=status_code)

# Function to test Brave Search specifically
@app.post("/api/v1/test/brave-search")
async def test_brave_search(query: str = "test query"):
    """Test Brave Search functionality"""
    global function_registry
    
    if not function_registry:
        raise HTTPException(status_code=503, detail="Function tools not initialized")
    
    try:
        brave_search = function_registry.get_tool("brave_search")
        if not brave_search:
            raise HTTPException(status_code=404, detail="Brave Search tool not available")
        
        # Test with a simple query
        result = await brave_search(query, count=3)
        
        return {
            "status": "success",
            "query": query,
            "results_count": len(result.get("web", {}).get("results", [])),
            "metadata": result.get("metadata", {}),
            "has_error": "error" in result
        }
        
    except Exception as e:
        logger.error(f"Brave Search test failed: {e}")
        raise HTTPException(status_code=500, detail=f"Brave Search test failed: {str(e)}")

# Background task for periodic health checks
async def periodic_health_check():
    """Periodic health check for function tools"""
    global function_registry
    
    while True:
        try:
            await asyncio.sleep(settings.health_check_interval)
            
            if function_registry:
                health_status = await function_registry.health_check()
                unhealthy_tools = [k for k, v in health_status.items() if not v]
                
                if unhealthy_tools:
                    logger.warning(f"Unhealthy function tools detected: {unhealthy_tools}")
                else:
                    logger.debug("All function tools healthy")
            
        except asyncio.CancelledError:
            logger.info("Health check task cancelled")
            break
        except Exception as e:
            logger.error(f"Health check task error: {e}")

# Custom error handlers
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Custom 404 handler"""
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": f"The path {request.url.path} was not found",
            "request_id": getattr(request.state, "request_id", "unknown")
        }
    )

@app.exception_handler(422)
async def validation_error_handler(request: Request, exc):
    """Custom validation error handler"""
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation Error",
            "message": "Invalid request data",
            "details": exc.errors() if hasattr(exc, 'errors') else str(exc),
            "request_id": getattr(request.state, "request_id", "unknown")
        }
    )

@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc):
    """Custom 500 handler"""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error(f"Internal server error for request {request_id}: {str(exc)}")
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred",
            "request_id": request_id
        }
    )

# Utility function to get function registry
def get_app_function_registry():
    """Get the application's function registry"""
    global function_registry
    return function_registry