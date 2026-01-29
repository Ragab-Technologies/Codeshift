"""
Old Celery patterns that need migration.
Uses deprecated patterns from Celery 4.x that changed in Celery 5.x+
"""
from celery import Celery, Task
from celery.decorators import task, periodic_task  # Deprecated imports
from celery.task import task as old_task_decorator  # Deprecated
from celery.schedules import crontab
from datetime import timedelta

# Old pattern: Using deprecated app configuration style
app = Celery('tasks')

# Old pattern: Using deprecated CELERY_ prefix configuration
app.conf.update(
    CELERY_BROKER_URL='redis://localhost:6379/0',  # Deprecated: use broker_url
    CELERY_RESULT_BACKEND='redis://localhost:6379/0',  # Deprecated: use result_backend
    CELERY_TASK_SERIALIZER='json',  # Deprecated: use task_serializer
    CELERY_RESULT_SERIALIZER='json',  # Deprecated: use result_serializer
    CELERY_ACCEPT_CONTENT=['json'],  # Deprecated: use accept_content
    CELERY_TIMEZONE='UTC',  # Deprecated: use timezone
    CELERY_ENABLE_UTC=True,  # Deprecated: use enable_utc
    CELERY_TASK_RESULT_EXPIRES=3600,  # Deprecated: use result_expires
)

# Old pattern: Using deprecated @task decorator from celery.decorators
@task(name='add_numbers')
def add(x, y):
    """Old task decorator pattern."""
    return x + y

# Old pattern: Using deprecated @periodic_task decorator
@periodic_task(run_every=timedelta(minutes=30))
def cleanup_old_data():
    """Deprecated periodic_task decorator."""
    print("Cleaning up old data...")

# Old pattern: Using deprecated task base class
class OldStyleTask(Task):
    """Old Task base class pattern."""
    abstract = True
    max_retries = 3
    default_retry_delay = 60
    
    # Deprecated: Using old callback style
    def on_success(self, retval, task_id, args, kwargs):
        print(f"Task {task_id} succeeded")
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        print(f"Task {task_id} failed: {exc}")

# Old pattern: Using deprecated bind=True with old signature
@app.task(bind=True, base=OldStyleTask)
def process_data_old_style(self, data):
    """Old bound task pattern."""
    try:
        result = data * 2
        return result
    except Exception as exc:
        # Old retry pattern
        self.retry(exc=exc, countdown=60)

# Old pattern: Using deprecated task.delay syntax without proper error handling
def trigger_task_old():
    """Old task triggering pattern."""
    result = add.delay(4, 4)
    # Old pattern: blocking get without timeout
    return result.get()

# Old pattern: Using deprecated apply_async with old parameters
def trigger_with_options_old():
    """Old apply_async pattern."""
    result = add.apply_async(
        args=[4, 4],
        countdown=10,
        expires=300,
        # Deprecated parameters
        eta=None,
        serializer='json',
        compression='zlib',
        routing_key='default'
    )
    return result

# Old pattern: Using deprecated chain syntax
from celery import chain, group, chord

def create_workflow_old():
    """Old workflow pattern."""
    # Old pattern: Using | operator without proper immutable signatures
    workflow = chain(add.s(2, 2), add.s(4), add.s(8))
    return workflow()

# Old pattern: Using deprecated beat schedule configuration
app.conf.beat_schedule = {
    'add-every-30-seconds': {
        'task': 'tasks.add',
        'schedule': 30.0,
        'args': (16, 16),
        # Deprecated: Using old schedule format
        'options': {
            'expires': 60,
        }
    },
}
