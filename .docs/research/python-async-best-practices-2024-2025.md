# Python Async Best Practices 2024-2025: Research Report

**Date:** 2025-12-03
**Research Focus:** Modern async patterns for high-performance Python services
**Target:** Connection pooling, lock-free concurrency, task management, error handling, testing, and profiling

---

## Executive Summary

This research report synthesizes current best practices for Python asyncio development based on authoritative sources including official Python documentation, PEPs, production service implementations, and expert recommendations. The findings emphasize structured concurrency patterns introduced in Python 3.11+, lock-free pool designs, defensive error handling, and modern testing approaches.

**Key Findings:**
- Python 3.11+ TaskGroup provides safer structured concurrency than gather()
- Lock-free connection pools leverage asyncio's cooperative multitasking for zero-contention access
- ExceptionGroup and except* syntax enable proper multi-exception handling
- AsyncMock (stdlib since 3.8) simplifies async testing
- Statistical profilers (scalene, py-spy) outperform cProfile for async code
- PEP 789 (2024) addresses task cancellation bugs in async generators

---

## 1. Connection Pooling Patterns

### Lock-Free Pool Design

Modern async connection pools can eliminate explicit locking by leveraging asyncio's cooperative multitasking atomicity. The `asyncio-connection-pool` library demonstrates this pattern:

**Core Principle:** "Theoretically, there is an implicit 'lock' that is held while an asyncio task is executing. Since asyncio tasks only yield voluntarily, operations between yields are atomic without explicit synchronization primitives."

**Implementation Pattern:**
```python
class ConnectionStrategy(Protocol):
    async def create_connection(self) -> Connection:
        """Create new connection when pool needs capacity."""
        ...

    def connection_is_closed(self, conn: Connection) -> bool:
        """Validate connection health; return True if unusable."""
        ...

    async def close_connection(self, conn: Connection) -> None:
        """Teardown logic for surplus connections."""
        ...

# Usage with burst capacity
pool = ConnectionPool(
    strategy=MyConnectionStrategy(),
    max_size=10,        # Soft limit
    burst_limit=20      # Hard ceiling during load spikes
)

async with pool.get_connection() as conn:
    # Available connections retrieved without yielding to event loop
    await conn.execute(...)
```

**Benefits:**
- No lock contention for available connections
- Zero-copy retrieval without event loop context switches
- Adaptive capacity handles transient peaks efficiently

