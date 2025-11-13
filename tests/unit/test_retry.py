"""Tests for retry logic and error handling utilities."""

import asyncio
import pytest
from src.utils.retry import (
    RetryConfig,
    with_retry,
    RetryableError,
    RateLimitError,
    NetworkError,
    CircuitBreaker,
    with_circuit_breaker,
    RateLimiter,
    with_rate_limit
)


class TestRetryConfig:
    """Tests for RetryConfig."""

    def test_default_config(self):
        """Test default retry configuration."""
        config = RetryConfig()

        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True

    def test_custom_config(self):
        """Test custom retry configuration."""
        config = RetryConfig(
            max_attempts=5,
            base_delay=0.5,
            max_delay=30.0,
            exponential_base=3.0,
            jitter=False
        )

        assert config.max_attempts == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 30.0
        assert config.exponential_base == 3.0
        assert config.jitter is False

    def test_calculate_delay(self):
        """Test delay calculation."""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=False)

        # Test exponential backoff
        assert config.calculate_delay(0) == 1.0  # 1.0 * 2^0
        assert config.calculate_delay(1) == 2.0  # 1.0 * 2^1
        assert config.calculate_delay(2) == 4.0  # 1.0 * 2^2

    def test_calculate_delay_with_max(self):
        """Test that delay doesn't exceed max_delay."""
        config = RetryConfig(base_delay=1.0, max_delay=5.0, exponential_base=2.0, jitter=False)

        assert config.calculate_delay(10) == 5.0  # Capped at max_delay


class TestWithRetry:
    """Tests for with_retry decorator."""

    @pytest.mark.asyncio
    async def test_successful_call(self):
        """Test that successful calls don't retry."""
        call_count = 0

        @with_retry()
        async def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await successful_func()

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_retryable_error(self):
        """Test that retryable errors trigger retry."""
        call_count = 0

        @with_retry(config=RetryConfig(max_attempts=3, base_delay=0.01))
        async def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise NetworkError("Network error")
            return "success"

        result = await failing_func()

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_max_attempts_exceeded(self):
        """Test that max attempts limit is enforced."""
        call_count = 0

        @with_retry(config=RetryConfig(max_attempts=3, base_delay=0.01))
        async def always_failing_func():
            nonlocal call_count
            call_count += 1
            raise NetworkError("Network error")

        with pytest.raises(NetworkError):
            await always_failing_func()

        assert call_count == 3

    @pytest.mark.asyncio
    async def test_non_retryable_error(self):
        """Test that non-retryable errors don't trigger retry."""
        call_count = 0

        @with_retry(config=RetryConfig(max_attempts=3))
        async def func_with_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Not retryable")

        with pytest.raises(ValueError):
            await func_with_value_error()

        assert call_count == 1  # No retries


class TestCircuitBreaker:
    """Tests for CircuitBreaker."""

    @pytest.mark.asyncio
    async def test_initial_state_closed(self):
        """Test that circuit breaker starts in CLOSED state."""
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0)

        assert breaker.state == "CLOSED"

    @pytest.mark.asyncio
    async def test_open_circuit_after_threshold(self):
        """Test that circuit opens after exceeding failure threshold."""
        breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=1.0,
            expected_exception=NetworkError
        )

        async def failing_func():
            raise NetworkError("Network error")

        # Trigger failures
        for _ in range(3):
            with pytest.raises(NetworkError):
                await breaker.call(failing_func)

        assert breaker.state == "OPEN"

    @pytest.mark.asyncio
    async def test_circuit_recovery(self):
        """Test that circuit can recover after timeout."""
        breaker = CircuitBreaker(
            failure_threshold=2,
            recovery_timeout=0.1,  # Short timeout for testing
            expected_exception=NetworkError
        )

        async def failing_then_succeeding():
            # Will fail until circuit recovers
            if breaker.state == "CLOSED":
                raise NetworkError("Network error")
            return "success"

        # Trigger failures to open circuit
        for _ in range(2):
            with pytest.raises(NetworkError):
                await breaker.call(failing_then_succeeding)

        assert breaker.state == "OPEN"

        # Wait for recovery timeout
        await asyncio.sleep(0.2)

        # Next call should enter HALF_OPEN state
        # We'll modify the function to succeed now
        async def succeeding_func():
            return "success"

        result = await breaker.call(succeeding_func)

        assert result == "success"
        assert breaker.state == "CLOSED"


class TestRateLimiter:
    """Tests for RateLimiter."""

    @pytest.mark.asyncio
    async def test_rate_limit_acquisition(self):
        """Test that tokens are acquired at the correct rate."""
        limiter = RateLimiter(rate=10.0, burst=1)  # 10 req/s, no burst

        # First request should be immediate
        start = asyncio.get_event_loop().time()
        await limiter.acquire()
        elapsed1 = asyncio.get_event_loop().time() - start

        # Second request should wait ~0.1s
        start = asyncio.get_event_loop().time()
        await limiter.acquire()
        elapsed2 = asyncio.get_event_loop().time() - start

        assert elapsed1 < 0.01  # First request immediate
        assert 0.08 < elapsed2 < 0.15  # Second request waits ~0.1s

    @pytest.mark.asyncio
    async def test_burst_capacity(self):
        """Test that burst capacity allows multiple immediate requests."""
        limiter = RateLimiter(rate=5.0, burst=3)  # 5 req/s, burst of 3

        # First 3 requests should be immediate
        start = asyncio.get_event_loop().time()
        await limiter.acquire()
        await limiter.acquire()
        await limiter.acquire()
        elapsed = asyncio.get_event_loop().time() - start

        assert elapsed < 0.05  # All 3 requests nearly immediate

    @pytest.mark.asyncio
    async def test_rate_limit_decorator(self):
        """Test with_rate_limit decorator."""
        limiter = RateLimiter(rate=20.0, burst=1)  # 20 req/s
        call_times = []

        @with_rate_limit(limiter)
        async def rate_limited_func():
            call_times.append(asyncio.get_event_loop().time())
            return "success"

        # Make multiple calls
        for _ in range(3):
            await rate_limited_func()

        # Check that calls were rate limited
        # Time between calls should be ~0.05s (1/20)
        if len(call_times) >= 2:
            time_diff = call_times[1] - call_times[0]
            assert 0.04 < time_diff < 0.07


class TestWithCircuitBreaker:
    """Tests for with_circuit_breaker decorator."""

    @pytest.mark.asyncio
    async def test_decorator_basic_functionality(self):
        """Test that decorator works correctly."""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        call_count = 0

        @with_circuit_breaker(breaker)
        async def test_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await test_func()

        assert result == "success"
        assert call_count == 1
        assert breaker.state == "CLOSED"


class TestRetryableErrors:
    """Tests for retryable error types."""

    def test_retryable_error_inheritance(self):
        """Test that specific errors inherit from RetryableError."""
        assert issubclass(RateLimitError, RetryableError)
        assert issubclass(NetworkError, RetryableError)

    def test_error_messages(self):
        """Test that errors can be created with messages."""
        error = NetworkError("Connection timeout")
        assert str(error) == "Connection timeout"

        error = RateLimitError("Too many requests")
        assert str(error) == "Too many requests"
