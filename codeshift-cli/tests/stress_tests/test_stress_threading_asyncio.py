"""
STRESS TEST: Complex Threading to Asyncio Migration

This file contains complex threading patterns that should be migrated to asyncio equivalents.
It tests the LLM migration capabilities for patterns without built-in AST transformers.

Migration targets:
- Thread pools -> asyncio.gather
- Queue -> asyncio.Queue
- Lock -> asyncio.Lock
- Event -> asyncio.Event
- Semaphore -> asyncio.Semaphore
- Barrier patterns
- Timer threads
- Daemon threads
- Thread-local storage
- Condition variables
- Producer-consumer patterns
- Thread synchronization
- Executor patterns
- concurrent.futures integration
- Blocking I/O to async I/O
"""

import logging
import queue
import random
import socket
import threading
import time
import urllib.request
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Barrier, Condition, Event, Lock, RLock, Semaphore, Thread, Timer
from typing import Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# 1. THREAD POOL TO ASYNCIO.GATHER MIGRATION
# =============================================================================

class ThreadPoolDataProcessor:
    """Process data items in parallel using ThreadPoolExecutor.

    Should migrate to:
    - async def process_items() with asyncio.gather()
    - async def process_single_item()
    """

    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.results: list[Any] = []
        self._lock = Lock()

    def process_single_item(self, item: dict) -> dict:
        """Process a single item - simulates I/O bound work."""
        time.sleep(random.uniform(0.1, 0.3))  # Simulate network call
        return {"processed": item, "timestamp": time.time()}

    def process_items(self, items: list[dict]) -> list[dict]:
        """Process multiple items in parallel using thread pool."""
        futures: list[Future] = []

        for item in items:
            future = self.executor.submit(self.process_single_item, item)
            futures.append(future)

        results = []
        for future in as_completed(futures):
            try:
                result = future.result(timeout=30)
                with self._lock:
                    self.results.append(result)
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing item: {e}")

        return results

    def shutdown(self) -> None:
        """Shutdown the executor."""
        self.executor.shutdown(wait=True)


# =============================================================================
# 2. QUEUE TO ASYNCIO.QUEUE MIGRATION
# =============================================================================

class ThreadedMessageQueue:
    """Message queue using threading.Queue.

    Should migrate to:
    - asyncio.Queue
    - async def put(), async def get()
    """

    def __init__(self, maxsize: int = 100):
        self._queue: queue.Queue = queue.Queue(maxsize=maxsize)
        self._priority_queue: queue.PriorityQueue = queue.PriorityQueue()
        self._lifo_queue: queue.LifoQueue = queue.LifoQueue()

    def put(self, message: str, priority: int = 0, block: bool = True, timeout: float | None = None) -> bool:
        """Put a message on the queue."""
        try:
            self._queue.put(message, block=block, timeout=timeout)
            self._priority_queue.put((priority, message))
            return True
        except queue.Full:
            logger.warning("Queue is full")
            return False

    def get(self, block: bool = True, timeout: float | None = None) -> str | None:
        """Get a message from the queue."""
        try:
            return self._queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None

    def get_priority(self) -> tuple[int, str] | None:
        """Get highest priority message."""
        try:
            return self._priority_queue.get_nowait()
        except queue.Empty:
            return None

    def task_done(self) -> None:
        """Mark task as done."""
        self._queue.task_done()

    def join(self) -> None:
        """Wait for all tasks to complete."""
        self._queue.join()

    @property
    def qsize(self) -> int:
        """Return queue size."""
        return self._queue.qsize()

    @property
    def empty(self) -> bool:
        """Check if queue is empty."""
        return self._queue.empty()


# =============================================================================
# 3. LOCK TO ASYNCIO.LOCK MIGRATION
# =============================================================================

