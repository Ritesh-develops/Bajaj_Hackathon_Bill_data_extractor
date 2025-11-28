"""Dependency injection and initialization"""

import logging
from app.config import LOG_LEVEL

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def get_logger(name: str):
    """Get a configured logger"""
    return logging.getLogger(name)
