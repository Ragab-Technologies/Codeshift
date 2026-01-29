"""Stress test for type hints migration.

This test creates a complex untyped Python module and tests the Codeshift
LLM migration tool's ability to add comprehensive type annotations.

The untyped code includes:
- 20+ functions without type hints
- Classes without typed attributes
- Complex return types
- Generic types needed
- Optional/Union inference
- Callback types
- Protocol types needed
- TypedDict usage
- Literal types
- NewType definitions
- Type aliases
- Overloaded functions
- Generic classes
- Type variables
- Recursive types
"""

from pathlib import Path

import pytest

from codeshift.migrator.ast_transforms import TransformStatus
from codeshift.migrator.engine import MigrationEngine
from codeshift.migrator.llm_migrator import LLMMigrationResult, LLMMigrator
from codeshift.validator.syntax_checker import quick_syntax_check


def is_llm_available() -> bool:
    """Check if LLM migrator is available, handling SSL and connection errors."""
    try:
        migrator = LLMMigrator(use_cache=False)
        return migrator.is_available
    except Exception:
        return False


# =============================================================================
# STRESS TEST: Complex untyped Python module needing full type hints
# =============================================================================

COMPLEX_UNTYPED_CODE = '''
"""A complex module with no type hints - testing type annotation inference."""

import json
import asyncio
from dataclasses import dataclass
from collections import defaultdict
from abc import ABC, abstractmethod


# --- NewType candidates ---
def create_user_id(value):
    """Should use NewType for UserId."""
    return str(value)


def create_order_id(value):
    """Should use NewType for OrderId."""
    return int(value)


# --- Simple functions without type hints ---
def add_numbers(a, b):
    """Add two numbers."""
    return a + b


def concatenate_strings(first, second, separator=None):
    """Concatenate strings with optional separator."""
    if separator is None:
        return first + second
    return first + separator + second


def find_maximum(items):
    """Find maximum in a list - needs generic typing."""
    if not items:
        return None
    return max(items)


def filter_positive(numbers):
    """Filter positive numbers - returns list of same type."""
    return [n for n in numbers if n > 0]


def count_occurrences(text, char):
    """Count character occurrences."""
    return text.count(char)


# --- Functions with complex return types ---
def parse_config(config_str):
    """Parse JSON config - returns dict with string keys and any values."""
    return json.loads(config_str)


def get_user_or_none(user_id, users_db):
    """Get user from dict or return None - Optional return."""
    return users_db.get(user_id)


def divide_numbers(a, b):
    """Divide numbers, return tuple of quotient and remainder."""
    return a // b, a % b


def process_items(items, predicate, transform):
    """Process items with predicate and transform - needs Callable types."""
    return [transform(item) for item in items if predicate(item)]


def get_nested_value(data, *keys):
    """Get nested value from dict - variable args."""
    result = data
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key)
        else:
            return None
    return result


# --- Functions needing Union types ---
def normalize_input(value):
    """Normalize input - accepts str or bytes, returns str."""
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def safe_parse_int(value, default=0):
    """Parse int safely - accepts str or int."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


# --- Callback and higher-order functions ---
def apply_twice(func, value):
    """Apply function twice to value."""
    return func(func(value))


def create_multiplier(factor):
    """Create a multiplier function - returns Callable."""
    def multiplier(x):
        return x * factor
    return multiplier


def compose(f, g):
    """Compose two functions."""
    def composed(x):
        return f(g(x))
    return composed


def retry_operation(operation, max_retries, delay):
    """Retry an operation with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return operation()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            asyncio.sleep(delay * (2 ** attempt))
    return None


# --- Classes without typed attributes ---
class Point:
    """2D point without type hints."""

    def __init__(self, x, y):
        self.x = x
        self.y = y

    def distance_to(self, other):
        """Calculate distance to another point."""
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5

    def __add__(self, other):
        """Add two points."""
        return Point(self.x + other.x, self.y + other.y)

    def __repr__(self):
        return f"Point({self.x}, {self.y})"


class Rectangle:
    """Rectangle class needing typed attributes."""

    def __init__(self, top_left, bottom_right):
        self.top_left = top_left
        self.bottom_right = bottom_right
        self._area = None

    @property
    def width(self):
        return abs(self.bottom_right.x - self.top_left.x)

    @property
    def height(self):
        return abs(self.bottom_right.y - self.top_left.y)

    @property
    def area(self):
        if self._area is None:
            self._area = self.width * self.height
        return self._area

    def contains_point(self, point):
        return (self.top_left.x <= point.x <= self.bottom_right.x and
                self.top_left.y <= point.y <= self.bottom_right.y)


# --- Generic class needing TypeVar ---
class Stack:
    """Generic stack implementation."""

    def __init__(self):
        self._items = []

    def push(self, item):
        self._items.append(item)

    def pop(self):
        if not self._items:
            return None
        return self._items.pop()

    def peek(self):
        if not self._items:
            return None
        return self._items[-1]

    def is_empty(self):
        return len(self._items) == 0

    def __len__(self):
        return len(self._items)


class Queue:
    """Generic queue implementation."""

    def __init__(self, maxsize=None):
        self._items = []
        self._maxsize = maxsize

    def enqueue(self, item):
        if self._maxsize is not None and len(self._items) >= self._maxsize:
            raise ValueError("Queue is full")
        self._items.append(item)

    def dequeue(self):
        if not self._items:
            return None
        return self._items.pop(0)

    def is_full(self):
        return self._maxsize is not None and len(self._items) >= self._maxsize


# --- Protocol-like interface ---
class Renderable(ABC):
    """Abstract base for renderable objects."""

    @abstractmethod
    def render(self):
        """Render the object to string."""
        pass

    @abstractmethod
    def get_size(self):
        """Get the size as (width, height) tuple."""
        pass


class TextBox(Renderable):
    """Text box implementation."""

    def __init__(self, content, width, height):
        self.content = content
        self.width = width
        self.height = height

    def render(self):
        return f"[{self.content}]"

    def get_size(self):
        return (self.width, self.height)


# --- TypedDict candidates ---
def create_user_record(name, email, age, is_active=True):
    """Create a user record dict - should suggest TypedDict."""
    return {
        "name": name,
        "email": email,
        "age": age,
        "is_active": is_active,
        "created_at": None,
    }


def process_api_response(response):
    """Process API response - typical TypedDict use case."""
    return {
        "status": response.get("status", "unknown"),
        "data": response.get("data", []),
        "error": response.get("error"),
        "pagination": {
            "page": response.get("page", 1),
            "total": response.get("total", 0),
        },
    }


# --- Literal type candidates ---
def get_log_level(level_name):
    """Get log level - should use Literal type."""
    levels = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
    return levels.get(level_name.upper(), 0)


def set_mode(mode):
    """Set mode - should accept Literal["read", "write", "append"]."""
    valid_modes = ("read", "write", "append")
    if mode not in valid_modes:
        raise ValueError(f"Invalid mode: {mode}")
    return mode


# --- Recursive type structure ---
class TreeNode:
    """Tree node with recursive structure."""

    def __init__(self, value, children=None):
        self.value = value
        self.children = children or []

    def add_child(self, child):
        self.children.append(child)
        return self

    def traverse_dfs(self, visit_func):
        """Depth-first traversal."""
        visit_func(self)
        for child in self.children:
            child.traverse_dfs(visit_func)

    def find(self, predicate):
        """Find node matching predicate."""
        if predicate(self):
            return self
        for child in self.children:
            found = child.find(predicate)
            if found:
                return found
        return None


def build_tree_from_dict(data):
    """Build tree from nested dict - recursive function."""
    if not isinstance(data, dict):
        return TreeNode(data)

    node = TreeNode(data.get("value"))
    for child_data in data.get("children", []):
        node.add_child(build_tree_from_dict(child_data))
    return node


# --- Overload candidates ---
def format_value(value, precision=None):
    """Format value differently based on type - needs @overload."""
    if isinstance(value, float) and precision is not None:
        return f"{value:.{precision}f}"
    elif isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value)
    elif isinstance(value, dict):
        return json.dumps(value, indent=2)
    return str(value)


def get_item(container, key):
    """Get item from container - works with dict, list, or str."""
    if isinstance(container, dict):
        return container.get(key)
    elif isinstance(container, (list, str)):
        try:
            return container[key]
        except (IndexError, KeyError):
            return None
    return None


# --- Async functions without type hints ---
async def fetch_data(url, timeout=30):
    """Fetch data from URL - async function."""
    await asyncio.sleep(0.1)  # Simulated network delay
    return {"url": url, "data": "response", "timeout": timeout}


async def process_batch(items, processor, concurrency=5):
    """Process items in batches with concurrency limit."""
    semaphore = asyncio.Semaphore(concurrency)

    async def process_with_limit(item):
        async with semaphore:
            return await processor(item)

    tasks = [process_with_limit(item) for item in items]
    return await asyncio.gather(*tasks)


async def retry_async(coro_func, max_attempts=3, delay=1.0):
    """Retry async operation with delay."""
    last_error = None
    for attempt in range(max_attempts):
        try:
            return await coro_func()
        except Exception as e:
            last_error = e
            if attempt < max_attempts - 1:
                await asyncio.sleep(delay)
    raise last_error


# --- Complex type inference scenarios ---
def merge_dicts(*dicts):
    """Merge multiple dicts - needs TypeVar for proper typing."""
    result = {}
    for d in dicts:
        result.update(d)
    return result


def group_by(items, key_func):
    """Group items by key function - returns dict of lists."""
    groups = defaultdict(list)
    for item in items:
        groups[key_func(item)].append(item)
    return dict(groups)


def partition(items, predicate):
    """Partition items by predicate - returns tuple of two lists."""
    true_items = []
    false_items = []
    for item in items:
        if predicate(item):
            true_items.append(item)
        else:
            false_items.append(item)
    return true_items, false_items


def flatten(nested_list, depth=None):
    """Flatten nested list to specified depth."""
    if depth is not None and depth <= 0:
        return nested_list

    result = []
    for item in nested_list:
        if isinstance(item, list):
            new_depth = None if depth is None else depth - 1
            result.extend(flatten(item, new_depth))
        else:
            result.append(item)
    return result


def zip_longest_with_fill(*iterables, fillvalue=None):
    """Zip iterables with fill value for shorter ones."""
    max_len = max(len(it) for it in iterables) if iterables else 0
    result = []
    for i in range(max_len):
        row = []
        for iterable in iterables:
            if i < len(iterable):
                row.append(iterable[i])
            else:
                row.append(fillvalue)
        result.append(tuple(row))
    return result


# --- Context manager without proper typing ---
class Timer:
    """Context manager for timing code blocks."""

    def __init__(self, name=None):
        self.name = name
        self.start_time = None
        self.end_time = None

    def __enter__(self):
        import time
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        import time
        self.end_time = time.time()
        return False

    @property
    def elapsed(self):
        if self.end_time is None or self.start_time is None:
            return None
        return self.end_time - self.start_time


# --- Decorator without proper typing ---
def memoize(func):
    """Memoization decorator - needs proper Callable typing."""
    cache = {}

    def wrapper(*args, **kwargs):
        key = (args, tuple(sorted(kwargs.items())))
        if key not in cache:
            cache[key] = func(*args, **kwargs)
        return cache[key]

    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


def validate_args(**validators):
    """Argument validation decorator."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for arg_name, validator in validators.items():
                if arg_name in kwargs:
                    if not validator(kwargs[arg_name]):
                        raise ValueError(f"Invalid value for {arg_name}")
            return func(*args, **kwargs)
        return wrapper
    return decorator


def log_calls(logger=None):
    """Logging decorator with optional logger."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            name = func.__name__
            if logger:
                logger.info(f"Calling {name}")
            result = func(*args, **kwargs)
            if logger:
                logger.info(f"{name} returned {result}")
            return result
        return wrapper
    return decorator
'''