class ThreadSafeCounter:
    """Thread-safe counter using Lock.

    Should migrate to:
    - asyncio.Lock
    - async with lock
    """

    def __init__(self):
        self._value = 0
        self._lock = Lock()
        self._rlock = RLock()  # Reentrant lock

    def increment(self) -> int:
        """Increment counter with lock."""
        with self._lock:
            self._value += 1
            return self._value

    def decrement(self) -> int:
        """Decrement counter with lock."""
        self._lock.acquire()
        try:
            self._value -= 1
            return self._value
        finally:
            self._lock.release()

    def add(self, amount: int) -> int:
        """Add amount with reentrant lock."""
        with self._rlock:
            for _ in range(amount):
                self._increment_internal()
            return self._value

    def _increment_internal(self) -> None:
        """Internal increment that can be called recursively with RLock."""
        with self._rlock:
            self._value += 1

    @property
    def value(self) -> int:
        """Get current value."""
        with self._lock:
            return self._value


# =============================================================================
# 4. EVENT TO ASYNCIO.EVENT MIGRATION
# =============================================================================

class ThreadedEventSystem:
    """Event-based signaling system using threading.Event.

    Should migrate to:
    - asyncio.Event
    - await event.wait()
    """

    def __init__(self):
        self._shutdown_event = Event()
        self._ready_event = Event()
        self._data_available = Event()
        self._data: Any | None = None

    def wait_for_ready(self, timeout: float | None = None) -> bool:
        """Wait for system to be ready."""
        return self._ready_event.wait(timeout=timeout)

    def signal_ready(self) -> None:
        """Signal that system is ready."""
        self._ready_event.set()

    def wait_for_shutdown(self, timeout: float | None = None) -> bool:
        """Wait for shutdown signal."""
        return self._shutdown_event.wait(timeout=timeout)

    def signal_shutdown(self) -> None:
        """Signal shutdown."""
        self._shutdown_event.set()

    def is_shutdown_requested(self) -> bool:
        """Check if shutdown was requested."""
        return self._shutdown_event.is_set()

    def clear_ready(self) -> None:
        """Clear ready signal."""
        self._ready_event.clear()

    def set_data(self, data: Any) -> None:
        """Set data and signal availability."""
        self._data = data
        self._data_available.set()

    def wait_for_data(self, timeout: float | None = None) -> Any | None:
        """Wait for data to be available."""
        if self._data_available.wait(timeout=timeout):
            self._data_available.clear()
            return self._data
        return None


# =============================================================================
# 5. SEMAPHORE TO ASYNCIO.SEMAPHORE MIGRATION
# =============================================================================

class RateLimitedResourcePool:
    """Resource pool with semaphore-based rate limiting.

    Should migrate to:
    - asyncio.Semaphore
    - asyncio.BoundedSemaphore
    """

    def __init__(self, max_concurrent: int = 5):
        self._semaphore = Semaphore(max_concurrent)
        self._bounded_semaphore = threading.BoundedSemaphore(max_concurrent)
        self._active_count = 0
        self._lock = Lock()

    @contextmanager
    def acquire_resource(self):
        """Acquire a resource slot."""
        self._semaphore.acquire()
        with self._lock:
            self._active_count += 1
        try:
            yield
        finally:
            with self._lock:
                self._active_count -= 1
            self._semaphore.release()

    def try_acquire(self, timeout: float = 1.0) -> bool:
        """Try to acquire with timeout."""
        return self._semaphore.acquire(timeout=timeout)

    def release(self) -> None:
        """Release the semaphore."""
        self._semaphore.release()

    @property
    def active_count(self) -> int:
        """Get count of active acquisitions."""
        with self._lock:
            return self._active_count


# =============================================================================
# 6. BARRIER PATTERNS
# =============================================================================

