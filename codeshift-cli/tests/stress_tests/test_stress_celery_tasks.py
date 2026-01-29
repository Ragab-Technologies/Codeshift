"""
Stress test file for Celery 4.x to 5.x migration.

This file contains a complex, production-like Celery 4.x codebase with:
- 15+ task definitions with @task decorator
- Task inheritance and base tasks
- Chord, group, chain compositions
- Retry logic with exponential backoff
- Task routing and queues
- Periodic tasks with beat schedule
- Canvas signatures
- Error handling and callbacks
- Task states and result backend
- Deprecated settings (CELERY_ prefix)
- Rate limiting
- Task time limits
- Custom task serializers
- Task events and monitoring
- Worker signals

This tests the codeshift Celery 4.x -> 5.x migration transformer's ability
to handle real-world complexity.
"""

from __future__ import annotations

import random
import time
from datetime import timedelta
from typing import Any

# These are fine to keep
from celery import Celery, chain, chord, group
from celery.canvas import Signature

# ============================================================================
# CELERY 4.x STYLE IMPORTS (Should be transformed)
# ============================================================================
# Deprecated: celery.decorators module removed in 5.0
from celery.decorators import periodic_task, task
from celery.exceptions import MaxRetriesExceededError, Reject, Retry
from celery.result import AsyncResult, GroupResult
from celery.signals import (
    celeryd_init,
    task_failure,
    task_postrun,
    task_prerun,
    task_revoked,
    task_success,
    worker_init,
    worker_ready,
    worker_shutdown,
)

# Deprecated: celery.task module removed in 5.0
from celery.task import Task
from celery.task import task as task_alias
from celery.task.schedules import crontab

# Deprecated: celery.utils.encoding moved to kombu in 5.0
from celery.utils.encoding import safe_repr, safe_str
from celery.utils.log import get_task_logger

# ============================================================================
# APPLICATION CONFIGURATION (CELERY_ PREFIX - Should be transformed)
# ============================================================================

app = Celery('stress_test_app')

# Deprecated uppercase config keys (CELERY_ prefix should be removed in 5.0)
app.conf.CELERY_BROKER_URL = 'redis://localhost:6379/0'
app.conf.CELERY_RESULT_BACKEND = 'redis://localhost:6379/1'
app.conf.CELERY_TASK_SERIALIZER = 'json'
app.conf.CELERY_RESULT_SERIALIZER = 'json'
app.conf.CELERY_ACCEPT_CONTENT = ['json', 'msgpack']
app.conf.CELERY_TIMEZONE = 'UTC'
app.conf.CELERY_ENABLE_UTC = True
app.conf.CELERY_TASK_ALWAYS_EAGER = False
app.conf.CELERY_TASK_EAGER_PROPAGATES = True
app.conf.CELERY_TASK_IGNORE_RESULT = False
app.conf.CELERY_TASK_TRACK_STARTED = True
app.conf.CELERY_TASK_TIME_LIMIT = 3600
app.conf.CELERY_TASK_SOFT_TIME_LIMIT = 3000
app.conf.CELERY_TASK_ACKS_LATE = True
app.conf.CELERY_RESULT_EXPIRES = 86400
app.conf.CELERY_IMPORTS = ['tasks.email', 'tasks.reports']
app.conf.CELERY_INCLUDE = ['tasks.notifications']

# Deprecated CELERYD_ prefix for worker settings
app.conf.CELERYD_CONCURRENCY = 8
app.conf.CELERYD_PREFETCH_MULTIPLIER = 4
app.conf.CELERYD_MAX_TASKS_PER_CHILD = 1000
app.conf.CELERYD_DISABLE_RATE_LIMITS = False
app.conf.CELERYD_TASK_TIME_LIMIT = 7200
app.conf.CELERYD_TASK_SOFT_TIME_LIMIT = 6000

# Deprecated CELERYBEAT_ prefix
app.conf.CELERYBEAT_SCHEDULE = {
    'cleanup-every-hour': {
        'task': 'tasks.cleanup_old_data',
        'schedule': crontab(minute=0),
    },
    'daily-report': {
        'task': 'tasks.generate_daily_report',
        'schedule': crontab(hour=0, minute=0),
    },
}
app.conf.CELERYBEAT_SCHEDULER = 'celery.beat:PersistentScheduler'

