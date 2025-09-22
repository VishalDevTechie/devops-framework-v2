# scripts/utils/logger.py
import logging
import sys
from typing import Optional

def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    """Get a configured logger instance"""
    logger = logging.getLogger(name)
    
    # Avoid adding multiple handlers
    if logger.handlers:
        return logger
    
    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    # Set level
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric_level)
    handler.setLevel(numeric_level)
    
    # Add handler
    logger.addHandler(handler)
    
    return logger