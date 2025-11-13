"""Retry logic and error handling utilities for Arena Improver.

Provides decorators and utilities for handling:
- API rate limiting
- Network failures
- Transient errors
- Exponential backoff
"""

import asyncio
import logging
from functools import wraps
from typing import Callable, Optional, Type, Tuple, Any
import time

logger = logging.getLogger(__name__)


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        """Initialize retry configuration.

        Args:
            max_attempts: Maximum number of retry attempts
            base_delay: Initial delay between retries (seconds)
            max_delay: Maximum delay between retries (seconds)
            exponential_base: Base for exponential backoff
            jitter: Whether to add random jitter to delays
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number."""
        import random

        # Exponential backoff
        delay = min(
            self.base_delay * (self.exponential_base ** attempt),
            self.max_delay
        )

        # Add jitter to prevent thundering herd
        if self.jitter:
            delay = delay * (0.5 + random.random() * 0.5)

        return delay


class RetryableError(Exception):
    """Base class for errors that should trigger retry."""
    pass


class RateLimitError(RetryableError):
    """Raised when API rate limit is hit."""
    pass


class NetworkError(RetryableError):
    """Raised on network-related failures."""
    pass


class ServiceUnavailableError(RetryableError):
    """Raised when external service is temporarily unavailable."""
    pass


def with_retry(
    config: Optional[RetryConfig] = None,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None
):
    """Decorator to add retry logic to async functions.

    Args:
        config: Retry configuration (uses defaults if None)
        retryable_exceptions: Tuple of exception types that should trigger retry

    Usage:
        @with_retry(config=RetryConfig(max_attempts=5))
        async def fetch_data():
            # Your code here
            pass
    """
    if config is None:
        config = RetryConfig()

    if retryable_exceptions is None:
        retryable_exceptions = (
            RetryableError,
            RateLimitError,
            NetworkError,
            ServiceUnavailableError,
            asyncio.TimeoutError,
            ConnectionError
        )

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)

                except retryable_exceptions as e:
                    last_exception = e

                    if attempt < config.max_attempts - 1:
                        delay = config.calculate_delay(attempt)
                        logger.warning(
                            f"Attempt {attempt + 1}/{config.max_attempts} failed for "
                            f"{func.__name__}: {type(e).__name__}: {str(e)}. "
                            f"Retrying in {delay:.2f}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"All {config.max_attempts} attempts failed for "
                            f"{func.__name__}: {type(e).__name__}: {str(e)}"
                        )
                        raise

                except Exception as e:
                    # Non-retryable exception
                    logger.error(
                        f"Non-retryable error in {func.__name__}: "
                        f"{type(e).__name__}: {str(e)}"
                    )
                    raise

            # Should never reach here, but just in case
            if last_exception:
                raise last_exception

        return wrapper

    return decorator


class CircuitBreaker:
    """Circuit breaker pattern for preventing cascading failures.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failures exceeded threshold, requests fail fast
    - HALF_OPEN: Testing if service has recovered
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            expected_exception: Exception type that triggers circuit breaker
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    @property
    def state(self) -> str:
        """Get current circuit breaker state."""
        return self._state

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self._last_failure_time is None:
            return False

        return (time.time() - self._last_failure_time) >= self.recovery_timeout

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""

        # Check if circuit is open
        if self._state == "OPEN":
            if self._should_attempt_reset():
                logger.info("Circuit breaker entering HALF_OPEN state")
                self._state = "HALF_OPEN"
            else:
                raise ServiceUnavailableError(
                    f"Circuit breaker is OPEN. Service unavailable. "
                    f"Will retry after {self.recovery_timeout}s"
                )

        try:
            result = await func(*args, **kwargs)

            # Success - always reset failure tracking
            self._failure_count = 0
            self._last_failure_time = None
            
            # Transition from HALF_OPEN to CLOSED if we were testing
            if self._state == "HALF_OPEN":
                logger.info("Circuit breaker entering CLOSED state (service recovered)")
                self._state = "CLOSED"

            return result

        except self.expected_exception as e:
            self._failure_count += 1
            self._last_failure_time = time.time()

            logger.warning(
                f"Circuit breaker failure {self._failure_count}/{self.failure_threshold}: {e}"
            )

            # Open circuit if threshold exceeded
            if self._failure_count >= self.failure_threshold:
                if self._state != "OPEN":
                    logger.error(
                        f"Circuit breaker entering OPEN state after "
                        f"{self._failure_count} failures"
                    )
                    self._state = "OPEN"

            raise


def with_circuit_breaker(circuit_breaker: CircuitBreaker):
    """Decorator to add circuit breaker protection to async functions.

    Args:
        circuit_breaker: CircuitBreaker instance to use

    Usage:
        breaker = CircuitBreaker(failure_threshold=5)

        @with_circuit_breaker(breaker)
        async def fetch_data():
            # Your code here
            pass
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            return await circuit_breaker.call(func, *args, **kwargs)

        return wrapper

    return decorator


class RateLimiter:
    """Token bucket rate limiter for API calls."""

    def __init__(
        self,
        rate: float,  # requests per second
        burst: int = 1  # max burst size
    ):
        """Initialize rate limiter.

        Args:
            rate: Maximum requests per second
            burst: Maximum burst size (tokens in bucket)
        """
        self.rate = rate
        self.burst = burst
        self._tokens = float(burst)
        self._last_update = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1):
        """Acquire tokens from the bucket, waiting if necessary."""
        async with self._lock:
            while True:
                now = time.time()
                elapsed = now - self._last_update

                # Add tokens based on elapsed time
                self._tokens = min(
                    self.burst,
                    self._tokens + elapsed * self.rate
                )
                self._last_update = now

                # Check if we have enough tokens
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return

                # Calculate wait time
                needed = tokens - self._tokens
                wait_time = needed / self.rate

                logger.debug(f"Rate limit: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)


def with_rate_limit(limiter: RateLimiter, tokens: int = 1):
    """Decorator to add rate limiting to async functions.

    Args:
        limiter: RateLimiter instance to use
        tokens: Number of tokens to consume per call

    Usage:
        limiter = RateLimiter(rate=2.0, burst=5)  # 2 req/s, burst of 5

        @with_rate_limit(limiter)
        async def api_call():
            # Your code here
            pass
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            await limiter.acquire(tokens)
            return await func(*args, **kwargs)

        return wrapper

    return decorator
