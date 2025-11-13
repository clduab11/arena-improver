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
        """
        Configure retry behavior for operations.
        
        Parameters:
            max_attempts (int): Maximum number of attempts before giving up.
            base_delay (float): Initial backoff delay in seconds.
            max_delay (float): Upper bound for computed delay in seconds.
            exponential_base (float): Multiplier base used for exponential backoff per attempt.
            jitter (bool): If True, applies random jitter (between 0.5x and 1.0x) to the computed delay.
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def calculate_delay(self, attempt: int) -> float:
        """
        Compute the retry delay for a given attempt using exponential backoff with optional jitter.
        
        Parameters:
            attempt (int): Retry attempt index (0 for the first attempt).
        
        Returns:
            float: Delay in seconds to wait before the next retry.
        """
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
    """
    Decorator that retries an async function on configured transient errors using exponential backoff and optional jitter.
    
    Wraps an async callable to attempt execution up to config.max_attempts times. When an exception instance matches one of retryable_exceptions, the wrapper waits a delay computed by config.calculate_delay(attempt) and retries until attempts are exhausted; on the final failed attempt the exception is re-raised. Any exception not in retryable_exceptions is re-raised immediately.
    
    Parameters:
        config (RetryConfig | None): RetryConfig instance controlling max attempts, base/max delays, backoff base, and jitter. If None, a default RetryConfig is used.
        retryable_exceptions (tuple[type[Exception], ...] | None): Tuple of exception types that should trigger a retry. If None, a default set of transient/retryable exceptions is used.
    
    Returns:
        Callable: A decorator that, when applied to an async function, returns a wrapped async function implementing the described retry behavior.
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
        """
        Wrap an asynchronous callable with retry behavior using the enclosing `config` and `retryable_exceptions`.
        
        Wraps `func` so that it is invoked up to `config.max_attempts` times when a `retryable_exceptions` type is raised, waiting the delay returned by `config.calculate_delay(attempt)` between retries. A non-retryable exception is re-raised immediately. If all attempts are exhausted, the last retryable exception is re-raised.
        
        Parameters:
            func (Callable): The asynchronous callable to wrap.
        
        Returns:
            Callable: An async wrapper that applies the configured retry policy to `func`.
        """
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
        """
        Create a CircuitBreaker configured with failure and recovery parameters.
        
        Parameters:
            failure_threshold (int): Number of consecutive failures required to open the circuit.
            recovery_timeout (float): Seconds to wait after opening before allowing a reset attempt.
            expected_exception (Type[Exception]): Exception type that is counted as a failure toward the threshold.
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    @property
    def state(self) -> str:
        """
        Return the current state of the circuit breaker.
        
        Returns:
            state (str): One of "CLOSED", "OPEN", or "HALF_OPEN" representing the circuit breaker's current state.
        """
        return self._state

    def _should_attempt_reset(self) -> bool:
        """
        Determine whether the circuit breaker may attempt a recovery reset based on elapsed time.
        
        Returns:
            bool: `True` if `recovery_timeout` seconds have elapsed since the last recorded failure, `False` otherwise.
        """
        if self._last_failure_time is None:
            return False

        return (time.time() - self._last_failure_time) >= self.recovery_timeout

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute the given async callable under circuit breaker protection.
        
        When the circuit is OPEN and the recovery timeout has not elapsed, raises ServiceUnavailableError.
        If the circuit is OPEN and the recovery timeout has elapsed, transitions to HALF_OPEN and attempts the call.
        On a successful call while HALF_OPEN, transitions the circuit to CLOSED and resets the failure count.
        
        Parameters:
            func (Callable): The asynchronous callable to execute.
            *args: Positional arguments forwarded to `func`.
            **kwargs: Keyword arguments forwarded to `func`.
        
        Returns:
            Any: The result returned by `func`.
        
        Raises:
            ServiceUnavailableError: If the circuit is OPEN and recovery timeout has not elapsed.
            Exception: Re-raises exceptions of the configured `expected_exception` type after recording the failure.
        """

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

            # Success - reset if we were in HALF_OPEN
            if self._state == "HALF_OPEN":
                logger.info("Circuit breaker entering CLOSED state (service recovered)")
                self._state = "CLOSED"
                self._failure_count = 0

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
    """
    Wrap an async function so its invocations are governed by the provided circuit breaker.
    
    Parameters:
        circuit_breaker (CircuitBreaker): CircuitBreaker instance that will govern call execution and transition circuit states.
    
    Returns:
        Callable: A decorator that, when applied to an async function, returns a wrapper which executes that function under the circuit breaker's protection.
    """

    def decorator(func: Callable) -> Callable:
        """
        Wraps an async callable so its invocations are executed through the configured CircuitBreaker.
        
        The returned wrapper delegates each call to circuit_breaker.call, preserving positional and keyword arguments and returning the underlying result or re-raising exceptions from the circuit breaker.
        
        Parameters:
            func (Callable): The async function to wrap.
        
        Returns:
            Callable: An async wrapper function that forwards calls to the circuit breaker.
        """
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
        """
        Create a token-bucket rate limiter configured with a refill rate and burst capacity.
        
        Parameters:
        	rate (float): Token refill rate in tokens per second.
        	burst (int): Maximum and initial token bucket capacity (maximum burst size).
        """
        self.rate = rate
        self.burst = burst
        self._tokens = float(burst)
        self._last_update = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1):
        """
        Waits until the requested number of tokens are available and consumes them from the token bucket.
        
        Replenishes tokens based on elapsed time (at the configured rate, capped by the burst capacity) and sleeps as necessary until the requested tokens can be taken.
        
        Parameters:
            tokens (int): Number of tokens to acquire from the bucket. Defaults to 1.
        """
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
    """
    Apply a token-bucket rate limiter to an async function.
    
    Wraps an async callable so that each invocation first acquires the specified number of tokens from the provided RateLimiter, waiting as needed, and then executes the callable.
    
    Parameters:
        limiter (RateLimiter): Token-bucket limiter used to throttle calls.
        tokens (int): Number of tokens to consume per invocation (default 1).
    
    Returns:
        Callable: A decorator that wraps an async function to enforce the rate limit on each call.
    """

    def decorator(func: Callable) -> Callable:
        """
        Wraps an async callable to enforce token-based rate limiting by acquiring tokens from the configured limiter before each invocation.
        
        @param func: The asynchronous callable to wrap.
        @returns: A wrapped coroutine function that acquires `tokens` from `limiter` before calling `func` and returns `func`'s result.
        """
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            await limiter.acquire(tokens)
            return await func(*args, **kwargs)

        return wrapper

    return decorator