import logging
import logging.config
from pathlib import Path
import os

def setup_logging(log_level: str = "INFO", log_file: str = "logs/tax_rag.log"):
    """Setup logging configuration"""
    
    # Ensure logs directory exists
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Ensure the log file exists
    log_file_path = Path(log_file)
    log_file_path.parent.mkdir(exist_ok=True)
    log_file_path.touch(exist_ok=True)
    
    LOGGING_CONFIG = {
        'version': 1,
        'disable_existing_loggers': False,  # This is crucial!
        'formatters': {
            'standard': {
                'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
            },
            'detailed': {
                'format': '%(asctime)s [%(levelname)s] %(name)s [%(filename)s:%(lineno)d]: %(message)s'
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': log_level,
                'formatter': 'standard',
                'stream': 'ext://sys.stdout'
            },
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': 'DEBUG',
                'formatter': 'detailed',
                'filename': log_file,
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5,
                'encoding': 'utf8'
            },
            'error_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': 'ERROR',
                'formatter': 'detailed',
                'filename': 'logs/errors.log',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5,
                'encoding': 'utf8'
            }
        },
        'loggers': {
            '': {  # Root logger
                'level': log_level,
                'handlers': ['console', 'file', 'error_file'],
                'propagate': False
            },
            'src': {
                'level': 'DEBUG',
                'handlers': ['console', 'file', 'error_file'],
                'propagate': False
            },
            'uvicorn': {
                'level': 'INFO',
                'handlers': ['console', 'file'],
                'propagate': False
            },
            'fastapi': {
                'level': 'INFO',
                'handlers': ['console', 'file'],
                'propagate': False
            }
        }
    }
    
    # Clear any existing handlers to avoid conflicts
    logging.getLogger().handlers.clear()
    
    # Apply the configuration
    logging.config.dictConfig(LOGGING_CONFIG)
    
    # Test that logging works
    logger = logging.getLogger(__name__)
    logger.info("Logging configuration initialized successfully")
    
    return logging.getLogger()