# Subscript-style config access (should also be transformed)
app.conf['CELERY_TASK_ANNOTATIONS'] = {
    'tasks.high_priority': {'rate_limit': '100/m'},
    'tasks.low_priority': {'rate_limit': '10/m'},
}

# Variable assignment style
CELERY_BROKER_URL = 'amqp://guest:guest@localhost:5672/'
CELERY_RESULT_BACKEND = 'rpc://'

# Task routing configuration
app.conf.CELERY_ROUTES = {
    'tasks.email.*': {'queue': 'email'},
    'tasks.reports.*': {'queue': 'reports'},
    'tasks.priority.*': {'queue': 'priority', 'routing_key': 'priority.high'},
}

logger = get_task_logger(__name__)

# ============================================================================
# BASE TASK CLASSES (Task inheritance patterns)
# ============================================================================


class LoggedTask(Task):
    """Base task that logs execution details."""

    abstract = True

    def on_success(self, retval: Any, task_id: str, args: tuple, kwargs: dict) -> None:
        logger.info(f"Task {self.name}[{task_id}] succeeded with result: {retval}")

    def on_failure(
        self,
        exc: Exception,
        task_id: str,
        args: tuple,
        kwargs: dict,
        einfo: Any
    ) -> None:
        logger.error(f"Task {self.name}[{task_id}] failed: {exc}")

    def on_retry(
        self,
        exc: Exception,
        task_id: str,
        args: tuple,
        kwargs: dict,
        einfo: Any
    ) -> None:
        logger.warning(f"Task {self.name}[{task_id}] retrying due to: {exc}")


class RetryableTask(LoggedTask):
    """Task with automatic retry on failure."""

    abstract = True
    autoretry_for = (ConnectionError, TimeoutError)
    retry_kwargs = {'max_retries': 5}
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True


class TransactionalTask(Task):
    """Task that wraps execution in a database transaction."""

    abstract = True

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        with self._get_db_connection():
            return super().__call__(*args, **kwargs)

    def _get_db_connection(self) -> Any:
        # Mock database connection
        class MockConnection:
            def __enter__(self) -> MockConnection:
                return self
            def __exit__(self, *args: Any) -> None:
                pass
        return MockConnection()


# ============================================================================
# TASK DEFINITIONS (Using deprecated @task decorator)
# ============================================================================

# Task 1: Simple task with deprecated decorator
@task
def add(x: int, y: int) -> int:
    """Add two numbers together."""
    return x + y


# Task 2: Task with options
@task(bind=True, name='tasks.multiply')
def multiply(self, x: int, y: int) -> int:
    """Multiply two numbers with task binding."""
    logger.info(f"Executing {self.name} with args: {x}, {y}")
    return x * y


# Task 3: Task with rate limiting
@task(rate_limit='10/m')
def rate_limited_task(data: dict[str, Any]) -> dict[str, Any]:
    """Process data with rate limiting."""
    return {'processed': True, 'input': data}


# Task 4: Task with time limits
@task(time_limit=300, soft_time_limit=240)
def time_limited_task(large_dataset: list[Any]) -> int:
    """Process large dataset with time constraints."""
    total = 0
    for item in large_dataset:
        total += 1
        time.sleep(0.001)  # Simulate processing
    return total


# Task 5: Task with custom queue
@task(queue='priority', routing_key='priority.high')
def high_priority_task(message: str) -> str:
    """High priority task routed to specific queue."""
    return f"PRIORITY: {message}"


# Task 6: Task with ignore result
@task(ignore_result=True)
def fire_and_forget(event_type: str, payload: dict[str, Any]) -> None:
    """Fire and forget task that doesn't store results."""
    logger.info(f"Event {event_type}: {payload}")


# Task 7: Task with custom serializer
@task(serializer='json')
def json_serialized_task(data: dict[str, Any]) -> dict[str, Any]:
    """Task using JSON serialization."""
    return data


# Task 8: Task with retry configuration
@task(
    bind=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=700,
    retry_jitter=True,
    max_retries=5,
)
def retry_with_backoff(self, url: str) -> dict[str, Any]:
    """Task with exponential backoff retry."""
    if random.random() < 0.3:  # 30% chance of failure for testing
        raise ConnectionError("Simulated connection failure")
    return {'url': url, 'status': 'success'}