**Source:** [asyncio-connection-pool GitHub](https://github.com/fellowapp/asyncio-connection-pool)

### Database-Specific Patterns

**asyncpg (PostgreSQL):**
```python
import asyncpg

# Create pool at application startup
pool = await asyncpg.create_pool(
    'postgresql://user@localhost/database',
    min_size=10,
    max_size=50,
    command_timeout=60
)

# Acquire with async context manager
async with pool.acquire() as conn:
    async with conn.transaction():
        result = await conn.fetch('SELECT * FROM users')

# Cleanup at shutdown
await pool.close()
```

**Key Practice:** "For server-type applications that handle frequent requests and need the database connection for a short period while handling a request, the use of a connection pool is recommended."

**Source:** [asyncpg Usage Documentation](https://magicstack.github.io/asyncpg/current/usage.html)

### Connection Pool Best Practices

1. **Validate connections before use** - Implement health checks to detect stale connections
2. **Use context managers** - `async with pool.acquire()` ensures proper resource cleanup
3. **Configure timeouts** - Set connection and command timeouts to prevent hangs
4. **Monitor pool metrics** - Track active/idle connections, acquisition wait times
5. **Release eagerly** - Return connections to pool immediately after operations complete

**Concurrency Safety Note:** "When using Python asyncio, there are no 'threads', there is only one event loop thread. So the concept of 'thread safety' does not apply. There is however the concept of 'concurrency-safe' in asyncio, that is, two or more awaitables operating upon the same state."

**Source:** [SQLAlchemy AsyncIO Discussion](https://github.com/sqlalchemy/sqlalchemy/discussions/5980)

---

## 2. Lock-Free Concurrency Patterns

### Semaphores for Concurrency Control

Semaphores limit concurrent operation count without global locks:

```python
import asyncio

async def fetch_data(url: str, sem: asyncio.Semaphore):
    async with sem:  # Acquire/release automatically
        # Only 3 requests run concurrently at any time
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            return response.json()

async def main():
    # Limit to 3 concurrent HTTP requests
    sem = asyncio.Semaphore(3)

    urls = [f"https://api.example.com/data/{i}" for i in range(100)]
    tasks = [fetch_data(url, sem) for url in urls]
    results = await asyncio.gather(*tasks)
```

**Why Semaphores Are Needed:** "While certain concurrency bugs that would occur in multithreaded or multiprocessing applications are eliminated by asyncio's single-threaded nature, they are not completely eliminated. Concurrent tasks in asyncio are executed asynchronously, which means that there may be alternating execution of multiple tasks in time."

**Source:** [Mastering Synchronization Primitives in Python Asyncio](https://towardsdatascience.com/mastering-synchronization-primitives-in-python-asyncio-a-comprehensive-guide-ae1ae720d0de/)

### BoundedSemaphore for Safety

Use `asyncio.BoundedSemaphore` to prevent accidental over-release:

```python
sem = asyncio.BoundedSemaphore(5)

# Raises ValueError if release() called more times than acquire()
async with sem:
    await process()
```

**Source:** [Python Documentation - Synchronization Primitives](https://docs.python.org/3/library/asyncio-sync.html)

### Queues for Producer-Consumer Patterns

```python
import asyncio

async def producer(queue: asyncio.Queue, count: int):
    for i in range(count):
        await queue.put(f"item-{i}")
        await asyncio.sleep(0.1)
    await queue.put(None)  # Sentinel for shutdown

async def consumer(queue: asyncio.Queue, name: str):
    while True:
        item = await queue.get()
        if item is None:
            queue.task_done()
            break

        # Process item
        print(f"{name} processing {item}")
        await asyncio.sleep(0.5)
        queue.task_done()

async def main():
    queue = asyncio.Queue(maxsize=10)  # Bounded queue for backpressure

    async with asyncio.TaskGroup() as tg:
        tg.create_task(producer(queue, 100))
        tg.create_task(consumer(queue, "worker-1"))
        tg.create_task(consumer(queue, "worker-2"))
        tg.create_task(consumer(queue, "worker-3"))

    await queue.join()  # Wait for all items to be processed
```

**Source:** [Asyncio Design Patterns](https://dev-kit.io/blog/python/asyncio-design-patterns)

---

## 3. Task Management Patterns

### TaskGroup (Python 3.11+) - Recommended Pattern

TaskGroup provides structured concurrency with automatic cleanup and safer exception handling:

```python
import asyncio
import time

async def task_with_delay(name: str, delay: float):
    print(f"{name} starting")
    await asyncio.sleep(delay)
    print(f"{name} completed")
    return f"Result from {name}"

async def main():
    async with asyncio.TaskGroup() as tg:
        # Tasks created within the group
        task1 = tg.create_task(task_with_delay("Task-1", 1.0))
        task2 = tg.create_task(task_with_delay("Task-2", 2.0))
        task3 = tg.create_task(task_with_delay("Task-3", 0.5))

        # No need to await - implicit when context exits

    # All tasks guaranteed to complete here
    print(f"Results: {task1.result()}, {task2.result()}, {task3.result()}")
```

**Key Advantages:**
- **Automatic cancellation:** If one task fails, all others are cancelled
- **Structured lifetime:** Tasks cannot outlive the scope
- **Better exception handling:** Supports ExceptionGroup for multiple failures
- **No manual gather:** Implicit await on context exit

**Comparison with gather():**
```python
# Old pattern with gather() - requires manual cancellation on error
tasks = [task1(), task2(), task3()]
try:
    results = await asyncio.gather(*tasks)
except Exception:
    # Must manually cancel remaining tasks
    for task in tasks:
        if not task.done():
            task.cancel()
    raise

# New pattern with TaskGroup - automatic cancellation
async with asyncio.TaskGroup() as tg:
    t1 = tg.create_task(task1())
    t2 = tg.create_task(task2())
    t3 = tg.create_task(task3())
# If any task fails, others are auto-cancelled
```

**Source:** [Python Coroutines and Tasks Documentation](https://docs.python.org/3/library/asyncio-task.html)

### Background Task Management

**Critical Rule:** Always maintain strong references to background tasks to prevent garbage collection:

```python
class ServiceManager:
    def __init__(self):
        self._background_tasks: set[asyncio.Task] = set()

    def create_background_task(self, coro):
        """Create background task with automatic cleanup."""
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

    async def shutdown(self):
        """Cancel all background tasks and wait for cleanup."""
        for task in list(self._background_tasks):
            task.cancel()

        # Wait for all cancellations to complete
        await asyncio.gather(*self._background_tasks, return_exceptions=True)
```

**Warning:** "The event loop only keeps weak references to tasks. This means you should always save a reference to your background tasks to prevent them from being garbage collected."

**Source:** [How to Garbage Collect Python Background Asyncio Tasks](https://stackoverflow.com/questions/76160467/how-to-garbage-collect-python-background-asyncio-tasks)

### Graceful Shutdown Pattern

Implement cancellable sleeps for responsive shutdown:

```python
class CancellableSleeps:
    """Track and cancel active sleep operations for fast shutdown."""

    def __init__(self):
        self._sleeps: set[asyncio.Task] = set()

    async def sleep(self, delay: float, result=None):
        """Sleep that can be cancelled during shutdown."""
        task = asyncio.ensure_future(asyncio.sleep(delay, result=result))
        self._sleeps.add(task)
        try:
            return await task
        except asyncio.CancelledError:
            return result
        finally:
            self._sleeps.remove(task)

    def cancel_all(self):
        """Immediately cancel all active sleeps."""
        for task in self._sleeps:
            task.cancel()

# Usage in service
class Service:
    def __init__(self):
        self._sleeps = CancellableSleeps()
        self._running = True

    async def run(self):
        while self._running:
            await self._sleeps.sleep(60)  # Poll every minute
            await self.do_work()

    async def shutdown(self):
        self._running = False
        self._sleeps.cancel_all()  # Immediate wake-up
```

**Use Case:** "Services become unresponsive during shutdown when blocked on sleep operations. This implementation makes your service unresponsive for up to a minute when handling the shutdown signals if it is waiting for sleep to be over."

**Source:** [Three Essential Async Patterns - Elastic Blog](https://www.elastic.co/blog/async-patterns-building-python-service)

### Task Pool for Controlled Concurrency

Prevent task explosion with bounded concurrency:

```python
class ConcurrentTasks:
    """Limit concurrent task execution to prevent resource exhaustion."""

    def __init__(self, max_concurrency: int = 5):
        self.max_concurrency = max_concurrency
        self.tasks: list[asyncio.Task] = []
        self._task_over = asyncio.Event()

    async def put(self, coroutine):
        """Add task to pool, blocking if at capacity."""
        # Wait if pool is full
        if len(self.tasks) >= self.max_concurrency:
            await self._task_over.wait()
            self._task_over.clear()

        task = asyncio.create_task(coroutine)
        self.tasks.append(task)
        task.add_done_callback(lambda _: self._task_over.set())
        return task

    async def join(self):
        """Wait for all tasks to complete."""
        await asyncio.gather(*self.tasks, return_exceptions=True)

# Usage
async def process_items(items):
    pool = ConcurrentTasks(max_concurrency=10)

    for item in items:
        await pool.put(process_single_item(item))

    await pool.join()
```

**Challenge:** "Fire-and-forget task creation can cause 'task explosion,' overwhelming system resources when producers outpace consumers."

**Source:** [Three Essential Async Patterns - Elastic Blog](https://www.elastic.co/blog/async-patterns-building-python-service)

---

## 4. Error Propagation and Exception Handling

### ExceptionGroup and except* (Python 3.11+)

Handle multiple concurrent exceptions with ExceptionGroup:

```python
async def task_that_may_fail(n: int):
    await asyncio.sleep(0.1)
    if n % 2 == 0:
        raise ValueError(f"Task {n} failed")
    return f"Success {n}"

async def main():
    try:
        async with asyncio.TaskGroup() as tg:
            for i in range(5):
                tg.create_task(task_that_may_fail(i))
    except* ValueError as eg:
        # Handle all ValueError exceptions from group
        print(f"Caught {len(eg.exceptions)} ValueError exceptions")
        for exc in eg.exceptions:
            print(f"  - {exc}")
    except* Exception as eg:
        # Handle any other exception types
        print(f"Other exceptions: {eg.exceptions}")
```

**Key Feature:** "It is possible for more than one task to raise an exception in a task group. This raises the question: which exception is propagated from the task group context manager? The answer is 'both'. In practice this means that a special exception, ExceptionGroup (or BaseExceptionGroup) is raised which contains both exception objects."

**Source:** [Python Coroutines and Tasks Documentation](https://docs.python.org/3/library/asyncio-task.html)

### gather() Exception Modes

```python
# Default: First exception propagates, other tasks continue
try:
    results = await asyncio.gather(task1(), task2(), task3())
except Exception as e:
    # First exception raised by any task
    print(f"Failed: {e}")

# return_exceptions=True: All results returned, including exceptions
results = await asyncio.gather(
    task1(), task2(), task3(),
    return_exceptions=True
)

for i, result in enumerate(results):
    if isinstance(result, Exception):
        print(f"Task {i} failed: {result}")
    else:
        print(f"Task {i} succeeded: {result}")
```

**Important:** "If `return_exceptions` is True, exceptions in the tasks are treated the same as successful results, and gathered in the result list; otherwise, the first raised exception will be immediately propagated to the returned future."

**Source:** [Asyncio Task Exception Handling - ProxiesAPI](https://proxiesapi.com/articles/asyncio-task-exception-handling)

### Defensive Error Handling Pattern

Implement layered exception handling:

```python
import logging
import traceback

logger = logging.getLogger(__name__)

async def safe_execute(coro, operation_name: str):
    """
    Execute coroutine with comprehensive error handling.

    Layers:
    1. Operation-level: Catch and log with full traceback
    2. Return error indicator rather than raising
    3. Enable caller to decide recovery strategy
    """
    try:
        return await coro
    except asyncio.CancelledError:
        logger.info(f"{operation_name} cancelled")
        raise  # Always propagate cancellation
    except Exception as e:
        # Log with full traceback for diagnostics
        logger.exception(f"{operation_name} failed: {e}")
        return None  # Or return error object

# Usage
async def fetch_data(url: str):
    result = await safe_execute(
        httpx.get(url),
        operation_name=f"fetch {url}"
    )

    if result is None:
        # Fallback strategy
        return get_cached_data(url)

    return result
```

**Best Practice:** "Bubbling exceptions lose their tracebacks, making the root cause hard to diagnose. Use `logging.exception()` within the except block to preserve the full traceback for diagnostics."

**Source:** [Exception Handling in Asyncio - Piccolo Blog](https://piccolo-orm.com/blog/exception-handling-in-asyncio/)

### Task Exception Retrieval

```python
# Create task without immediate await
task = asyncio.create_task(risky_operation())

# Do other work
await asyncio.sleep(1)

# Check for exceptions
try:
    exception = task.exception()
    if exception:
        logger.error(f"Task failed: {exception}")
except asyncio.CancelledError:
    logger.info("Task was cancelled")

# Retrieve result (raises if task failed)
result = await task
```

**Source:** [How to Handle Asyncio Task Exceptions - Super Fast Python](https://superfastpython.com/asyncio-task-exceptions/)

### CancelledError Handling

```python
async def cleanup_aware_task():
    try:
        while True:
            await asyncio.sleep(1)
            await process_data()
    except asyncio.CancelledError:
        # Clean up resources before exiting
        logger.info("Task cancelled, cleaning up...")
        await flush_buffers()
        await close_connections()
        raise  # Re-raise to complete cancellation
```

**Critical:** "If the coroutine in which a CancelledError is raised is communicating with another system, accessing a database, or changing resources, it may leave the system in an unstable state. Catching the CancelledError provides an opportunity to unwind transactions minimizing the risk of data corruption."

**Source:** [How to Manage Exceptions When Waiting On Multiple Asyncio Tasks](https://plainenglish.io/blog/how-to-manage-exceptions-when-waiting-on-multiple-asyncio)

---

## 5. Testing Async Code

### pytest-asyncio Setup

```python
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"  # Auto-detect async tests

# test_service.py
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_fetch_user():
    # Test async functions naturally
    user = await fetch_user_from_db(user_id=123)
    assert user.name == "Alice"

# Or use fixture for event loop control
@pytest.fixture
async def db_connection():
    conn = await create_connection()
    yield conn
    await conn.close()

@pytest.mark.asyncio
async def test_with_fixture(db_connection):
    result = await db_connection.execute("SELECT 1")
    assert result == [(1,)]
```

**Source:** [A Practical Guide To Async Testing With Pytest-Asyncio](https://pytest-with-eric.com/pytest-advanced/pytest-asyncio/)

### AsyncMock Pattern

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_api_client():
    # Create mock with return value
    mock_response = AsyncMock()
    mock_response.json = AsyncMock(return_value={"id": 1, "name": "Test"})

    # Patch async HTTP client
    with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response

        # Test code using mocked client
        client = APIClient()
        result = await client.fetch_user(123)

        # Verify call
        mock_get.assert_called_once_with("https://api.example.com/users/123")
        assert result["name"] == "Test"

# Test exception scenarios
@pytest.mark.asyncio
async def test_api_error_handling():
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.TimeoutError("Connection timeout"))

    with pytest.raises(APIError):
        await fetch_with_retry(mock_client, "https://example.com")
```

**Source:** [Async Test Patterns for Pytest](https://tonybaloney.github.io/posts/async-test-patterns-for-pytest-and-unittest.html)

### Mocking Async Context Managers

```python
class AsyncContextManagerMock:
    """Mock for async context manager pattern."""

    def __init__(self, return_value=None):
        self.return_value = return_value

    async def __aenter__(self):
        return self.return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False

# Usage
@pytest.mark.asyncio
async def test_connection_pool():
    mock_connection = AsyncMock()
    mock_pool = AsyncMock()

    # Mock acquire() returning async context manager
    mock_pool.acquire.return_value = AsyncContextManagerMock(mock_connection)

    # Test code
    async with mock_pool.acquire() as conn:
        await conn.execute("SELECT 1")

    mock_connection.execute.assert_called_once()
```

**Source:** [Mastering Async Context Manager Mocking in Python Tests](https://dzone.com/articles/mastering-async-context-manager-mocking-in-python)

### Testing Race Conditions

```python
import asyncio

@pytest.mark.asyncio
async def test_concurrent_access():
    """Test for race conditions with controlled execution."""
    counter = {"value": 0}
    event1 = asyncio.Event()
    event2 = asyncio.Event()

    async def increment_unsafe():
        # Read value
        temp = counter["value"]
        await event1.wait()  # Pause to force interleaving
        # Write value
        counter["value"] = temp + 1
        event2.set()

    async def concurrent_increment():
        task1 = asyncio.create_task(increment_unsafe())
        await asyncio.sleep(0.01)  # Ensure task1 starts first
        task2 = asyncio.create_task(increment_unsafe())

        # Allow first task to read value
        event1.set()
        await event2.wait()

        # Both tasks complete
        await asyncio.gather(task1, task2)

    await concurrent_increment()
    # Race condition detected: value is 1 instead of 2
    assert counter["value"] == 1, "Race condition exists (expected for this test)"
```

**Source:** [Boost Your Python Testing with pytest asyncio](https://articles.mergify.com/pytest-asyncio/)

### Best Practices for Async Testing

1. **Isolate tests** - Each test gets clean event loop state
2. **Mock external I/O** - Never make real API/database calls in tests
3. **Use fixtures for setup/teardown** - Properly initialize and clean resources
4. **Test error paths** - Verify exception handling, timeouts, cancellation
5. **Test concurrency** - Use Event objects to control task interleaving
6. **Assert mock calls** - Verify interactions with `assert_called_with()`
7. **Avoid real sleeps** - Mock time or use small delays for timing tests

**Source:** [A Practical Guide To Async Testing With Pytest-Asyncio](https://pytest-with-eric.com/pytest-advanced/pytest-asyncio/)

---

## 6. Performance Profiling

### Statistical Profilers (Recommended for Async)

**Scalene** - Top recommendation for async code:

```bash
# Install
pip install scalene

# Profile async application
scalene --cpu --memory --outfile profile.html your_app.py

# Profile specific function
python -m scalene --cpu-only --profile-interval 0.01 app.py
```

**Features:**
- CPU and memory profiling
- Native asyncio support
- Low overhead (10-20% vs 100%+ for cProfile)
- HTML output with line-by-line breakdown
- 10k+ GitHub stars, actively maintained

**Source:** [Profiling Asynchronous Python](https://medium.com/@maximsmirnov/profiling-asynchronous-python-576568f6f2c0)

**py-spy** - Sampling profiler without code changes:

```bash
# Install
pip install py-spy

# Profile running process
py-spy record -o profile.svg --pid 12345

# Profile script from start
py-spy record -o profile.svg -- python app.py

# Live top-like view
py-spy top --pid 12345
```

**Benefits:**
- Attach to running process
- No instrumentation required
- Minimal overhead
- Flame graph output

**Source:** [Profiling Python Code](https://copdips.com/2024/06/profiling-python-code.html)

**yappi** - Coroutine-aware profiler:

```python
import yappi

yappi.set_clock_type("wall")  # Use wall time for I/O-bound code
yappi.start()

# Run async application
asyncio.run(main())

yappi.stop()

# Get stats
stats = yappi.get_func_stats()
stats.sort("totaltime")
stats.print_all()

# Thread/coroutine stats
thread_stats = yappi.get_thread_stats()
thread_stats.print_all()
```

**Critical Feature:** "With v1.2, Yappi corrects issues with coroutine profiling. Under the hood, it differentiates the yield from real function exit and if wall time is selected as the clock_type it will accumulate the time and corrects the call count metric."

**Source:** [How to Profile/Benchmark Python ASYNCIO Code](https://stackoverflow.com/questions/54292461/how-to-profile-benchmark-python-asyncio-code)

### line_profiler for Detailed Analysis

```bash
# Install
pip install line_profiler

# Add @profile decorator to target functions
# No import needed - decorator injected by kernprof

# In your code:
@profile
async def slow_function():
    results = []
    async for item in fetch_items():
        processed = await process_item(item)
        results.append(processed)
    return results

# Run profiler
kernprof -l -v app.py
```

**Output Example:**
```
Line #      Hits         Time  Per Hit   % Time  Line Contents
==============================================================
   10                                           @profile
   11                                           async def slow_function():
   12         1        100.0    100.0      5.0      results = []
   13       100       1500.0     15.0     75.0      async for item in fetch_items():
   14       100        300.0      3.0     15.0          processed = await process_item(item)
   15       100        100.0      1.0      5.0          results.append(processed)
   16         1          0.0      0.0      0.0      return results
```

**Source:** [How to Profile Asyncio With line_profiler](https://superfastpython.com/asyncio-line_profiler/)

### Identifying Common Bottlenecks

**1. Blocking Calls in Async Context**

```python
# BAD: Blocks event loop
async def fetch_data():
    response = requests.get(url)  # Synchronous call
    return response.json()

# GOOD: Use async HTTP client
async def fetch_data():
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()
```

**2. Sequential I/O Instead of Concurrent**

```python
# BAD: Sequential execution (10 seconds total)
async def fetch_all_sequential(urls):
    results = []
    for url in urls:
        result = await fetch(url)  # Each takes 1 second
        results.append(result)
    return results

# GOOD: Concurrent execution (1 second total)
async def fetch_all_concurrent(urls):
    tasks = [fetch(url) for url in urls]
    return await asyncio.gather(*tasks)
```

**3. CPU-Intensive Operations**

```python
# BAD: CPU-bound work blocks event loop
async def process_data(large_dataset):
    # JSON parsing is CPU-intensive
    return json.loads(large_dataset)

# GOOD: Offload to thread pool
async def process_data(large_dataset):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,  # Use default ThreadPoolExecutor
        json.loads,
        large_dataset
    )
```

**4. Excessive Context Switching**

```python
# BAD: Too many tiny tasks
async def process_items(items):
    tasks = [process_single_byte(byte) for byte in items]
    await asyncio.gather(*tasks)  # 1 million tasks for 1MB file

# GOOD: Batch processing
async def process_items(items):
    batch_size = 1000
    batches = [items[i:i+batch_size] for i in range(0, len(items), batch_size)]
    tasks = [process_batch(batch) for batch in batches]
    await asyncio.gather(*tasks)
```

**Source:** [Rooting Out CPU Bottlenecks From Asyncio Based API Services](https://www.balajeerc.info/Rooting-out-CPU-Bottlenecks-from-asyncio-based-API-services/)

### Monitoring and Observability

```python
import time
import structlog

logger = structlog.get_logger()

class PerformanceMonitor:
    """Track asyncio performance metrics."""

    @staticmethod
    async def timed_operation(coro, operation_name: str):
        """Time async operation and log if slow."""
        start = time.perf_counter()
        try:
            result = await coro
            duration = time.perf_counter() - start

            if duration > 1.0:  # Log slow operations
                logger.warning(
                    "slow_operation",
                    operation=operation_name,
                    duration_ms=duration * 1000
                )
            else:
                logger.debug(
                    "operation_complete",
                    operation=operation_name,
                    duration_ms=duration * 1000
                )

            return result
        except Exception as e:
            duration = time.perf_counter() - start
            logger.error(
                "operation_failed",
                operation=operation_name,
                duration_ms=duration * 1000,
                error=str(e)
            )
            raise

# Usage
result = await PerformanceMonitor.timed_operation(
    fetch_data(url),
    operation_name="fetch_user_data"
)
```

**Tools for Production Monitoring:**
- **structlog** - Structured logging for async flows
- **opentelemetry** - Distributed tracing
- **Prometheus + Grafana** - Metrics visualization (self-hosted)

**Source:** [Mastering AsyncIO in Python: Performance Optimization](https://pydiary.com/posts/mastering_asyncio_in_python/9-performance-optimization-and-monitoring/)

---

## 7. Recent Developments and Future Trends

### PEP 789 (2024) - Preventing Task-Cancellation Bugs

**Problem:** Async generators can yield during cancellation, causing resource leaks.

**Solution:** New `sys.prevent_yields()` context manager:

```python
import sys
import asyncio

async def safe_cleanup():
    """Prevent yielding during critical cleanup."""
    async with asyncio.timeout(5):
        with sys.prevent_yields():
            # RuntimeError if code tries to yield/await here
            await cleanup_resources()  # Will raise RuntimeError
```

**Impact:** "In the standard library, sys.prevent_yields could be used by asyncio.TaskGroup, asyncio.timeout, and asyncio.timeout_at."

**Status:** Proposed for Python 3.14+

**Source:** [PEP 789 - Preventing Task-Cancellation Bugs](https://peps.python.org/pep-0789/)

### Python 3.12 Eager Tasks

Meta contributed optimization for immediate task results:

```python
# Set custom task factory for eager execution
loop = asyncio.get_event_loop()
loop.set_task_factory(asyncio.eager_task_factory)

# When result available immediately, skip event loop scheduling
async def get_cached_value():
    return cache.get("key")  # Synchronous cache lookup

# Task resolves without event loop roundtrip
task = asyncio.create_task(get_cached_value())
result = await task  # Faster than standard task scheduling
```

**Benefit:** "With eager tasks, coroutine and Task objects are still created when a result is available immediately, but we can sometimes avoid scheduling the task to the event loop and instead resolve it right away."

**Source:** [Meta Contributes New Features to Python 3.12](https://engineering.fb.com/2023/10/05/developer-tools/python-312-meta-new-features/)

### PEP 703 - Free-Threading (Python 3.14+)

**Major Change:** Optional removal of Global Interpreter Lock (GIL)

**Impact on Asyncio:**
- True parallel execution of CPU-bound async tasks
- New concurrency primitives needed (locks, semaphores, mutexes)
- Existing asyncio code continues to work
- Opt-in via build flag

**Timeline:** Experimental in 3.13, production-ready in 3.14+

**Source:** [The State of Python 2025](https://blog.jetbrains.com/pycharm/2025/08/the-state-of-python-2025/)

### ExceptionGroup Syntax (Python 3.11+)

```python
try:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(task1())
        tg.create_task(task2())
        tg.create_task(task3())
except* ValueError as eg:
    # Handle all ValueError instances
    for exc in eg.exceptions:
        log_value_error(exc)
except* KeyError as eg:
    # Handle all KeyError instances
    for exc in eg.exceptions:
        log_key_error(exc)
except* Exception as eg:
    # Handle any other exceptions
    for exc in eg.exceptions:
        log_generic_error(exc)
```

**Source:** [Python's asyncio: A Hands-On Walkthrough](https://realpython.com/async-io-python/)

---

## 8. Actionable Patterns for Scout MCP

Based on the current Scout MCP architecture and research findings, here are specific improvements:

### 1. Replace Global Lock with Semaphore

**Current Pattern:**
```python
# scout_mcp/services/pool.py
class ConnectionPool:
    def __init__(self):
        self._lock = asyncio.Lock()  # Global bottleneck

    async def get_connection(self, host: str):
        async with self._lock:  # All requests serialize here
            # Get or create connection
```

**Improved Pattern:**
```python
class ConnectionPool:
    def __init__(self, max_concurrent_connections: int = 50):
        # Semaphore allows concurrent connection access
        self._semaphore = asyncio.Semaphore(max_concurrent_connections)
        # Per-host locks only for creation
        self._host_locks: dict[str, asyncio.Lock] = {}

    async def get_connection(self, host: str):
        async with self._semaphore:  # Limit total concurrency
            # Get host-specific lock (only locks during creation)
            if host not in self._host_locks:
                self._host_locks[host] = asyncio.Lock()

            # Only lock if creating new connection
            if host in self._connections:
                return self._connections[host]

            async with self._host_locks[host]:
                # Double-check after acquiring lock
                if host in self._connections:
                    return self._connections[host]

                # Create new connection
                conn = await self._create_connection(host)
                self._connections[host] = conn
                return conn
```

### 2. Implement TaskGroup for Cleanup

**Current Pattern:**
```python
async def cleanup_idle_connections(self):
    for host, conn in list(self._connections.items()):
        if conn.is_idle():
            await conn.close()
            del self._connections[host]
```

**Improved Pattern:**
```python
async def cleanup_idle_connections(self):
    """Clean up idle connections concurrently with proper error handling."""
    to_cleanup = [
        (host, conn)
        for host, conn in self._connections.items()
        if conn.is_idle()
    ]

    async with asyncio.TaskGroup() as tg:
        for host, conn in to_cleanup:
            tg.create_task(self._cleanup_connection(host, conn))

async def _cleanup_connection(self, host: str, conn: PooledConnection):
    """Clean up single connection with error handling."""
    try:
        await conn.close()
        del self._connections[host]
        logger.debug("connection_cleaned_up", host=host)
    except Exception as e:
        logger.warning("cleanup_failed", host=host, error=str(e))
        # TaskGroup will continue cleaning other connections
```

### 3. Enhanced Error Handling

**Current Pattern:**
```python
async def execute_command(self, host: str, command: str) -> CommandResult:
    try:
        conn = await self.get_connection(host)
        result = await conn.run(command)
        return CommandResult(success=True, output=result.stdout)
    except Exception as e:
        return CommandResult(success=False, error=str(e))
```

**Improved Pattern:**
```python
async def execute_command(self, host: str, command: str) -> CommandResult:
    """Execute command with retry and detailed error tracking."""
    try:
        conn = await self.get_connection(host)
        result = await asyncio.wait_for(
            conn.run(command),
            timeout=self._command_timeout
        )
        return CommandResult(success=True, output=result.stdout)

    except asyncio.TimeoutError:
        logger.warning("command_timeout", host=host, command=command[:50])
        return CommandResult(
            success=False,
            error=f"Command timed out after {self._command_timeout}s"
        )

    except asyncssh.ConnectionLost:
        logger.warning("connection_lost", host=host)
        # Retry once with new connection
        async with self._host_locks.get(host, asyncio.Lock()):
            if host in self._connections:
                del self._connections[host]
        return await self.execute_command(host, command)

    except asyncio.CancelledError:
        logger.info("command_cancelled", host=host)
        raise  # Propagate cancellation

    except Exception as e:
        logger.exception("command_failed", host=host, command=command[:50])
        return CommandResult(success=False, error=str(e))
```

### 4. Lock-Free Pool with ConnectionStrategy

**New Implementation:**
```python
from typing import Protocol

class ConnectionStrategy(Protocol):
    """Strategy for managing SSH connections."""

    async def create_connection(self, host: SSHHost) -> asyncssh.SSHClientConnection:
        """Create new SSH connection."""
        ...

    def connection_is_closed(self, conn: asyncssh.SSHClientConnection) -> bool:
        """Check if connection is no longer usable."""
        ...

    async def close_connection(self, conn: asyncssh.SSHClientConnection) -> None:
        """Clean up connection."""
        ...

class LockFreeConnectionPool:
    """Lock-free connection pool using asyncio cooperative multitasking."""

    def __init__(
        self,
        strategy: ConnectionStrategy,
        max_size: int = 50,
        burst_limit: int | None = None
    ):
        self._strategy = strategy
        self._max_size = max_size
        self._burst_limit = burst_limit or max_size
        self._connections: dict[str, asyncssh.SSHClientConnection] = {}
        self._pending: dict[str, asyncio.Future] = {}

    async def get_connection(self, host: SSHHost) -> asyncssh.SSHClientConnection:
        """
        Get connection without explicit locking.

        Atomicity guaranteed by cooperative multitasking:
        - Operations between await points are atomic
        - Multiple tasks can safely check _connections dict
        - Only one task proceeds to create new connection per host
        """
        # Fast path: connection exists and is valid
        if host.name in self._connections:
            conn = self._connections[host.name]
            if not self._strategy.connection_is_closed(conn):
                return conn
            # Connection stale, remove it
            del self._connections[host.name]

        # Check if another task is creating connection
        if host.name in self._pending:
            # Wait for pending creation to complete
            return await self._pending[host.name]

        # This task will create the connection
        future: asyncio.Future = asyncio.Future()
        self._pending[host.name] = future

        try:
            # Enforce burst limit
            if len(self._connections) >= self._burst_limit:
                raise RuntimeError(f"Connection pool at burst limit ({self._burst_limit})")

            # Create connection (this is the only await - yields to event loop)
            conn = await self._strategy.create_connection(host)

            # Store connection
            self._connections[host.name] = conn
            future.set_result(conn)

            return conn

        except Exception as e:
            future.set_exception(e)
            raise

        finally:
            # Clean up pending tracker
            del self._pending[host.name]
```

### 5. Graceful Shutdown with Cancellable Operations

**New Implementation:**
```python
class ScoutServer:
    """Scout MCP server with graceful shutdown."""

    def __init__(self):
        self._pool = ConnectionPool()
        self._background_tasks: set[asyncio.Task] = set()
        self._shutdown_event = asyncio.Event()

    def create_background_task(self, coro):
        """Track background task with automatic cleanup."""
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

    async def start_cleanup_task(self):
        """Periodic cleanup with graceful shutdown support."""
        self.create_background_task(self._cleanup_loop())

    async def _cleanup_loop(self):
        """Run cleanup periodically until shutdown."""
        while not self._shutdown_event.is_set():
            try:
                # Wait with timeout to allow shutdown check
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=60.0  # Cleanup interval
                )
            except asyncio.TimeoutError:
                # Timeout is normal - run cleanup
                await self._pool.cleanup_idle_connections()

    async def shutdown(self):
        """Gracefully shut down server."""
        logger.info("shutdown_initiated")

        # Signal shutdown
        self._shutdown_event.set()

        # Cancel all background tasks
        for task in list(self._background_tasks):
            task.cancel()

        # Wait for cancellations with timeout
        try:
            await asyncio.wait_for(
                asyncio.gather(*self._background_tasks, return_exceptions=True),
                timeout=5.0
            )
        except asyncio.TimeoutError:
            logger.warning("shutdown_timeout", pending=len(self._background_tasks))

        # Close all connections
        await self._pool.close_all()

        logger.info("shutdown_complete")
```

### 6. Performance Monitoring Middleware

**New Implementation:**
```python
import time
from functools import wraps

def monitor_performance(threshold_ms: float = 1000.0):
    """Decorator to monitor async operation performance."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            operation_name = f"{func.__module__}.{func.__name__}"

            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start) * 1000

                if duration_ms > threshold_ms:
                    logger.warning(
                        "slow_operation",
                        operation=operation_name,
                        duration_ms=round(duration_ms, 2),
                        args=str(args)[:100]
                    )
                else:
                    logger.debug(
                        "operation_complete",
                        operation=operation_name,
                        duration_ms=round(duration_ms, 2)
                    )

                return result

            except Exception as e:
                duration_ms = (time.perf_counter() - start) * 1000
                logger.error(
                    "operation_failed",
                    operation=operation_name,
                    duration_ms=round(duration_ms, 2),
                    error=str(e)
                )
                raise

        return wrapper
    return decorator

# Usage
@monitor_performance(threshold_ms=500.0)
async def cat_file(conn: asyncssh.SSHClientConnection, path: str) -> str:
    """Read file with performance monitoring."""
    result = await conn.run(f"cat {path!r}")
    return result.stdout
```

---

## Summary of Key Recommendations

### Connection Pooling
1. Replace global lock with semaphore for concurrent access
2. Use per-host locks only for connection creation
3. Implement ConnectionStrategy pattern for flexibility
4. Add burst capacity for load spikes

### Task Management
5. Use TaskGroup (Python 3.11+) for structured concurrency
6. Track background tasks in a set to prevent garbage collection
7. Implement graceful shutdown with cancellable operations
8. Use asyncio.Event for clean shutdown signaling

### Error Handling
9. Use ExceptionGroup and except* for multiple concurrent failures
10. Log exceptions with full tracebacks using logging.exception()
11. Always re-raise CancelledError after cleanup
12. Implement defensive error handling at each layer

### Testing
13. Use pytest-asyncio with auto mode
14. Mock async operations with AsyncMock
15. Test race conditions with asyncio.Event for controlled execution
16. Never make real I/O calls in tests

### Performance
17. Profile with scalene or py-spy (not cProfile)
18. Monitor slow operations with threshold-based logging
19. Avoid blocking calls in async context
20. Use concurrent execution with gather() or TaskGroup

---

## Sources

### Official Python Documentation
- [Developing with asyncio - Python 3.14](https://docs.python.org/3/library/asyncio-dev.html)
- [Coroutines and Tasks - Python 3.14](https://docs.python.org/3/library/asyncio-task.html)
- [Synchronization Primitives - Python 3.14](https://docs.python.org/3/library/asyncio-sync.html)

### Python Enhancement Proposals
- [PEP 492 - Coroutines with async and await syntax](https://peps.python.org/pep-0492/)
- [PEP 789 - Preventing task-cancellation bugs](https://peps.python.org/pep-0789/)
- [PEP 3156 - Asynchronous IO Support](https://peps.python.org/pep-3156/)

### Best Practices Guides
- [Python's asyncio: A Hands-On Walkthrough - Real Python](https://realpython.com/async-io-python/)
- [Practical Guide to Asynchronous Programming in Python - Better Stack](https://betterstack.com/community/guides/scaling-python/python-async-programming/)
- [Asyncio best practices - Python.org Discussions](https://discuss.python.org/t/asyncio-best-practices/12576)
- [3 Essential Async Patterns for Building a Python Service - Elastic Blog](https://www.elastic.co/blog/async-patterns-building-python-service)
- [Asyncio Design Patterns](https://dev-kit.io/blog/python/asyncio-design-patterns)

### Connection Pooling
- [asyncio-connection-pool - PyPI](https://pypi.org/project/asyncio-connection-pool/)
- [asyncio-connection-pool - GitHub](https://github.com/fellowapp/asyncio-connection-pool)
- [asyncpg Usage Documentation](https://magicstack.github.io/asyncpg/current/usage.html)
- [SQLAlchemy AsyncIO Discussion](https://github.com/sqlalchemy/sqlalchemy/discussions/5980)

### Concurrency Patterns
- [Mastering Synchronization Primitives in Python Asyncio - Towards Data Science](https://towardsdatascience.com/mastering-synchronization-primitives-in-python-asyncio-a-comprehensive-guide-ae1ae720d0de/)
- [Limit concurrency with semaphore - Redowan's Reflections](https://rednafi.com/python/limit-concurrency-with-semaphore/)
- [Asyncio Semaphore in Python - Super Fast Python](https://superfastpython.com/asyncio-semaphore/)

### Task Management
- [How to use asyncio.TaskGroup - Super Fast Python](https://superfastpython.com/asyncio-taskgroup/)
- [Python 3.11 asyncio.TaskGroup - Bruce Eckel](https://bruceeckel.substack.com/p/python-311-asynciotaskgroup)
- [How to Kill All Asyncio Tasks - Super Fast Python](https://superfastpython.com/asyncio-kill-all-tasks/)
- [How to Garbage Collect Background Tasks - Stack Overflow](https://stackoverflow.com/questions/76160467/how-to-garbage-collect-python-background-asyncio-tasks)

### Error Handling
- [Exception Handling in Asyncio - Piccolo Blog](https://piccolo-orm.com/blog/exception-handling-in-asyncio/)
- [Asyncio Task Exception Handling - ProxiesAPI](https://proxiesapi.com/articles/asyncio-task-exception-handling)
- [How to Handle Asyncio Task Exceptions - Super Fast Python](https://superfastpython.com/asyncio-task-exceptions/)
- [How to Manage Exceptions When Waiting On Multiple Tasks](https://plainenglish.io/blog/how-to-manage-exceptions-when-waiting-on-multiple-asyncio)

### Testing
- [A Practical Guide To Async Testing With Pytest-Asyncio](https://pytest-with-eric.com/pytest-advanced/pytest-asyncio/)
- [Async Test Patterns for Pytest](https://tonybaloney.github.io/posts/async-test-patterns-for-pytest-and-unittest.html)
- [Mastering Async Context Manager Mocking - DZone](https://dzone.com/articles/mastering-async-context-manager-mocking-in-python)
- [Boost Your Python Testing with pytest asyncio](https://articles.mergify.com/pytest-asyncio/)

### Performance Profiling
- [Profiling Asynchronous Python - Medium](https://medium.com/@maximsmirnov/profiling-asynchronous-python-576568f6f2c0)
- [Profiling Python Code - Copdips](https://copdips.com/2024/06/profiling-python-code.html)
- [Rooting Out CPU Bottlenecks From Asyncio Services](https://www.balajeerc.info/Rooting-out-CPU-Bottlenecks-from-asyncio-based-API-services/)
- [Mastering AsyncIO: Performance Optimization](https://pydiary.com/posts/mastering_asyncio_in_python/9-performance-optimization-and-monitoring/)

### Recent Developments
- [Meta Contributes New Features to Python 3.12](https://engineering.fb.com/2023/10/05/developer-tools/python-312-meta-new-features/)
- [The State of Python 2025 - JetBrains](https://blog.jetbrains.com/pycharm/2025/08/the-state-of-python-2025/)
- [Asyncio in Python - The Essential Guide for 2025](https://medium.com/@shweta.trrev/asyncio-in-python-the-essential-guide-for-2025-a006074ee2d1)

---

**Report Compiled:** 2025-12-03
**Python Versions Covered:** 3.11, 3.12, 3.13, 3.14 (upcoming)
**Total Sources:** 40+ authoritative references
