"""Logging configuration for DevGuides."""

import logging
import sys
from pathlib import Path
from typing import Optional

import structlog
from rich.logging import RichHandler
from rich.console import Console

def setup_logging(level: str = "INFO", log_file: Optional[Path] = None):
    """Configure structured logging for DevGuides."""
    
    # Convert string level to logging constant
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Configure structlog processors
    if log_file:
        # For file logging, use structured JSON format
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ]
    else:
        # For console logging, convert to standard log message format
        def render_message(logger, name, event_dict):
            """Convert structlog event to simple message format."""
            level = event_dict.get("level", "INFO").upper()
            message = event_dict.get("event", "")
            return f"[{level}] {message}"
        
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            render_message  # Custom simple message renderer
        ]
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configure standard logging
    handlers = []
    
    # Console handler
    if not log_file:
        console = Console(stderr=True)
        console_handler = RichHandler(
            level=log_level,
            console=console,
            rich_tracebacks=True,
            show_path=False,
            show_time=True
        )
        handlers.append(console_handler)
    
    # File handler if specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(
            logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        )
        handlers.append(file_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        handlers=handlers,
        force=True
    )
    
    # Set specific logger levels for known modules
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)

def configure_for_cli(debug: bool = False):
    """Configure logging for CLI usage."""
    level = "DEBUG" if debug else "INFO"
    setup_logging(level=level)

def configure_for_testing():
    """Configure logging for testing."""
    # Suppress most logs during testing except errors
    logging.basicConfig(level=logging.ERROR)
    
    # Minimal structlog configuration for testing
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.processors.TimeStamper(fmt="H:%M:%S"),
            structlog.dev.ConsoleRenderer(colors=False)
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )