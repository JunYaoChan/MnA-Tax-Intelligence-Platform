import uvicorn
from api.app import app
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Starting Tax Research Multi-Agent System")
    uvicorn.run(
        "api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )