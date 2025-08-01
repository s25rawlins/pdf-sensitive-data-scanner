"""
Logging configuration for the PDF sensitive data scanner.
"""

import logging
import sys
from typing import Dict, Any


def setup_logging(log_level: str = "INFO") -> None:
    """
    Configure logging for the application.
    
    Args:
        log_level: The logging level (DEBUG, INFO, WARNING, ERROR)
    """
    # Define log format - simplified for production
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        datefmt=date_format,
        stream=sys.stdout,
        force=True
    )
    
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)

    logging.getLogger("httpx").setLevel(logging.WARNING)

    logging.getLogger("httpcore").setLevel(logging.WARNING)

    app_logger = logging.getLogger("app")
    app_logger.setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.
    
    Args:
        name: The name of the logger
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class SummaryLogFilter(logging.Filter):
    """
    Filter to reduce verbosity of certain log messages.
    """
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter log records to reduce verbosity.
        
        Args:
            record: The log record to filter
            
        Returns:
            True if the record should be logged, False otherwise
        """

        if record.levelno >= logging.WARNING:
            return True
        
        if "health" in record.getMessage().lower():
            return False
        
        if "OPTIONS" in record.getMessage():
            return False
        
        return True
