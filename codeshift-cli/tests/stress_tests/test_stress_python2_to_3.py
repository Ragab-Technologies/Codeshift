"""
Stress test file: Python 2 migration patterns (Python 3 compatible syntax).

This file tests legacy patterns that may need modernization.
All code is valid Python 3 syntax but contains patterns that could be improved.

NOTE: Codeshift is designed for LIBRARY migrations (pydantic v1->v2, etc.),
not Python 2 to Python 3 migrations. This file is kept as a reference for
potential future Python modernization features, but the actual stress test
for Codeshift should focus on library migrations.
"""

from __future__ import annotations

import configparser
import io
import queue
import sys
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

# =============================================================================
# LEGACY PATTERNS - VALID PYTHON 3 BUT COULD BE MODERNIZED
# =============================================================================

# -----------------------------------------------------------------------------
# 1. Old-style string formatting (% operator)
# -----------------------------------------------------------------------------
def format_strings_old_style() -> tuple:
    """Use old-style % string formatting - could use f-strings."""
    name = "Alice"
    age = 30
    score = 95.5

    # Basic formatting - could be f-strings
    greeting = "Hello, %s!" % name
    info = "Name: %s, Age: %d" % (name, age)
    precise = "Score: %.2f%%" % score

    # Width and alignment
    padded = "|%10s|%-10s|%10d|" % (name, name, age)

    # Multiple types
    complex_format = "User: %s (ID: %05d) - Score: %6.2f - Active: %s" % (
        name, 42, score, True
    )

    # Dict-based formatting
    data = {'name': name, 'age': age}
    from_dict = "%(name)s is %(age)d years old" % data

    return greeting, info, precise, padded, complex_format, from_dict


# -----------------------------------------------------------------------------
# 2. .format() method - could be f-strings
# -----------------------------------------------------------------------------
def format_strings_format_method() -> tuple:
    """Use .format() method - could use f-strings in most cases."""
    name = "Bob"
    age = 25

    basic = f"Hello, {name}!"
    positional = f"Name: {name}, Age: {age}"
    keyword = f"Name: {name}, Age: {age}"
    mixed = f"{name} is {age} years old"

    return basic, positional, keyword, mixed


# -----------------------------------------------------------------------------
# 3. Type checking with isinstance (old patterns)
# -----------------------------------------------------------------------------
def check_types_old_style(obj: Any) -> str:
    """Type checking - could use match statement in Python 3.10+."""
    if isinstance(obj, str):
        return "string"
    elif isinstance(obj, (int, float)):
        return "number"
    elif isinstance(obj, (list, tuple)):
        return "sequence"
    elif isinstance(obj, dict):
        return "mapping"
    else:
        return "unknown"


# -----------------------------------------------------------------------------
# 4. Dictionary operations (Python 3 compatible but verbose)
# -----------------------------------------------------------------------------
def process_dictionary(data: dict) -> tuple:
    """Dictionary operations using explicit iteration."""
    result = {}

    # Could use dict comprehension
    for key, value in data.items():
        result[key] = value * 2

    # Collecting keys - could use list(data.keys()) or just list(data)
    all_keys = []
    for k in data.keys():
        all_keys.append(k)

    # Summing values - could use sum(data.values())
    total = 0
    for v in data.values():
        total += v

    # Check key existence - 'in' is preferred over .get() for presence check
    has_important = "important" in data

    return result, all_keys, total


# -----------------------------------------------------------------------------
# 5. URL handling (modern pattern but verbose)
# -----------------------------------------------------------------------------
def fetch_url(url: str) -> tuple | None:
    """Fetch URL using urllib - could use requests/httpx."""
    try:
        request = Request(url)
        request.add_header('User-Agent', 'Python-urllib/3.x')

        response = urlopen(request, timeout=30)
        content = response.read()

        # Parse URL components
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)

        # URL encode data
        encoded = urlencode({'key': 'value', 'name': 'test'})

        return content, query_params, encoded
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return None