# Task 9: Task with manual retry
@task(bind=True, max_retries=3)
def manual_retry_task(self, data: dict[str, Any]) -> dict[str, Any]:
    """Task with manual retry logic."""
    try:
        # Simulate processing
        if random.random() < 0.5:
            raise ValueError("Processing failed")
        return {'processed': data}
    except ValueError as exc:
        # Exponential backoff
        countdown = 2 ** self.request.retries
        raise self.retry(exc=exc, countdown=countdown)


# Task 10: Task with error callbacks
@task
def on_task_error(request: Any, exc: Exception, traceback: Any) -> None:
    """Error callback handler."""
    logger.error(f"Task {request.id} failed: {exc}")


@task(bind=True, on_failure=on_task_error)
def task_with_error_callback(self, value: int) -> int:
    """Task that uses error callback."""
    if value < 0:
        raise ValueError("Value must be non-negative")
    return value * 2


# Task 11: Task using base class
@task(base=LoggedTask, bind=True)
def logged_computation(self, values: list[int]) -> int:
    """Task using custom base class."""
    result = sum(values)
    logger.info(f"Computed sum: {result}")
    return result


# Task 12: Task using retryable base
@task(base=RetryableTask, bind=True)
def fetch_external_data(self, endpoint: str) -> dict[str, Any]:
    """Fetch data from external API with auto-retry."""
    # Simulate API call
    if random.random() < 0.2:
        raise ConnectionError("API unavailable")
    return {'endpoint': endpoint, 'data': {'key': 'value'}}


# Task 13: Task with acks_late
@task(acks_late=True, reject_on_worker_lost=True)
def reliable_task(item_id: int) -> dict[str, Any]:
    """Task with late acknowledgement for reliability."""
    return {'item_id': item_id, 'processed': True}


# Task 14: Task with track_started
@task(track_started=True, bind=True)
def long_running_task(self, duration: int) -> dict[str, Any]:
    """Long running task that tracks started state."""
    self.update_state(state='PROGRESS', meta={'progress': 0})
    for i in range(duration):
        time.sleep(0.01)
        self.update_state(state='PROGRESS', meta={'progress': (i + 1) / duration * 100})
    return {'duration': duration, 'completed': True}


# Task 15: Task with custom task_id
@task(bind=True)
def idempotent_task(self, operation_id: str, data: dict[str, Any]) -> dict[str, Any]:
    """Idempotent task that uses custom task ID."""
    return {'operation_id': operation_id, 'result': data}


# Task 16: Task alias (using task_alias from celery.task)
@task_alias(name='tasks.aliased_task')
def aliased_task(message: str) -> str:
    """Task using the aliased import."""
    return f"Aliased: {message}"


# ============================================================================
# PERIODIC TASKS (Using deprecated @periodic_task decorator)
# ============================================================================

@periodic_task(run_every=timedelta(minutes=30))
def cleanup_old_data() -> int:
    """Clean up old data every 30 minutes."""
    deleted_count = random.randint(0, 100)
    logger.info(f"Cleaned up {deleted_count} old records")
    return deleted_count


@periodic_task(run_every=crontab(hour=0, minute=0))
def generate_daily_report() -> dict[str, Any]:
    """Generate daily report at midnight."""
    return {
        'report_date': time.strftime('%Y-%m-%d'),
        'total_tasks': random.randint(1000, 10000),
        'success_rate': random.uniform(0.95, 0.99),
    }


@periodic_task(run_every=crontab(minute='*/15'))
def heartbeat_check() -> dict[str, bool]:
    """Check system heartbeat every 15 minutes."""
    return {
        'database': True,
        'cache': True,
        'queue': True,
    }


# ============================================================================
# CANVAS OPERATIONS (Chord, Group, Chain)
# ============================================================================


def build_parallel_workflow(numbers: list[int]) -> GroupResult:
    """Build a parallel workflow using group."""
    # Create a group of add tasks
    job = group(add.s(n, n) for n in numbers)
    return job.apply_async()


def build_sequential_workflow(initial_value: int) -> AsyncResult:
    """Build a sequential workflow using chain."""
    workflow = chain(
        add.s(initial_value, 10),
        multiply.s(2),
        add.s(5),
    )
    return workflow.apply_async()


def build_chord_workflow(numbers: list[int]) -> AsyncResult:
    """Build a chord workflow (parallel with callback)."""
    # Sum all numbers in parallel, then multiply the result
    callback = multiply.s(10)
    header = group(add.s(n, 1) for n in numbers)
    workflow = chord(header)(callback)
    return workflow


