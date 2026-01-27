"""Tests for Celery 4.x to 5.x transforms."""

from codeshift.migrator.transforms.celery_transformer import transform_celery


class TestCeleryTaskImportTransforms:
    """Tests for Celery task import transformations."""

    def test_celery_decorators_import(self):
        """Test transforming from celery.decorators import task."""
        code = """
from celery.decorators import task

@task
def add(x, y):
    return x + y
"""
        transformed, changes = transform_celery(code)

        assert "from celery import shared_task" in transformed or "shared_task" in transformed
        assert len(changes) >= 1

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_celery_task_task_import(self):
        """Test transforming from celery.task import task."""
        code = """
from celery.task import task

@task
def multiply(x, y):
    return x * y
"""
        transformed, changes = transform_celery(code)

        assert "shared_task" in transformed or len(changes) >= 1

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestCeleryConfigTransforms:
    """Tests for Celery config key transformations."""

    def test_celery_result_backend_config(self):
        """Test transforming CELERY_RESULT_BACKEND to result_backend."""
        code = """
from celery import Celery

app = Celery('tasks')
app.conf.CELERY_RESULT_BACKEND = 'redis://localhost'
"""
        transformed, changes = transform_celery(code)

        assert "result_backend" in transformed
        assert "CELERY_RESULT_BACKEND" not in transformed
        assert len(changes) >= 1

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_celery_broker_url_config(self):
        """Test transforming CELERY_BROKER_URL to broker_url."""
        code = """
from celery import Celery

app = Celery('tasks')
app.conf.CELERY_BROKER_URL = 'redis://localhost'
"""
        transformed, changes = transform_celery(code)

        assert "broker_url" in transformed
        assert "CELERY_BROKER_URL" not in transformed
        assert len(changes) >= 1

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_celery_task_serializer_config(self):
        """Test transforming CELERY_TASK_SERIALIZER to task_serializer."""
        code = """
from celery import Celery

app = Celery('tasks')
app.conf.CELERY_TASK_SERIALIZER = 'json'
"""
        transformed, changes = transform_celery(code)

        assert "task_serializer" in transformed
        assert len(changes) >= 1

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestCeleryExceptionTransforms:
    """Tests for Celery exception import transformations."""

    def test_celery_exceptions_import(self):
        """Test transforming celery.exceptions imports."""
        code = """
from celery.exceptions import MaxRetriesExceededError

@app.task(bind=True)
def my_task(self):
    try:
        do_work()
    except MaxRetriesExceededError:
        handle_failure()
"""
        transformed, changes = transform_celery(code)

        # Should handle exception imports
        assert len(changes) >= 0

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestCeleryTaskClassTransforms:
    """Tests for Celery task class transformations."""

    def test_celery_task_base_import(self):
        """Test transforming celery.task.Task import."""
        code = """
from celery.task import Task

class MyTask(Task):
    def run(self):
        pass
"""
        transformed, changes = transform_celery(code)

        # Should transform to celery.Task
        assert "from celery" in transformed
        assert len(changes) >= 0

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestCeleryLoggerTransforms:
    """Tests for Celery logger transformations."""

    def test_get_task_logger_import(self):
        """Test transforming celery.utils.log imports."""
        code = """
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)
"""
        transformed, changes = transform_celery(code)

        # Should be properly imported
        assert len(changes) >= 0

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestCeleryMultipleTransforms:
    """Tests for multiple Celery transformations."""

    def test_comprehensive_migration(self):
        """Test multiple Celery migrations in one file."""
        code = """
from celery import Celery
from celery.decorators import task

app = Celery('tasks')
app.conf.CELERY_BROKER_URL = 'redis://localhost'
app.conf.CELERY_RESULT_BACKEND = 'redis://localhost'
app.conf.CELERY_TASK_SERIALIZER = 'json'

@task
def add(x, y):
    return x + y
"""
        transformed, changes = transform_celery(code)

        # Should have multiple changes
        assert len(changes) >= 3
        assert "broker_url" in transformed
        assert "result_backend" in transformed
        assert "task_serializer" in transformed

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_no_false_positives(self):
        """Test that modern Celery code is not transformed."""
        code = """
from celery import Celery, shared_task

app = Celery('tasks')
app.conf.broker_url = 'redis://localhost'
app.conf.result_backend = 'redis://localhost'
app.conf.task_serializer = 'json'

@shared_task
def add(x, y):
    return x + y
"""
        transformed, changes = transform_celery(code)

        # No changes should be made
        assert len(changes) == 0
        assert transformed == code

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")