# -----------------------------------------------------------------------------
# 6. Buffer operations
# -----------------------------------------------------------------------------
def buffer_operations() -> tuple:
    """Buffer operations using io module."""
    # StringIO
    buffer = io.StringIO()
    buffer.write("Line 1\n")
    buffer.write("Line 2\n")
    content = buffer.getvalue()

    # BytesIO
    byte_buffer = io.BytesIO()
    byte_buffer.write(b"Binary content")
    binary_content = byte_buffer.getvalue()

    return content, binary_content


# -----------------------------------------------------------------------------
# 7. Config parsing
# -----------------------------------------------------------------------------
def read_config(config_path: str) -> tuple:
    """Read configuration using configparser."""
    config = configparser.ConfigParser()
    config.read(config_path)

    # Get values with defaults
    debug = config.getboolean('main', 'debug', fallback=False)
    port = config.getint('server', 'port', fallback=8080)
    host = config.get('server', 'host', fallback='localhost')

    # Iterate sections
    for section in config.sections():
        print(f"Section: {section}")
        for option in config.options(section):
            print(f"  {option} = {config.get(section, option)}")

    return debug, port, host


# -----------------------------------------------------------------------------
# 8. Queue operations
# -----------------------------------------------------------------------------
def create_worker_queue() -> tuple:
    """Create queues using queue module."""
    # Standard FIFO queue
    task_queue: queue.Queue = queue.Queue()

    # Priority queue
    priority_queue: queue.PriorityQueue = queue.PriorityQueue()

    # LIFO queue (stack)
    stack: queue.LifoQueue = queue.LifoQueue()

    # Add items
    for i in range(10):
        task_queue.put(f"Task {i}")
        priority_queue.put((i, f"Priority task {i}"))
        stack.put(f"Stack item {i}")

    # Get items with timeout
    try:
        item = task_queue.get(timeout=5)
    except queue.Empty:
        print("Queue is empty!")

    return task_queue, priority_queue, stack


# -----------------------------------------------------------------------------
# 9. Classes with explicit object inheritance (Python 3 implicit)
# -----------------------------------------------------------------------------
class ModernClass:
    """Modern Python 3 class - no need to inherit from object."""

    class_var = "I am a class variable"

    def __init__(self, value: Any) -> None:
        self.value = value
        self.instance_var = "I am an instance variable"

    def get_value(self) -> Any:
        return self.value

    def __lt__(self, other: ModernClass) -> bool:
        """Modern comparison method."""
        return self.instance_var < other.instance_var

    def __eq__(self, other: object) -> bool:
        """Modern equality method."""
        if not isinstance(other, ModernClass):
            return NotImplemented
        return self.instance_var == other.instance_var


# -----------------------------------------------------------------------------
# 10. map/filter with explicit list conversion
# -----------------------------------------------------------------------------
def map_filter_operations() -> tuple:
    """Map/filter operations - could use list comprehensions."""
    numbers = list(range(20))

    # map with list() - could be list comprehension
    doubled = list(map(lambda x: x * 2, numbers))
    stringified = list(map(str, numbers))

    # filter with list() - could be list comprehension
    evens = list(filter(lambda x: x % 2 == 0, numbers))
    positives = list(filter(None, [-1, 0, 1, 2, -3, 4]))

    # reduce
    from functools import reduce
    total = reduce(lambda a, b: a + b, numbers)

    # Combined operations - could be nested list comprehension
    result = list(map(lambda x: x ** 2, filter(lambda x: x % 2 == 0, numbers)))

    # zip with list()
    names = ['Alice', 'Bob', 'Charlie']
    ages = [25, 30, 35]
    combined = list(zip(names, ages))

    return doubled, evens, total, result, combined


