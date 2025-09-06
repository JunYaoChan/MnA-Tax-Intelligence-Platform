from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import query, health, metrics
from api.middleware.error_handler import error_handler_middleware
from config.settings import Settings

settings = Settings()

app = FastAPI(
    title="Tax Research Multi-Agent System",
    version="1.0.0"
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(error_handler_middleware)

# Routes
app.include_router(query.router, prefix="/api/v1", tags=["Query"])
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(metrics.router, prefix="/api/v1", tags=["Metrics"])