def build_complex_workflow(data: dict[str, list[int]]) -> AsyncResult:
    """Build a complex nested workflow."""
    # Complex workflow with nested groups and chains
    workflows = []

    for key, numbers in data.items():
        # For each key, create a chain that processes numbers
        sub_workflow = chain(
            group(add.s(n, 1) for n in numbers),
            logged_computation.s(),
        )
        workflows.append(sub_workflow)

    # Run all sub-workflows in parallel
    main_workflow = group(workflows)
    return main_workflow.apply_async()


# ============================================================================
# SIGNATURE OPERATIONS
# ============================================================================


def create_signatures() -> list[Signature]:
    """Create various task signatures."""
    signatures = [
        # Simple signature
        add.signature((2, 3)),

        # Signature with options
        add.signature((4, 5), countdown=10),

        # Shortcut syntax
        add.s(6, 7),

        # Signature with routing
        add.signature((8, 9), queue='priority'),

        # Immutable signature
        add.si(10, 11),

        # Partial signature
        multiply.s(5),  # Will receive first argument later
    ]
    return signatures


def apply_signatures(signatures: list[Signature]) -> list[AsyncResult]:
    """Apply a list of signatures."""
    results = []
    for sig in signatures:
        result = sig.apply_async()
        results.append(result)
    return results


# ============================================================================
# RESULT HANDLING AND STATE MANAGEMENT
# ============================================================================


def check_task_status(task_id: str) -> dict[str, Any]:
    """Check the status of a task by ID."""
    result = AsyncResult(task_id)
    return {
        'task_id': task_id,
        'status': result.status,
        'ready': result.ready(),
        'successful': result.successful() if result.ready() else None,
        'result': result.result if result.ready() else None,
    }


def wait_for_results(results: list[AsyncResult], timeout: int = 30) -> list[Any]:
    """Wait for multiple results with timeout."""
    collected = []
    for result in results:
        try:
            value = result.get(timeout=timeout)
            collected.append(value)
        except Exception as e:
            collected.append({'error': str(e)})
    return collected


def revoke_tasks(task_ids: list[str], terminate: bool = False) -> None:
    """Revoke multiple tasks."""
    for task_id in task_ids:
        app.control.revoke(task_id, terminate=terminate)


# ============================================================================
# WORKER SIGNALS
# ============================================================================


@worker_init.connect
def worker_init_handler(sender: Any = None, **kwargs: Any) -> None:
    """Handle worker initialization."""
    logger.info("Worker initializing...")


@worker_ready.connect
def worker_ready_handler(sender: Any = None, **kwargs: Any) -> None:
    """Handle worker ready state."""
    logger.info("Worker is ready to accept tasks")


@worker_shutdown.connect
def worker_shutdown_handler(sender: Any = None, **kwargs: Any) -> None:
    """Handle worker shutdown."""
    logger.info("Worker shutting down...")


@celeryd_init.connect
def celeryd_init_handler(sender: Any = None, conf: Any = None, **kwargs: Any) -> None:
    """Handle celery daemon initialization."""
    logger.info(f"Celery daemon initialized with config: {conf}")


# ============================================================================
# TASK SIGNALS
# ============================================================================


@task_prerun.connect
def task_prerun_handler(
    sender: Any = None,
    task_id: str = None,
    task: Any = None,
    args: tuple = None,
    kwargs: dict = None,
    **extra: Any
) -> None:
    """Handle task pre-run event."""
    logger.debug(f"Task {task_id} starting: {task.name}")


@task_postrun.connect
def task_postrun_handler(
    sender: Any = None,
    task_id: str = None,
    task: Any = None,
    args: tuple = None,
    kwargs: dict = None,
    retval: Any = None,
    state: str = None,
    **extra: Any
) -> None:
    """Handle task post-run event."""
    logger.debug(f"Task {task_id} completed with state: {state}")


@task_success.connect
def task_success_handler(
    sender: Any = None,
    result: Any = None,
    **kwargs: Any
) -> None:
    """Handle task success event."""
    logger.info(f"Task succeeded: {sender.name}")


@task_failure.connect
def task_failure_handler(
    sender: Any = None,
    task_id: str = None,
    exception: Exception = None,
    args: tuple = None,
    kwargs: dict = None,
    traceback: Any = None,
    einfo: Any = None,
    **extra: Any
) -> None:
    """Handle task failure event."""
    logger.error(f"Task {task_id} failed: {exception}")