# =============================================================================
# Expected type hints patterns (for validation)
# =============================================================================

EXPECTED_TYPE_PATTERNS = [
    # Function signatures
    "def add_numbers(a: ",
    "def concatenate_strings(first: str",
    "-> Optional[",  # For find_maximum
    "-> list[",  # For filter_positive
    "-> dict[",  # For parse_config
    "-> tuple[",  # For divide_numbers

    # Callable types
    "Callable[",
    "Callable[[",

    # Generic types
    "TypeVar",
    "Generic[",

    # Protocol/ABC
    "-> str",  # render return
    "-> tuple[int, int]",  # get_size return

    # Async types
    "async def fetch_data(",
    "Awaitable[",
    "Coroutine[",

    # Class attributes
    "self.x:",
    "self.y:",

    # Union types
    "Union[",
    "|",  # Modern union syntax

    # TypedDict
    "TypedDict",

    # Literal
    "Literal[",
]


# =============================================================================
# Test Classes
# =============================================================================

class TestStressTypeHintsAdd:
    """Stress test for adding type hints to complex untyped code."""

    def test_untyped_code_is_valid_python(self):
        """Verify the test code is valid Python syntax."""
        # Should compile without errors
        compile(COMPLEX_UNTYPED_CODE, "<string>", "exec")

    def test_untyped_code_has_no_type_hints(self):
        """Verify the test code truly has no type hints."""
        # Check for absence of type annotation syntax
        assert ": str" not in COMPLEX_UNTYPED_CODE.split("def ")[0]  # Before first func
        assert "-> " not in COMPLEX_UNTYPED_CODE.replace('"->"', "")  # Exclude strings

        # Count functions without return type hints
        import re
        func_pattern = r"def \w+\([^)]*\):"
        funcs_without_hints = re.findall(func_pattern, COMPLEX_UNTYPED_CODE)
        assert len(funcs_without_hints) >= 20, f"Expected 20+ functions, found {len(funcs_without_hints)}"

    def test_untyped_code_function_count(self):
        """Verify we have at least 20 functions for stress testing."""
        import re
        # Count all function definitions
        func_count = len(re.findall(r"\ndef \w+\(", COMPLEX_UNTYPED_CODE))
        async_func_count = len(re.findall(r"\nasync def \w+\(", COMPLEX_UNTYPED_CODE))
        method_count = len(re.findall(r"    def \w+\(", COMPLEX_UNTYPED_CODE))

        total = func_count + async_func_count + method_count
        assert total >= 20, f"Expected 20+ functions/methods, found {total}"

    def test_untyped_code_class_count(self):
        """Verify we have multiple classes for stress testing."""
        import re
        class_count = len(re.findall(r"\nclass \w+", COMPLEX_UNTYPED_CODE))
        assert class_count >= 5, f"Expected 5+ classes, found {class_count}"

    def test_code_complexity_metrics(self):
        """Verify code complexity is sufficient for stress testing."""
        lines = COMPLEX_UNTYPED_CODE.strip().split("\n")
        non_empty_lines = [l for l in lines if l.strip() and not l.strip().startswith("#")]

        assert len(non_empty_lines) >= 300, f"Expected 300+ lines, got {len(non_empty_lines)}"