class SynchronizedWorkerPool:
    """Worker pool using Barrier for synchronization.

    Should migrate to:
    - asyncio barrier patterns using asyncio.Event or asyncio.Condition
    """

    def __init__(self, num_workers: int = 4):
        self._num_workers = num_workers
        self._barrier = Barrier(num_workers)
        self._workers: list[Thread] = []
        self._results: list[Any] = []
        self._lock = Lock()

    def _worker_task(self, worker_id: int, work_item: Any) -> None:
        """Worker task that synchronizes at barrier."""
        logger.info(f"Worker {worker_id} starting phase 1")
        time.sleep(random.uniform(0.1, 0.5))

        # Wait at barrier for all workers to complete phase 1
        self._barrier.wait()

        logger.info(f"Worker {worker_id} starting phase 2")
        result = {"worker": worker_id, "item": work_item, "completed": True}

        with self._lock:
            self._results.append(result)

        # Wait at barrier for all workers to complete phase 2
        self._barrier.wait()

    def run_parallel_work(self, work_items: list[Any]) -> list[Any]:
        """Run work items in parallel with barrier sync."""
        if len(work_items) != self._num_workers:
            raise ValueError(f"Need exactly {self._num_workers} work items")

        self._results.clear()

        for i, item in enumerate(work_items):
            worker = Thread(target=self._worker_task, args=(i, item))
            self._workers.append(worker)
            worker.start()

        for worker in self._workers:
            worker.join()

        self._workers.clear()
        return self._results


# =============================================================================
# 7. TIMER THREADS
# =============================================================================

class ScheduledTaskRunner:
    """Run tasks on a schedule using Timer threads.

    Should migrate to:
    - asyncio.create_task with asyncio.sleep
    - asyncio.call_later patterns
    """

    def __init__(self):
        self._timers: list[Timer] = []
        self._lock = Lock()
        self._running = True

    def schedule_once(self, delay: float, func: Callable, *args, **kwargs) -> Timer:
        """Schedule a function to run once after delay."""
        timer = Timer(delay, func, args=args, kwargs=kwargs)
        with self._lock:
            self._timers.append(timer)
        timer.start()
        return timer

    def schedule_repeating(self, interval: float, func: Callable, *args, **kwargs) -> None:
        """Schedule a function to run repeatedly at interval."""
        def repeating_wrapper():
            if self._running:
                func(*args, **kwargs)
                self.schedule_repeating(interval, func, *args, **kwargs)

        self.schedule_once(interval, repeating_wrapper)

    def cancel_all(self) -> None:
        """Cancel all scheduled timers."""
        self._running = False
        with self._lock:
            for timer in self._timers:
                timer.cancel()
            self._timers.clear()


# =============================================================================
# 8. DAEMON THREADS
# =============================================================================

class BackgroundMonitor:
    """Background monitoring using daemon threads.

    Should migrate to:
    - asyncio.create_task for background tasks
    - Proper cancellation with asyncio.CancelledError
    """

    def __init__(self):
        self._daemon_thread: Thread | None = None
        self._stop_event = Event()
        self._metrics: dict[str, Any] = {}
        self._lock = Lock()

    def start(self) -> None:
        """Start background monitoring."""
        self._stop_event.clear()
        self._daemon_thread = Thread(target=self._monitor_loop, daemon=True)
        self._daemon_thread.start()

    def stop(self) -> None:
        """Stop background monitoring."""
        self._stop_event.set()
        if self._daemon_thread:
            self._daemon_thread.join(timeout=5.0)

    def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while not self._stop_event.is_set():
            with self._lock:
                self._metrics["timestamp"] = time.time()
                self._metrics["memory_usage"] = random.randint(100, 1000)
                self._metrics["cpu_usage"] = random.uniform(0.1, 100.0)

            # Wait for 1 second or until stop event
            self._stop_event.wait(timeout=1.0)

    def get_metrics(self) -> dict[str, Any]:
        """Get current metrics."""
        with self._lock:
            return self._metrics.copy()


# =============================================================================
# 9. THREAD-LOCAL STORAGE
# =============================================================================

