"""Error handling utilities for DevGuides."""

import asyncio
from typing import Callable, Any, Optional
from functools import wraps
import time

from .logging import get_logger

logger = get_logger(__name__)

def retry_with_backoff(max_attempts: int = 3, base_delay: float = 1.0, max_delay: float = 60.0):
    """Retry decorator with exponential backoff."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        logger.warning(
                            "operation_retrying", 
                            attempt=attempt + 1, 
                            max_attempts=max_attempts,
                            delay=delay,
                            error=str(e),
                            function=func.__name__
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            "operation_failed", 
                            attempts=attempt + 1, 
                            error=str(e),
                            function=func.__name__
                        )
            
            if last_exception:
                raise last_exception
            else:
                raise RuntimeError("Function failed without raising an exception")
        return wrapper
    return decorator

def handle_mcp_errors(default_return=None):
    """Decorator to handle MCP-specific errors gracefully."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except ConnectionError as e:
                logger.error("mcp_connection_error", error=str(e), function=func.__name__)
                return default_return
            except TimeoutError as e:
                logger.error("mcp_timeout_error", error=str(e), function=func.__name__)
                return default_return
            except Exception as e:
                logger.error("mcp_unexpected_error", error=str(e), function=func.__name__)
                return default_return
        return wrapper
    return decorator

def handle_llm_errors(default_return=""):
    """Decorator to handle LLM-specific errors gracefully."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error("llm_error", error=str(e), function=func.__name__)
                return default_return
        return wrapper
    return decorator

class CircuitBreaker:
    """Circuit breaker pattern for external service calls."""
    
    def __init__(self, failure_threshold: int = 5, timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func: Callable, *args, **kwargs):
        """Call function with circuit breaker protection."""
        if self.state == "OPEN":
            if time.time() - self.last_failure_time >= self.timeout:
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise e
    
    def on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        self.state = "CLOSED"
    
    def on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"

class RateLimiter:
    """Simple rate limiter for API calls."""
    
    def __init__(self, max_calls: int, time_window: float):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []
    
    async def acquire(self):
        """Acquire permission to make a call."""
        now = time.time()
        
        # Remove old calls outside the time window
        self.calls = [call_time for call_time in self.calls 
                     if now - call_time < self.time_window]
        
        if len(self.calls) >= self.max_calls:
            sleep_time = self.time_window - (now - self.calls[0])
            if sleep_time > 0:
                logger.info("rate_limit_sleeping", sleep_time=sleep_time)
                await asyncio.sleep(sleep_time)
                return await self.acquire()  # Recursive call after sleep
        
        self.calls.append(now)

def setup_error_handling():
    """Set up global error handling configuration."""
    # Configure asyncio exception handling
    def handle_exception(loop, context):
        logger.error("asyncio_exception", context=context)
    
    try:
        loop = asyncio.get_event_loop()
        loop.set_exception_handler(handle_exception)
    except RuntimeError:
        # No event loop running
        pass