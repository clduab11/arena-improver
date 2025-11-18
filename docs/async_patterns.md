# Async Patterns and Best Practices

This document outlines the async/await patterns used in the Arena Improver codebase and provides guidelines for maintaining async best practices.

## Overview

Arena Improver uses asynchronous patterns throughout to:
- Efficiently handle I/O-bound operations (HTTP requests, database queries)
- Avoid blocking the event loop in Gradio UI handlers
- Reuse HTTP connections via connection pooling
- Meet API rate limits (e.g., Scryfall's 100ms requirement)

## Shared HTTP Client

### ✅ DO: Use the Shared HTTP Client

The `HTTPClientManager` provides a singleton async client with connection pooling:

```python
from src.services.http_client import get_http_client

async def fetch_data():
    client = await get_http_client()
    response = await client.get("https://api.example.com/data")
    return response.json()
```

**Benefits:**
- Reuses TCP connections (20% faster for rate-limited APIs)
- Shared connection pool (100 max connections, 20 keepalive)
- Automatic cleanup via FastAPI lifespan

### ❌ DON'T: Create New AsyncClient Instances

**Bad:**
```python
# Anti-pattern: Creates new connection each time
async def fetch_data():
    async with httpx.AsyncClient() as client:  # ❌
        response = await client.get("https://api.example.com/data")
        return response.json()
```

**Problems:**
- Wastes resources creating/destroying connections
- Bypasses rate limiting coordination
- Defeats connection pooling benefits

## Service Patterns

### ✅ DO: Use Async Context Managers

Services should support async context managers for proper lifecycle management:

```python
class MyService:
    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self._client = client
    
    async def __aenter__(self):
        """Initialize resources."""
        if self._client is None:
            self._client = await get_http_client()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup (shared client is managed by lifespan)."""
        return False
    
    async def _ensure_client(self) -> httpx.AsyncClient:
        """Lazy initialization for non-context-manager usage."""
        if self._client is None:
            self._client = await get_http_client()
        return self._client
    
    async def fetch_something(self, id: str):
        client = await self._ensure_client()
        response = await client.get(f"/api/{id}")
        return response.json()
```

**Usage:**
```python
# With context manager
async with MyService() as service:
    data = await service.fetch_something("123")

# Without context manager (auto-initializes)
service = MyService()
data = await service.fetch_something("123")
```

### ✅ DO: Propagate Async Context Managers

When services depend on other services, propagate the lifecycle:

```python
class DependentService:
    def __init__(self, base_service: Optional[BaseService] = None):
        self.base = base_service or BaseService()
    
    async def __aenter__(self):
        # Initialize dependency
        if hasattr(self.base, '__aenter__'):
            await self.base.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Cleanup dependency
        if hasattr(self.base, '__aexit__'):
            await self.base.__aexit__(exc_type, exc_val, exc_tb)
        return False
```

## Gradio UI Handlers

### ✅ DO: Use Async Handlers

Gradio 5.x supports async functions. Always use async for I/O operations:

```python
async def handle_upload(file_path: str) -> Dict[str, Any]:
    """Async handler for file upload."""
    client = await _get_gradio_client()  # Separate client for UI
    
    with open(file_path, "rb") as f:
        files = {"file": f}
        response = await client.post("/api/upload", files=files)
    
    return response.json()

# Register with Gradio
button.click(
    fn=handle_upload,  # Gradio handles async automatically
    inputs=[file_input],
    outputs=[status_output]
)
```

### ❌ DON'T: Use Blocking Calls in Handlers

**Bad:**
```python
def handle_upload(file_path: str) -> Dict[str, Any]:  # ❌ Sync function
    # Blocks the event loop
    response = httpx.post("/api/upload", files={"file": open(file_path, "rb")})
    return response.json()
```

**Problems:**
- Blocks Gradio event loop
- Freezes UI during I/O
- Poor user experience

## Error Handling

### ✅ DO: Handle Async Errors Properly

```python
async def fetch_with_retry(url: str, max_retries: int = 3):
    client = await get_http_client()
    
    for attempt in range(max_retries):
        try:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            return response.json()
        
        except httpx.TimeoutException:
            logger.warning(f"Timeout on attempt {attempt + 1}")
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code}")
            raise
        
        except Exception as e:
            logger.exception("Unexpected error")
            raise
```

### ✅ DO: Use asyncio.sleep for Delays

```python
# Correct
await asyncio.sleep(1.0)  # ✅ Non-blocking

# Incorrect
time.sleep(1.0)  # ❌ Blocks event loop
```

## Rate Limiting

### ✅ DO: Implement Rate Limiting with Async

```python
class RateLimitedService:
    def __init__(self):
        self._last_request = datetime.now()
        self._rate_limit_delay = 0.1  # 100ms
    
    async def _rate_limit(self):
        """Enforce rate limit between requests."""
        now = datetime.now()
        elapsed = (now - self._last_request).total_seconds()
        
        if elapsed < self._rate_limit_delay:
            await asyncio.sleep(self._rate_limit_delay - elapsed)
        
        self._last_request = datetime.now()
    
    async def make_request(self, url: str):
        await self._rate_limit()  # Enforce delay
        client = await get_http_client()
        return await client.get(url)
```

## Testing Async Code

### ✅ DO: Use pytest-asyncio

```python
import pytest
import pytest_asyncio

@pytest_asyncio.fixture
async def service():
    """Async fixture with proper lifecycle."""
    async with MyService() as svc:
        yield svc
    # Cleanup happens automatically

@pytest.mark.asyncio
async def test_fetch_data(service):
    """Test async service method."""
    data = await service.fetch_something("123")
    assert data is not None
```

### ✅ DO: Mock Async Functions

```python
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_with_mock():
    mock_client = AsyncMock()
    mock_client.get.return_value.json.return_value = {"status": "ok"}
    
    service = MyService(client=mock_client)
    result = await service.fetch_something("123")
    
    assert result["status"] == "ok"
    mock_client.get.assert_called_once()
```

## FastAPI Integration

### ✅ DO: Use Lifespan for Client Lifecycle

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    await start_http_client()
    logger.info("HTTP client initialized")
    
    yield
    
    # Shutdown
    await shutdown_http_client()
    logger.info("HTTP client closed")

app = FastAPI(lifespan=lifespan)
```

## Common Pitfalls

### ❌ DON'T: Mix Sync and Async

**Bad:**
```python
def sync_function():
    # Cannot use await here
    data = async_function()  # ❌ Returns coroutine, doesn't execute
    return data
```

**Fix:**
```python
async def async_function():
    data = await other_async_function()  # ✅
    return data
```

### ❌ DON'T: Forget to Await

**Bad:**
```python
async def fetch_data():
    client = get_http_client()  # ❌ Missing await
    response = client.get("/api/data")  # ❌ Missing await
    return response
```

**Fix:**
```python
async def fetch_data():
    client = await get_http_client()  # ✅
    response = await client.get("/api/data")  # ✅
    return response
```

### ❌ DON'T: Use asyncio.run() in Async Functions

**Bad:**
```python
async def outer():
    result = asyncio.run(inner())  # ❌ Creates nested event loop
    return result
```

**Fix:**
```python
async def outer():
    result = await inner()  # ✅
    return result
```

## Performance Tips

1. **Connection Pooling**: Shared client reuses connections for 20%+ speedup
2. **Concurrent Requests**: Use `asyncio.gather()` for parallel requests:
   ```python
   results = await asyncio.gather(
       fetch_user(1),
       fetch_user(2),
       fetch_user(3)
   )
   ```
3. **Timeouts**: Always set timeouts to prevent hanging:
   ```python
   await client.get(url, timeout=10.0)
   ```
4. **Caching**: Cache responses to avoid redundant API calls
5. **Rate Limiting**: Coordinate rate limits via shared service state

## Debugging

Enable detailed httpx logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("httpx").setLevel(logging.DEBUG)
```

Check for blocking calls with:
```bash
python -m pytest --asyncio-mode=strict
```

## Migration Checklist

When converting sync code to async:

- [ ] Add `async` keyword to function definition
- [ ] Add `await` to all async function calls
- [ ] Replace `httpx.Client()` with `await get_http_client()`
- [ ] Replace `time.sleep()` with `await asyncio.sleep()`
- [ ] Update Gradio handlers (they support async automatically)
- [ ] Add `@pytest.mark.asyncio` to tests
- [ ] Verify no blocking calls remain in async functions
- [ ] Test with real HTTP requests to verify connection pooling

## References

- [httpx AsyncClient Docs](https://www.python-httpx.org/async/)
- [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/)
- [Gradio Async Support](https://www.gradio.app/guides/working-with-async-functions)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)

---

**Last Updated**: 2024-11-18
**Maintained by**: Arena Improver Team
