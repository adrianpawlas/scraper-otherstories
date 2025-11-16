"""Logging configuration and utilities."""

import sys
from pathlib import Path
from loguru import logger
from typing import Optional

from .config import Config


def setup_logging(config: Config) -> None:
    """Setup logging configuration."""

    logging_config = config.get_logging_config()
    log_level = config.get('LOG_LEVEL', 'INFO')
    log_file = logging_config.get('file_path', 'logs/scraper.log')
    max_file_size = logging_config.get('max_file_size', '10 MB')
    retention = logging_config.get('retention', '7 days')

    # Create logs directory
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove default handler
    logger.remove()

    # Add console handler
    logger.add(
        sys.stdout,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True
    )

    # Add file handler with rotation
    logger.add(
        log_file,
        level=log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation=max_file_size,
        retention=retention,
        encoding='utf-8'
    )

    logger.info("Logging initialized")


def get_logger(name: Optional[str] = None):
    """Get logger instance."""
    if name:
        return logger.bind(name=name)
    return logger