# -----------------------------------------------------------------------------
# 11. Exception handling (modern syntax)
# -----------------------------------------------------------------------------
def exception_handling() -> None:
    """Exception handling with modern Python 3 syntax."""
    try:
        result = 1 / 0
    except ZeroDivisionError as e:
        print(f"Division error: {e}")

    try:
        data = open("nonexistent.txt").read()
    except OSError as e:
        print(f"IO Error: {e.errno} {e.strerror}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        print("Cleanup complete")

    # Multiple exception types with modern syntax
    try:
        risky_operation()
    except (ValueError, TypeError) as e:
        print(f"Value or Type error: {e}")
    except KeyError as e:
        print(f"Key error: {e}")


def risky_operation() -> None:
    """Placeholder for risky operation."""
    pass


# -----------------------------------------------------------------------------
# 12. Complex combined class
# -----------------------------------------------------------------------------
class LegacyDataProcessor:
    """A class combining various patterns that could be modernized."""

    def __init__(self, config_path: str) -> None:
        self.config = configparser.ConfigParser()
        self.config.read(config_path)
        self.queue: queue.Queue = queue.Queue()
        self.buffer = io.StringIO()

    def load_data(self, url: str) -> str | None:
        """Load data from URL using urllib."""
        try:
            request = Request(url)
            response = urlopen(request)
            data = response.read()

            # Decode bytes to string
            if isinstance(data, bytes):
                data = data.decode('utf-8')

            return data
        except Exception as e:
            print("HTTP Error: %s" % e, file=sys.stderr)  # Old-style formatting
            return None

    def process_items(self, items: dict | list) -> list:
        """Process items using various patterns."""
        results = []

        # Use items for dict
        if hasattr(items, 'items'):
            for key, value in items.items():
                processed = self._transform(key, value)
                results.append(processed)
        else:
            # Handle list
            for i in range(len(items)):  # Could use enumerate
                self.queue.put(items[i])

        # Map/filter operations - could be list comprehensions
        filtered = list(filter(lambda x: x is not None, results))
        transformed = list(map(
            lambda x: x.upper() if isinstance(x, str) else x,
            filtered
        ))

        return transformed

    def _transform(self, key: Any, value: Any) -> Any:
        """Transform a key-value pair."""
        self.buffer.write("Processing: %s = %s\n" % (key, value))  # Old-style

        if isinstance(value, int):
            return value * 2
        elif isinstance(value, str):
            return value.encode('utf-8') if isinstance(value, str) else value
        return value

    def run(self) -> None:
        """Main processing loop."""
        print("Starting LegacyDataProcessor...")

        try:
            for i in range(self.queue.qsize()):
                try:
                    item = self.queue.get(timeout=1)
                    print("Processing item %d: %s" % (i, item))  # Old-style
                except queue.Empty:
                    print("Queue empty, exiting")
                    break
        except KeyboardInterrupt:
            print("Interrupted by user", file=sys.stderr)
        except Exception as e:
            print("Error: %s" % e, file=sys.stderr)  # Old-style
        finally:
            print("Processing complete. Buffer contents:")
            print(self.buffer.getvalue())


# -----------------------------------------------------------------------------
# Main execution block
# -----------------------------------------------------------------------------
if __name__ == '__main__':
    print("=" * 60)
    print("Legacy Patterns Test Script (Python 3 Compatible)")
    print("=" * 60)

    # Test old-style formatting
    print("Testing old-style string formatting...")
    results = format_strings_old_style()
    print(f"  Results: {len(results)} formatted strings")

    # Test dictionary operations
    print("Testing dictionary operations...")
    d = {'a': 1, 'b': 2, 'c': 3}
    result, keys, total = process_dictionary(d)
    print("  Doubled: %s" % result)  # Old-style intentional
    print(f"  Keys: {keys}")  # .format() intentional
    print(f"  Total: {total}")  # Modern f-string

    # Test exception handling
    print("Testing exception handling...")
    exception_handling()

    # Test map/filter
    print("Testing map/filter operations...")
    doubled, evens, total, squares, combined = map_filter_operations()
    print(f"  Even squares: {squares[:5]}...")

    print("=" * 60)
    print("All tests complete!")
    print("=" * 60)