class RequestContext:
    """Thread-local request context.

    Should migrate to:
    - contextvars.ContextVar
    - async context management
    """

    _local = threading.local()

    @classmethod
    def set_request_id(cls, request_id: str) -> None:
        """Set request ID for current thread."""
        cls._local.request_id = request_id

    @classmethod
    def get_request_id(cls) -> str | None:
        """Get request ID for current thread."""
        return getattr(cls._local, "request_id", None)

    @classmethod
    def set_user(cls, user: dict) -> None:
        """Set user for current thread."""
        cls._local.user = user

    @classmethod
    def get_user(cls) -> dict | None:
        """Get user for current thread."""
        return getattr(cls._local, "user", None)

    @classmethod
    def clear(cls) -> None:
        """Clear thread-local data."""
        cls._local.__dict__.clear()


# =============================================================================
# 10. CONDITION VARIABLES
# =============================================================================

class BoundedBuffer:
    """Bounded buffer using Condition variables.

    Should migrate to:
    - asyncio.Condition
    - async with condition
    """

    def __init__(self, capacity: int = 10):
        self._capacity = capacity
        self._buffer: list[Any] = []
        self._lock = Lock()
        self._not_full = Condition(self._lock)
        self._not_empty = Condition(self._lock)

    def put(self, item: Any) -> None:
        """Put item in buffer, waiting if full."""
        with self._not_full:
            while len(self._buffer) >= self._capacity:
                self._not_full.wait()

            self._buffer.append(item)
            self._not_empty.notify()

    def get(self) -> Any:
        """Get item from buffer, waiting if empty."""
        with self._not_empty:
            while len(self._buffer) == 0:
                self._not_empty.wait()

            item = self._buffer.pop(0)
            self._not_full.notify()
            return item

    def put_timeout(self, item: Any, timeout: float) -> bool:
        """Put with timeout, returns False if timed out."""
        with self._not_full:
            if not self._not_full.wait_for(
                lambda: len(self._buffer) < self._capacity,
                timeout=timeout
            ):
                return False

            self._buffer.append(item)
            self._not_empty.notify()
            return True

    @property
    def size(self) -> int:
        """Get current buffer size."""
        with self._lock:
            return len(self._buffer)


# =============================================================================
# 11. PRODUCER-CONSUMER PATTERNS
# =============================================================================

@dataclass
class WorkItem:
    """Work item for producer-consumer pattern."""
    id: int
    data: Any
    priority: int = 0


class ProducerConsumerSystem:
    """Producer-consumer pattern using threads.

    Should migrate to:
    - asyncio tasks for producers and consumers
    - asyncio.Queue for work queue
    """

    def __init__(self, num_producers: int = 2, num_consumers: int = 4):
        self._work_queue: queue.Queue = queue.Queue(maxsize=100)
        self._result_queue: queue.Queue = queue.Queue()
        self._num_producers = num_producers
        self._num_consumers = num_consumers
        self._producers: list[Thread] = []
        self._consumers: list[Thread] = []
        self._stop_event = Event()
        self._items_produced = 0
        self._items_consumed = 0
        self._lock = Lock()

    def _producer_task(self, producer_id: int) -> None:
        """Producer task that generates work items."""
        item_count = 0
        while not self._stop_event.is_set():
            item = WorkItem(
                id=item_count,
                data=f"Producer {producer_id} item {item_count}",
                priority=random.randint(1, 10)
            )
            try:
                self._work_queue.put(item, timeout=1.0)
                with self._lock:
                    self._items_produced += 1
                item_count += 1
            except queue.Full:
                pass

            time.sleep(random.uniform(0.01, 0.1))

    def _consumer_task(self, consumer_id: int) -> None:
        """Consumer task that processes work items."""
        while not self._stop_event.is_set():
            try:
                item = self._work_queue.get(timeout=1.0)
                # Simulate processing
                time.sleep(random.uniform(0.01, 0.05))

                result = {"consumer": consumer_id, "item": item, "processed_at": time.time()}
                self._result_queue.put(result)

                with self._lock:
                    self._items_consumed += 1

                self._work_queue.task_done()
            except queue.Empty:
                pass

    def start(self) -> None:
        """Start producers and consumers."""
        self._stop_event.clear()

        for i in range(self._num_producers):
            producer = Thread(target=self._producer_task, args=(i,))
            self._producers.append(producer)
            producer.start()

        for i in range(self._num_consumers):
            consumer = Thread(target=self._consumer_task, args=(i,))
            self._consumers.append(consumer)
            consumer.start()

    def stop(self) -> None:
        """Stop all producers and consumers."""
        self._stop_event.set()

        for producer in self._producers:
            producer.join()
        self._producers.clear()

        for consumer in self._consumers:
            consumer.join()
        self._consumers.clear()

    def get_stats(self) -> dict[str, int]:
        """Get production/consumption statistics."""
        with self._lock:
            return {
                "items_produced": self._items_produced,
                "items_consumed": self._items_consumed,
                "queue_size": self._work_queue.qsize()
            }