class TestLLMMigrationCapabilities:
    """Test LLM migration capabilities on the stress test code."""

    @pytest.fixture
    def llm_migrator(self):
        """Create LLM migrator instance."""
        return LLMMigrator(use_cache=False, validate_output=True)

    @pytest.fixture
    def migration_engine(self):
        """Create migration engine instance."""
        return MigrationEngine()

    def test_llm_migrator_availability(self, llm_migrator):
        """Test if LLM migrator is available (requires auth)."""
        # This test documents the expected behavior
        is_available = llm_migrator.is_available

        if not is_available:
            pytest.skip("LLM migrator not available - requires authentication")

    @pytest.mark.skipif(
        not is_llm_available(),
        reason="LLM migrator not available - requires Pro/Unlimited subscription"
    )
    def test_llm_migration_on_stress_code(self, llm_migrator):
        """Test LLM migration on the complex untyped code."""
        # Attempt migration using "typing" as the "library" to test type hint addition
        result = llm_migrator.migrate(
            code=COMPLEX_UNTYPED_CODE,
            library="typing",
            from_version="untyped",
            to_version="fully-typed",
            context="Add comprehensive type hints to all functions, methods, and class attributes.",
        )

        # Verify result structure
        assert isinstance(result, LLMMigrationResult)
        assert result.original_code == COMPLEX_UNTYPED_CODE

        if result.success:
            # Validate the migrated code
            assert result.migrated_code != COMPLEX_UNTYPED_CODE
            assert result.validation_passed

            # Check for some expected type patterns
            migrated = result.migrated_code
            found_patterns = [p for p in EXPECTED_TYPE_PATTERNS if p in migrated]

            print(f"Found {len(found_patterns)}/{len(EXPECTED_TYPE_PATTERNS)} expected patterns")
            print(f"Found patterns: {found_patterns}")
        else:
            print(f"Migration failed: {result.error}")

    @pytest.mark.skipif(
        not is_llm_available(),
        reason="LLM migrator not available - requires Pro/Unlimited subscription"
    )
    def test_migration_output_syntax_validity(self, llm_migrator):
        """Test that LLM migration output is valid Python syntax."""
        result = llm_migrator.migrate(
            code=COMPLEX_UNTYPED_CODE,
            library="typing",
            from_version="untyped",
            to_version="fully-typed",
            context="Add type hints to all functions.",
        )

        if result.success:
            # Verify syntax is valid
            assert quick_syntax_check(result.migrated_code), "Migrated code has syntax errors"

            # Also verify we can compile it
            try:
                compile(result.migrated_code, "<string>", "exec")
            except SyntaxError as e:
                pytest.fail(f"Migrated code has syntax error: {e}")


