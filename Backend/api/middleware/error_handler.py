from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import traceback
from typing import Callable

logger = logging.getLogger(__name__)

class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Global error handler middleware"""
    
    async def dispatch(self, request: Request, call_next: Callable):
        try:
            response = await call_next(request)
            return response
            
        except HTTPException as e:
            # Let FastAPI handle HTTP exceptions
            raise e
            
        except Exception as e:
            # Log the full traceback
            logger.error(f"Unhandled exception: {e}")
            logger.error(traceback.format_exc())
            
            # Return a generic error response
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "message": str(e) if logger.level == logging.DEBUG else "An unexpected error occurred",
                    "request_id": request.headers.get("X-Request-ID", "unknown")
                }
            )

async def error_handler_middleware(request: Request, call_next: Callable):
    """Function-based error handler middleware"""
    try:
        response = await call_next(request)
        return response
        
    except HTTPException as e:
        raise e
        
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        logger.error(traceback.format_exc())
        
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "message": "An unexpected error occurred",
                "request_id": request.headers.get("X-Request-ID", "unknown")
            }
        )