# =============================================================================
# 12. THREAD SYNCHRONIZATION PATTERNS
# =============================================================================

class ReadWriteLock:
    """Read-write lock implementation.

    Should migrate to:
    - asyncio patterns for reader-writer locks
    """

    def __init__(self):
        self._read_ready = Condition(Lock())
        self._readers = 0
        self._writers_waiting = 0
        self._writing = False

    @contextmanager
    def read_lock(self):
        """Acquire read lock."""
        with self._read_ready:
            while self._writing or self._writers_waiting > 0:
                self._read_ready.wait()
            self._readers += 1

        try:
            yield
        finally:
            with self._read_ready:
                self._readers -= 1
                if self._readers == 0:
                    self._read_ready.notify_all()

    @contextmanager
    def write_lock(self):
        """Acquire write lock."""
        with self._read_ready:
            self._writers_waiting += 1
            while self._readers > 0 or self._writing:
                self._read_ready.wait()
            self._writers_waiting -= 1
            self._writing = True

        try:
            yield
        finally:
            with self._read_ready:
                self._writing = False
                self._read_ready.notify_all()


class SharedState:
    """Shared state protected by read-write lock."""

    def __init__(self):
        self._lock = ReadWriteLock()
        self._data: dict[str, Any] = {}

    def read(self, key: str) -> Any | None:
        """Read a value."""
        with self._lock.read_lock():
            return self._data.get(key)

    def write(self, key: str, value: Any) -> None:
        """Write a value."""
        with self._lock.write_lock():
            self._data[key] = value

    def read_all(self) -> dict[str, Any]:
        """Read all data."""
        with self._lock.read_lock():
            return self._data.copy()


# =============================================================================
# 13. EXECUTOR PATTERNS
# =============================================================================

class HybridExecutor:
    """Executor that handles both CPU and I/O bound work.

    Should migrate to:
    - asyncio.to_thread for blocking calls
    - asyncio.gather for concurrent execution
    - ProcessPoolExecutor in loop.run_in_executor
    """

    def __init__(self, io_workers: int = 10, cpu_workers: int = 4):
        self._io_executor = ThreadPoolExecutor(max_workers=io_workers, thread_name_prefix="io")
        self._cpu_executor = ThreadPoolExecutor(max_workers=cpu_workers, thread_name_prefix="cpu")

    def submit_io(self, func: Callable, *args, **kwargs) -> Future:
        """Submit I/O bound work."""
        return self._io_executor.submit(func, *args, **kwargs)

    def submit_cpu(self, func: Callable, *args, **kwargs) -> Future:
        """Submit CPU bound work."""
        return self._cpu_executor.submit(func, *args, **kwargs)

    def map_io(self, func: Callable, items: list[Any]) -> list[Any]:
        """Map function over items using I/O executor."""
        return list(self._io_executor.map(func, items))

    def map_cpu(self, func: Callable, items: list[Any]) -> list[Any]:
        """Map function over items using CPU executor."""
        return list(self._cpu_executor.map(func, items))

    def execute_parallel(self, tasks: list[tuple[Callable, tuple]]) -> list[Any]:
        """Execute multiple tasks in parallel."""
        futures = []
        for func, args in tasks:
            futures.append(self._io_executor.submit(func, *args))

        results = []
        for future in as_completed(futures):
            results.append(future.result())

        return results

    def shutdown(self) -> None:
        """Shutdown all executors."""
        self._io_executor.shutdown(wait=True)
        self._cpu_executor.shutdown(wait=True)