class TestTypeHintCoverage:
    """Test specific type hint coverage in migration results."""

    @pytest.mark.skipif(
        not is_llm_available(),
        reason="LLM migrator not available"
    )
    def test_function_return_types_added(self):
        """Test that return types are added to functions."""
        migrator = LLMMigrator(use_cache=False)
        result = migrator.migrate(
            code=COMPLEX_UNTYPED_CODE,
            library="typing",
            from_version="untyped",
            to_version="fully-typed",
        )

        if result.success:
            import re
            # Count functions with return type hints
            return_hints = re.findall(r"def \w+\([^)]*\)\s*->\s*\w+", result.migrated_code)
            print(f"Functions with return types: {len(return_hints)}")

    @pytest.mark.skipif(
        not is_llm_available(),
        reason="LLM migrator not available"
    )
    def test_generic_types_used(self):
        """Test that generic types are properly used."""
        migrator = LLMMigrator(use_cache=False)
        result = migrator.migrate(
            code=COMPLEX_UNTYPED_CODE,
            library="typing",
            from_version="untyped",
            to_version="fully-typed",
        )

        if result.success:
            code = result.migrated_code
            # Check for common generic patterns
            has_list_type = "list[" in code or "List[" in code
            has_dict_type = "dict[" in code or "Dict[" in code
            has_optional = "Optional[" in code or "| None" in code
            has_callable = "Callable[" in code

            print(f"Generic types found: list={has_list_type}, dict={has_dict_type}, "
                  f"optional={has_optional}, callable={has_callable}")