@task_revoked.connect
def task_revoked_handler(
    sender: Any = None,
    request: Any = None,
    terminated: bool = False,
    signum: int = None,
    expired: bool = False,
    **kwargs: Any
) -> None:
    """Handle task revoked event."""
    logger.warning(f"Task revoked: terminated={terminated}, expired={expired}")


# ============================================================================
# EXCEPTION HANDLING
# ============================================================================


@task(bind=True, max_retries=3)
def handle_max_retries(self, data: dict[str, Any]) -> dict[str, Any]:
    """Task demonstrating MaxRetriesExceededError handling."""
    try:
        # Simulate failure
        raise ConnectionError("Service unavailable")
    except ConnectionError as exc:
        try:
            raise self.retry(exc=exc, countdown=5)
        except MaxRetriesExceededError:
            logger.error("Max retries exceeded, sending to dead letter queue")
            return {'status': 'failed', 'reason': 'max_retries_exceeded'}


@task(bind=True)
def handle_rejection(self, item: dict[str, Any]) -> dict[str, Any]:
    """Task demonstrating Reject exception."""
    if not item.get('valid'):
        raise Reject("Invalid item", requeue=False)
    return {'processed': item}


@task(bind=True)
def handle_retry_exception(self, value: int) -> int:
    """Task demonstrating Retry exception."""
    if value < 0:
        raise Retry(exc=ValueError("Negative value"), when=10)
    return value * 2


# ============================================================================
# MONITORING AND EVENTS
# ============================================================================


def get_active_tasks() -> dict[str, list[dict[str, Any]]]:
    """Get all active tasks from workers."""
    inspect = app.control.inspect()
    return {
        'active': inspect.active() or {},
        'scheduled': inspect.scheduled() or {},
        'reserved': inspect.reserved() or {},
    }


def get_worker_stats() -> dict[str, Any]:
    """Get worker statistics."""
    inspect = app.control.inspect()
    return {
        'stats': inspect.stats() or {},
        'registered': inspect.registered() or {},
        'ping': inspect.ping() or {},
    }


def broadcast_shutdown() -> None:
    """Broadcast shutdown to all workers."""
    app.control.broadcast('shutdown')


def rate_limit_task(task_name: str, rate: str) -> None:
    """Dynamically set rate limit for a task."""
    app.control.rate_limit(task_name, rate)


# ============================================================================
# TASK ANNOTATIONS (Runtime configuration)
# ============================================================================

app.conf.CELERY_TASK_ANNOTATIONS = {
    'tasks.add': {
        'rate_limit': '100/s',
        'time_limit': 60,
    },
    'tasks.multiply': {
        'rate_limit': '50/s',
    },
    '*': {
        'retry_backoff': True,
    },
}


# ============================================================================
# CUSTOM SERIALIZERS
# ============================================================================


def register_custom_serializers() -> None:
    """Register custom serializers for specific data types."""
    import pickle

    from kombu.serialization import register

    def pickle_dumps(obj: Any) -> bytes:
        return pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)

    def pickle_loads(data: bytes) -> Any:
        return pickle.loads(data)

    register(
        'custom_pickle',
        pickle_dumps,
        pickle_loads,
        content_type='application/x-custom-pickle',
        content_encoding='binary',
    )


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def safe_string_representation(obj: Any) -> str:
    """Use the deprecated safe_str from celery.utils.encoding."""
    return safe_str(obj)


def safe_repr_representation(obj: Any) -> str:
    """Use the deprecated safe_repr from celery.utils.encoding."""
    return safe_repr(obj)


# ============================================================================
# MAIN EXECUTION (For testing)
# ============================================================================


if __name__ == '__main__':
    # Example usage
    print("Testing Celery 4.x stress test code...")

    # This would typically be run via celery worker
    # celery -A stress_test worker --loglevel=info

    # Test task signatures
    signatures = create_signatures()
    print(f"Created {len(signatures)} signatures")

    # Test workflow building
    parallel_result = build_parallel_workflow([1, 2, 3, 4, 5])
    print(f"Parallel workflow: {parallel_result}")

    sequential_result = build_sequential_workflow(10)
    print(f"Sequential workflow: {sequential_result}")

    print("Stress test module loaded successfully!")
