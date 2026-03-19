"""
Structured logging utility for prediction-market-debater.
Provides a consistent logging format across all modules.
"""

import logging
import sys

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_INITIALIZED = False


def _init_root_logger() -> None:
    """Configure the root logger once."""
    global _INITIALIZED
    if _INITIALIZED:
        return

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Console handler (stdout) with INFO level
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
    root.addHandler(console)

    # Quiet down noisy third-party loggers
    for name in ("urllib3", "httpx", "httpcore", "werkzeug", "engineio", "socketio"):
        logging.getLogger(name).setLevel(logging.WARNING)

    _INITIALIZED = True


def get_logger(name: str) -> logging.Logger:
    """
    Get a named logger with consistent formatting.

    Usage:
        from app.utils.logger import get_logger
        logger = get_logger(__name__)
        logger.info("Something happened")
    """
    _init_root_logger()
    return logging.getLogger(name)