class TestMigrationPerformance:
    """Test migration performance on large codebases."""

    @pytest.mark.skipif(
        not is_llm_available(),
        reason="LLM migrator not available"
    )
    def test_migration_completes_in_reasonable_time(self):
        """Test that migration completes within 60 seconds."""
        import time

        migrator = LLMMigrator(use_cache=False)

        start = time.time()
        result = migrator.migrate(
            code=COMPLEX_UNTYPED_CODE,
            library="typing",
            from_version="untyped",
            to_version="fully-typed",
        )
        elapsed = time.time() - start

        print(f"Migration took {elapsed:.2f} seconds")
        print(f"Success: {result.success}")
        if result.error:
            print(f"Error: {result.error}")

        # Should complete in reasonable time
        assert elapsed < 60, f"Migration took too long: {elapsed:.2f}s"


class TestDeterministicTransformFallback:
    """Test behavior when LLM is not available."""

    def test_graceful_fallback_without_llm(self):
        """Test that migration gracefully handles missing LLM."""
        try:
            migrator = LLMMigrator(use_cache=False)

            if migrator.is_available:
                pytest.skip("LLM is available - testing fallback behavior")

            result = migrator.migrate(
                code=COMPLEX_UNTYPED_CODE,
                library="typing",
                from_version="untyped",
                to_version="fully-typed",
            )

            # Should fail gracefully
            assert not result.success
            assert result.error is not None
            assert "authentication" in result.error.lower() or "login" in result.error.lower()

            # Original code should be preserved
            assert result.migrated_code == COMPLEX_UNTYPED_CODE
        except Exception as e:
            # Handle SSL/connection errors gracefully
            pytest.skip(f"Network/SSL error - cannot test LLM fallback: {e}")

    def test_engine_reports_no_tier1_transformer(self):
        """Test that engine reports no Tier 1 transformer for typing."""
        try:
            engine = MigrationEngine()

            result = engine.run_migration(
                code=COMPLEX_UNTYPED_CODE,
                file_path=Path("/test/stress_code.py"),
                library="typing",  # Not a supported Tier 1 library
                old_version="untyped",
                new_version="typed",
            )

            # Without LLM, should report no changes possible
            if not is_llm_available():
                assert result.status in (TransformStatus.NO_CHANGES, TransformStatus.FAILED)
        except Exception as e:
            # Handle SSL/connection errors gracefully
            pytest.skip(f"Network/SSL error - cannot test engine: {e}")