# =============================================================================
# 14. CONCURRENT.FUTURES INTEGRATION
# =============================================================================

class BatchProcessor:
    """Batch processor using concurrent.futures.

    Should migrate to:
    - asyncio.gather with semaphore for rate limiting
    - asyncio.TaskGroup (Python 3.11+)
    """

    def __init__(self, max_workers: int = 8):
        self._max_workers = max_workers

    def process_batch(
        self,
        items: list[Any],
        processor: Callable[[Any], Any],
        timeout: float = 30.0
    ) -> tuple[list[Any], list[Exception]]:
        """Process a batch of items concurrently."""
        results = []
        errors = []

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            future_to_item = {
                executor.submit(processor, item): item
                for item in items
            }

            for future in as_completed(future_to_item, timeout=timeout):
                item = future_to_item[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    errors.append(e)
                    logger.error(f"Error processing {item}: {e}")

        return results, errors

    def process_with_callback(
        self,
        items: list[Any],
        processor: Callable[[Any], Any],
        on_complete: Callable[[Any, Any], None],
        on_error: Callable[[Any, Exception], None]
    ) -> None:
        """Process items with callbacks."""
        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            future_to_item = {}

            for item in items:
                future = executor.submit(processor, item)
                future_to_item[future] = item

                def make_callback(item):
                    def callback(f):
                        try:
                            result = f.result()
                            on_complete(item, result)
                        except Exception as e:
                            on_error(item, e)
                    return callback

                future.add_done_callback(make_callback(item))


# =============================================================================
# 15. BLOCKING I/O TO ASYNC I/O
# =============================================================================

class SyncHttpClient:
    """Synchronous HTTP client using blocking I/O.

    Should migrate to:
    - aiohttp or httpx async client
    - async def methods
    """

    def __init__(self, timeout: float = 30.0):
        self._timeout = timeout

    def get(self, url: str) -> tuple[int, str]:
        """Perform GET request."""
        try:
            with urllib.request.urlopen(url, timeout=self._timeout) as response:
                return response.status, response.read().decode("utf-8")
        except Exception as e:
            raise RuntimeError(f"HTTP GET failed: {e}") from e

    def get_multiple(self, urls: list[str]) -> list[tuple[str, int, str]]:
        """Fetch multiple URLs in parallel using threads."""
        results = []
        lock = Lock()

        def fetch(url: str):
            status, body = self.get(url)
            with lock:
                results.append((url, status, body))

        threads = [Thread(target=fetch, args=(url,)) for url in urls]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        return results


class SyncSocketClient:
    """Synchronous socket client.

    Should migrate to:
    - asyncio streams (StreamReader, StreamWriter)
    - async def connect(), send(), recv()
    """

    def __init__(self, host: str, port: int, timeout: float = 10.0):
        self._host = host
        self._port = port
        self._timeout = timeout
        self._socket: socket.socket | None = None
        self._lock = Lock()

    def connect(self) -> None:
        """Connect to server."""
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.settimeout(self._timeout)
        self._socket.connect((self._host, self._port))

    def send(self, data: bytes) -> int:
        """Send data to server."""
        if not self._socket:
            raise RuntimeError("Not connected")

        with self._lock:
            return self._socket.send(data)

    def recv(self, buffer_size: int = 4096) -> bytes:
        """Receive data from server."""
        if not self._socket:
            raise RuntimeError("Not connected")

        with self._lock:
            return self._socket.recv(buffer_size)

    def close(self) -> None:
        """Close connection."""
        if self._socket:
            self._socket.close()
            self._socket = None


# =============================================================================
# INTEGRATION TEST: Full System Using All Patterns
# =============================================================================

class DistributedTaskProcessor:
    """
    Complex system that uses all threading patterns.

    This is the ultimate stress test for migration to asyncio.
    """

    def __init__(
        self,
        num_workers: int = 4,
        queue_size: int = 100,
        rate_limit: int = 10
    ):
        # Thread pool
        self._executor = ThreadPoolExecutor(max_workers=num_workers)

        # Queue
        self._task_queue: queue.Queue = queue.Queue(maxsize=queue_size)
        self._result_queue: queue.Queue = queue.Queue()

        # Synchronization
        self._lock = Lock()
        self._rlock = RLock()
        self._event = Event()
        self._semaphore = Semaphore(rate_limit)
        self._condition = Condition(self._lock)

        # Thread-local context
        self._context = threading.local()

        # State
        self._workers: list[Thread] = []
        self._running = False
        self._stats: dict[str, int] = {"processed": 0, "failed": 0}

        # Timer for periodic cleanup
        self._cleanup_timer: Timer | None = None

    def _set_context(self, task_id: str) -> None:
        """Set thread-local context."""
        self._context.task_id = task_id
        self._context.start_time = time.time()

    def _get_context(self) -> dict[str, Any]:
        """Get thread-local context."""
        return {
            "task_id": getattr(self._context, "task_id", None),
            "start_time": getattr(self._context, "start_time", None)
        }

    def _worker_loop(self, worker_id: int) -> None:
        """Main worker loop."""
        while self._running:
            try:
                task = self._task_queue.get(timeout=1.0)

                # Rate limit with semaphore
                with self._semaphore._cond:
                    self._semaphore.acquire()
                    try:
                        self._set_context(f"task-{task.id}")
                        result = self._process_task(task)
                        self._result_queue.put(result)

                        with self._lock:
                            self._stats["processed"] += 1
                    finally:
                        self._semaphore.release()

                self._task_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                with self._lock:
                    self._stats["failed"] += 1
                logger.error(f"Worker {worker_id} error: {e}")

    def _process_task(self, task: WorkItem) -> dict[str, Any]:
        """Process a single task."""
        time.sleep(random.uniform(0.01, 0.1))  # Simulate work
        context = self._get_context()
        return {
            "task_id": task.id,
            "data": task.data,
            "context": context,
            "processed_at": time.time()
        }

    def _cleanup_loop(self) -> None:
        """Periodic cleanup task."""
        if self._running:
            logger.info("Running periodic cleanup")
            # Schedule next cleanup
            self._cleanup_timer = Timer(60.0, self._cleanup_loop)
            self._cleanup_timer.start()

    def start(self) -> None:
        """Start the processor."""
        self._running = True

        # Start workers
        for i in range(4):
            worker = Thread(target=self._worker_loop, args=(i,), daemon=True)
            self._workers.append(worker)
            worker.start()

        # Start cleanup timer
        self._cleanup_timer = Timer(60.0, self._cleanup_loop)
        self._cleanup_timer.start()

        # Signal ready
        self._event.set()

    def stop(self) -> None:
        """Stop the processor."""
        self._running = False

        # Cancel cleanup timer
        if self._cleanup_timer:
            self._cleanup_timer.cancel()

        # Wait for workers
        for worker in self._workers:
            worker.join(timeout=5.0)
        self._workers.clear()

        # Clear event
        self._event.clear()

    def submit(self, task: WorkItem) -> None:
        """Submit a task for processing."""
        self._task_queue.put(task)

    def wait_for_completion(self, timeout: float | None = None) -> bool:
        """Wait for all tasks to complete."""
        # Use condition to wait
        with self._condition:
            start_time = time.time()
            while self._task_queue.qsize() > 0:
                remaining = None
                if timeout:
                    elapsed = time.time() - start_time
                    remaining = max(0, timeout - elapsed)
                    if remaining <= 0:
                        return False

                self._condition.wait(timeout=remaining or 1.0)

        return True

    def get_results(self) -> list[dict[str, Any]]:
        """Get all available results."""
        results = []
        while True:
            try:
                result = self._result_queue.get_nowait()
                results.append(result)
            except queue.Empty:
                break
        return results

    def get_stats(self) -> dict[str, int]:
        """Get processing statistics."""
        with self._lock:
            return self._stats.copy()


# =============================================================================
# TEST FUNCTIONS
# =============================================================================

def test_thread_pool_processor():
    """Test ThreadPoolDataProcessor."""
    processor = ThreadPoolDataProcessor(max_workers=4)
    items = [{"id": i, "value": f"item_{i}"} for i in range(10)]

    results = processor.process_items(items)
    assert len(results) == 10

    processor.shutdown()
    print("ThreadPoolDataProcessor: PASS")


def test_message_queue():
    """Test ThreadedMessageQueue."""
    mq = ThreadedMessageQueue(maxsize=10)

    mq.put("message1")
    mq.put("message2", priority=1)

    assert mq.get() == "message1"
    assert not mq.empty
    print("ThreadedMessageQueue: PASS")


def test_thread_safe_counter():
    """Test ThreadSafeCounter."""
    counter = ThreadSafeCounter()

    threads = []
    for _ in range(10):
        t = Thread(target=lambda: counter.increment())
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    assert counter.value == 10
    print("ThreadSafeCounter: PASS")


def test_event_system():
    """Test ThreadedEventSystem."""
    events = ThreadedEventSystem()

    def worker():
        events.wait_for_ready(timeout=5.0)
        events.set_data({"result": "success"})

    t = Thread(target=worker)
    t.start()

    time.sleep(0.1)
    events.signal_ready()

    data = events.wait_for_data(timeout=5.0)
    assert data == {"result": "success"}

    t.join()
    print("ThreadedEventSystem: PASS")


def test_semaphore_pool():
    """Test RateLimitedResourcePool."""
    pool = RateLimitedResourcePool(max_concurrent=3)

    active_counts = []

    def worker():
        with pool.acquire_resource():
            active_counts.append(pool.active_count)
            time.sleep(0.1)

    threads = [Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert max(active_counts) <= 3
    print("RateLimitedResourcePool: PASS")


def test_producer_consumer():
    """Test ProducerConsumerSystem."""
    system = ProducerConsumerSystem(num_producers=2, num_consumers=4)
    system.start()

    time.sleep(1.0)

    stats = system.get_stats()
    assert stats["items_produced"] > 0
    assert stats["items_consumed"] > 0

    system.stop()
    print("ProducerConsumerSystem: PASS")


def test_distributed_processor():
    """Test DistributedTaskProcessor."""
    processor = DistributedTaskProcessor(num_workers=4, queue_size=100, rate_limit=5)
    processor.start()

    # Submit tasks
    for i in range(20):
        processor.submit(WorkItem(id=i, data=f"task_{i}"))

    # Wait for completion
    time.sleep(2.0)

    stats = processor.get_stats()
    assert stats["processed"] > 0

    processor.stop()
    print("DistributedTaskProcessor: PASS")


def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("THREADING TO ASYNCIO STRESS TEST")
    print("=" * 60 + "\n")

    test_thread_pool_processor()
    test_message_queue()
    test_thread_safe_counter()
    test_event_system()
    test_semaphore_pool()
    test_producer_consumer()
    test_distributed_processor()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    run_all_tests()
