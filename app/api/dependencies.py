import logging
from app.config import LOG_LEVEL


logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def get_logger(name: str):
    return logging.getLogger(name)