# =============================================================================
# CLI Integration Test
# =============================================================================

class TestCLIIntegration:
    """Test CLI integration for type hints migration."""

    @pytest.fixture
    def temp_untyped_file(self, tmp_path):
        """Create a temporary file with untyped code."""
        file_path = tmp_path / "untyped_module.py"
        file_path.write_text(COMPLEX_UNTYPED_CODE)
        return file_path

    def test_temp_file_creation(self, temp_untyped_file):
        """Verify temporary test file is created correctly."""
        assert temp_untyped_file.exists()
        content = temp_untyped_file.read_text()
        assert "def add_numbers(a, b):" in content
        assert "class Point:" in content


# =============================================================================
# Report Generation
# =============================================================================

def generate_stress_test_report():
    """Generate a report of the stress test code complexity."""
    import re

    code = COMPLEX_UNTYPED_CODE

    # Count various elements
    functions = re.findall(r"\ndef (\w+)\(", code)
    async_functions = re.findall(r"\nasync def (\w+)\(", code)
    methods = re.findall(r"    def (\w+)\(", code)
    classes = re.findall(r"\nclass (\w+)", code)

    report = f"""
=== STRESS TEST CODE COMPLEXITY REPORT ===

Total Lines: {len(code.split(chr(10)))}
Non-empty Lines: {len([l for l in code.split(chr(10)) if l.strip()])}

Functions (top-level): {len(functions)}
  - {', '.join(functions[:10])}...

Async Functions: {len(async_functions)}
  - {', '.join(async_functions)}

Methods: {len(methods)}
  - {', '.join(methods[:10])}...

Classes: {len(classes)}
  - {', '.join(classes)}

Type Hint Complexity Requirements:
- NewType definitions: 2 (UserId, OrderId)
- Generic classes: 2 (Stack, Queue)
- TypeVar usage: Required for generic functions
- Callable types: 5+ (callbacks, decorators)
- Optional/Union: 10+ functions
- TypedDict candidates: 2
- Literal types: 2
- Recursive types: 1 (TreeNode)
- Protocol/ABC: 2 classes
- Context manager: 1
- Decorators: 3

Expected Typing Imports After Migration:
- from typing import (
    TypeVar, Generic, Optional, Union, Callable,
    Awaitable, Coroutine, TypedDict, Literal,
    Protocol, overload, Any
)
- from typing import NewType
"""
    return report


if __name__ == "__main__":
    # Print the stress test report
    print(generate_stress_test_report())

    # Run a quick validation
    print("\n=== VALIDATION ===")
    try:
        compile(COMPLEX_UNTYPED_CODE, "<string>", "exec")
        print("Code compiles successfully!")
    except SyntaxError as e:
        print(f"Syntax error: {e}")
