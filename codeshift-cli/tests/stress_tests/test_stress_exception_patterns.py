"""
Stress test for Codeshift LLM migration tool.

This file contains VERY complex exception handling patterns combined with
usage of multiple libraries that need migration. It tests the tool's ability
to handle:

- Bare except clauses
- Exception chaining (from cause)
- ExceptionGroup (Python 3.11+)
- except* syntax (Python 3.11+)
- Context managers for cleanup
- try/finally patterns
- Nested try/except
- Re-raising exceptions
- Custom exception hierarchies
- __cause__ and __context__
- traceback module usage
- sys.exc_info() patterns
- warnings module patterns

PLUS library patterns that need migration:
- Pydantic v1 patterns (to test v1 -> v2 migration)
- SQLAlchemy 1.4 patterns (to test v1.4 -> v2.0 migration)
- Requests patterns (to test v2.x -> v2.32 migration)
- FastAPI patterns (to test v0.x -> v1.0 migration)
"""

from __future__ import annotations

import builtins
import logging
import sys
import traceback
import warnings
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import wraps
from typing import TYPE_CHECKING, Any, NoReturn, TypeVar

# Requests imports
import requests

# FastAPI imports
from fastapi import FastAPI, HTTPException, Query
from fastapi.security import OAuth2PasswordBearer

# Pydantic v1 imports (these should be migrated to v2 style)
from pydantic import BaseModel, Field, root_validator, validator
from pydantic import ValidationError as PydanticValidationError
from requests.exceptions import ConnectionError as ReqConnectionError

# SQLAlchemy 1.4 style imports (these should be migrated to v2 style)
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship, sessionmaker

if TYPE_CHECKING:
    from types import TracebackType

# Configure logging
logger = logging.getLogger(__name__)

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


# =============================================================================
# PYDANTIC V1 MODELS (Should be migrated to v2)
# =============================================================================

# SQLAlchemy Base (v1.4 style - should be migrated)
Base = declarative_base()


class LegacyUserModel(BaseModel):
    """Pydantic v1 model with legacy validators."""

    id: int
    name: str
    email: str
    age: int | None = None

    # v1 style validator - should be migrated to field_validator
    @validator("email")
    def validate_email(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError("Invalid email address")
        return v.lower()

    # v1 style validator with pre=True
    @validator("name", pre=True)
    def strip_name(cls, v: Any) -> str:
        if isinstance(v, str):
            return v.strip()
        return str(v)

    # v1 style root_validator - should be migrated to model_validator
    @root_validator
    def check_age_for_email(cls, values: builtins.dict[str, Any]) -> builtins.dict[str, Any]:
        age = values.get("age")
        email = values.get("email", "")
        if age and age < 13 and "kids" not in email:
            raise ValueError("Users under 13 must use a kids email domain")
        return values

    class Config:
        # v1 style Config class - should be migrated to model_config
        orm_mode = True
        validate_assignment = True
        extra = "forbid"

    def dict(self, **kwargs: Any) -> builtins.dict[str, Any]:
        """v1 style .dict() method - should use .model_dump() in v2."""
        return super().dict(**kwargs)


class LegacyConfigModel(BaseModel):
    """Another Pydantic v1 model for configuration."""

    debug: bool = False
    max_connections: int = Field(default=10, ge=1, le=100)
    timeout_seconds: float = Field(default=30.0, gt=0)
    allowed_hosts: list[str] = []

    @validator("allowed_hosts", each_item=True)
    def validate_host(cls, v: str) -> str:
        if not v or v.startswith("."):
            raise ValueError(f"Invalid host: {v}")
        return v.lower()

    class Config:
        # v1 Config - should migrate
        schema_extra = {
            "example": {
                "debug": False,
                "max_connections": 50,
            }
        }


# =============================================================================
# SQLALCHEMY 1.4 MODELS (Should be migrated to v2)
# =============================================================================


class User(Base):
    """SQLAlchemy 1.4 style model."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(200), unique=True)

    # 1.4 style relationship
    posts = relationship("Post", back_populates="author")


class Post(Base):
    """SQLAlchemy 1.4 style model with foreign key."""

    __tablename__ = "posts"

    id = Column(Integer, primary_key=True)
    title = Column(String(200))
    user_id = Column(Integer, ForeignKey("users.id"))

    # 1.4 style relationship
    author = relationship("User", back_populates="posts")


# =============================================================================
# CUSTOM EXCEPTION HIERARCHIES
# =============================================================================


class CodeshiftBaseError(Exception):
    """Base exception for all Codeshift errors."""

    def __init__(self, message: str, code: int = 0, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}
        self.timestamp = __import__("datetime").datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for logging/serialization."""
        return {
            "type": self.__class__.__name__,
            "message": str(self),
            "code": self.code,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }


class ValidationError(CodeshiftBaseError):
    """Raised when validation fails."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.field = field
        self.value = value


class NetworkError(CodeshiftBaseError):
    """Raised for network-related failures."""

    def __init__(
        self,
        message: str,
        url: str | None = None,
        status_code: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.url = url
        self.status_code = status_code


class DatabaseError(CodeshiftBaseError):
    """Raised for database-related failures."""

    pass


class RetryableError(CodeshiftBaseError):
    """Marks errors that can be retried."""

    max_retries: int = 3
    retry_delay: float = 1.0


class MultiError(CodeshiftBaseError):
    """Holds multiple exceptions."""

    def __init__(self, errors: list[Exception], **kwargs: Any) -> None:
        message = f"Multiple errors occurred: {len(errors)} errors"
        super().__init__(message, **kwargs)
        self.errors = errors


# =============================================================================
# FASTAPI APPLICATION WITH EXCEPTION HANDLING
# =============================================================================

app = FastAPI(title="Stress Test API")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


@app.get("/users/{user_id}")
async def get_user(
    user_id: int,
    include_posts: bool = Query(default=False),  # FastAPI v0.x style
) -> dict[str, Any]:
    """Get user with complex exception handling."""
    try:
        try:
            # Nested try for database operations
            user_data = await fetch_user_from_db(user_id)
        except DatabaseError as db_err:
            raise HTTPException(status_code=500, detail="Database error") from db_err
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.exception("Unexpected error fetching user")
        raise HTTPException(status_code=500, detail=str(e)) from e

    return {"user": user_data}


@app.post("/users/")
async def create_user(user: LegacyUserModel) -> dict[str, Any]:
    """Create user using Pydantic v1 model."""
    try:
        # Use v1 .dict() method - should be .model_dump() in v2
        user_dict = user.dict(exclude_unset=True)
        return {"created": user_dict}
    except PydanticValidationError as e:
        # Handle Pydantic validation errors
        raise HTTPException(status_code=422, detail=e.errors())


# =============================================================================
# BARE EXCEPT CLAUSES (Legacy pattern - should be modernized)
# =============================================================================


def dangerous_bare_except_v1(data: Any) -> str:
    """Uses bare except - bad practice."""
    try:
        result = str(data.process())
        return result
    except:  # noqa: E722 - Intentionally bare except for testing
        return "error occurred"


def dangerous_bare_except_v2(items: list[Any]) -> list[str]:
    """Nested bare excepts - very bad practice."""
    results = []
    for item in items:
        try:
            try:
                results.append(str(item.transform()))
            except:  # noqa: E722
                results.append(str(item))
        except:  # noqa: E722
            results.append("failed")
    return results


def bare_except_with_logging() -> None:
    """Bare except with logging - common legacy pattern."""
    try:
        risky_operation()
    except:  # noqa: E722
        import traceback

        traceback.print_exc()
        logger.error("Operation failed")


# =============================================================================
# EXCEPTION CHAINING WITH DATABASE AND API CALLS
# =============================================================================


def exception_chaining_with_requests(url: str) -> dict[str, Any]:
    """Exception chaining with requests library."""
    try:
        # Requests call that might fail
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    except ReqConnectionError as e:
        raise NetworkError(f"Connection failed to {url}", url=url) from e
    except requests.Timeout as e:
        raise NetworkError(f"Request timed out: {url}", url=url) from e
    except requests.HTTPError as e:
        raise NetworkError(
            f"HTTP error: {e.response.status_code}",
            url=url,
            status_code=e.response.status_code,
        ) from e


def exception_chaining_with_sqlalchemy(session: Session, user_id: int) -> User:
    """Exception chaining with SQLAlchemy operations."""
    try:
        # SQLAlchemy 1.4 style query - should be migrated to v2 select() style
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValidationError(f"User {user_id} not found")
        return user
    except ValidationError:
        raise  # Re-raise our custom errors
    except Exception as e:
        raise DatabaseError(f"Database query failed for user {user_id}") from e


def exception_chaining_with_pydantic(data: dict[str, Any]) -> LegacyUserModel:
    """Exception chaining with Pydantic validation."""
    try:
        # v1 style - using parse_obj (should be model_validate in v2)
        return LegacyUserModel.parse_obj(data)
    except PydanticValidationError as e:
        raise ValidationError(f"Invalid user data: {e}") from e


# =============================================================================
# EXCEPTION GROUPS (Python 3.11+)
# =============================================================================


def exception_group_basic(tasks: list[Callable[[], Any]]) -> list[Any]:
    """Basic ExceptionGroup usage."""
    results = []
    errors = []

    for task in tasks:
        try:
            results.append(task())
        except Exception as e:
            errors.append(e)

    if errors:
        raise ExceptionGroup("Multiple task failures", errors)

    return results


def exception_group_with_validation(users: list[dict[str, Any]]) -> list[LegacyUserModel]:
    """ExceptionGroup with Pydantic validation."""
    results = []
    errors: list[Exception] = []

    for user_data in users:
        try:
            # v1 style parse_obj
            user = LegacyUserModel.parse_obj(user_data)
            results.append(user)
        except PydanticValidationError as e:
            errors.append(e)

    if errors:
        raise ExceptionGroup("Multiple validation failures", errors)

    return results


def handle_exception_group_with_except_star() -> None:
    """Using except* syntax (Python 3.11+)."""
    try:
        exception_group_basic([
            lambda: 1 / 0,  # ZeroDivisionError
            lambda: int("not a number"),  # ValueError
            lambda: LegacyUserModel.parse_obj({}),  # ValidationError
        ])
    except* PydanticValidationError as eg:
        logger.error(f"Pydantic errors: {eg.exceptions}")
    except* ValueError as eg:
        logger.error(f"Value errors: {eg.exceptions}")
    except* ZeroDivisionError as eg:
        logger.error(f"Math errors: {eg.exceptions}")


# =============================================================================
# CONTEXT MANAGERS FOR CLEANUP WITH DATABASE
# =============================================================================


class DatabaseSessionManager:
    """Database session manager with complex exception handling."""

    def __init__(self, engine: Any) -> None:
        self.engine = engine
        self.session: Session | None = None
        self._cleanup_handlers: list[Callable[[], None]] = []

    def __enter__(self) -> Session:
        # SQLAlchemy 1.4 style session creation
        SessionLocal = sessionmaker(bind=self.engine)
        self.session = SessionLocal()
        return self.session

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        """Handle cleanup with potential exception suppression."""
        cleanup_errors = []

        for handler in reversed(self._cleanup_handlers):
            try:
                handler()
            except Exception as e:
                cleanup_errors.append(e)

        if self.session:
            try:
                if exc_val:
                    self.session.rollback()
                else:
                    self.session.commit()
            except Exception as e:
                cleanup_errors.append(e)
            finally:
                self.session.close()

        if cleanup_errors:
            if exc_val:
                raise ExceptionGroup(
                    "Cleanup failed with pending exception",
                    [exc_val, *cleanup_errors],
                )
            else:
                raise ExceptionGroup("Cleanup failed", cleanup_errors)

        return False


@contextmanager
def api_request_context(
    base_url: str,
    timeout: float = 30.0,
) -> Generator[requests.Session, None, None]:
    """Context manager for API requests with exception handling."""
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})

    try:
        yield session
    except ReqConnectionError as e:
        raise NetworkError(f"Connection failed to {base_url}") from e
    except requests.Timeout as e:
        raise NetworkError(f"Request timed out after {timeout}s") from e
    finally:
        session.close()


# =============================================================================
# TRY/FINALLY PATTERNS WITH PYDANTIC
# =============================================================================


def try_finally_with_pydantic_validation(data: dict[str, Any]) -> LegacyUserModel:
    """Try/finally with Pydantic validation."""
    original_data = data.copy()
    try:
        # v1 style construct (should be model_construct in v2)
        return LegacyUserModel.construct(**data)
    finally:
        logger.debug(f"Attempted to construct from: {original_data}")


def try_finally_with_database(session: Session, user_data: dict[str, Any]) -> User:
    """Try/finally with database operations."""
    user = None
    try:
        user = User(**user_data)
        session.add(user)
        session.flush()
        return user
    finally:
        if user and user.id:
            logger.info(f"User operation completed for ID: {user.id}")


# =============================================================================
# NESTED TRY/EXCEPT WITH MULTIPLE LIBRARIES
# =============================================================================


def deeply_nested_with_libraries(
    url: str,
    session: Session,
    user_data: dict[str, Any],
) -> dict[str, Any]:
    """Deeply nested exception handling with multiple libraries."""
    result: dict[str, Any] = {}

    try:
        try:
            # Outer try: API request
            api_response = requests.get(url, timeout=10)
            api_response.raise_for_status()
            result["api_data"] = api_response.json()

            try:
                # Middle try: Pydantic validation
                user = LegacyUserModel.parse_obj(user_data)
                result["user"] = user.dict()  # v1 style

                try:
                    # Inner try: Database operation
                    db_user = session.query(User).filter(
                        User.email == user.email
                    ).first()
                    if db_user:
                        result["existing"] = True
                except Exception as db_err:
                    result["db_error"] = str(db_err)

            except PydanticValidationError as val_err:
                result["validation_error"] = str(val_err)

        except requests.RequestException as req_err:
            result["api_error"] = str(req_err)

    except BaseException as e:
        result["fatal_error"] = str(e)

    return result


# =============================================================================
# RE-RAISING EXCEPTIONS WITH PYDANTIC AND SQLALCHEMY
# =============================================================================


def reraise_with_pydantic_context() -> None:
    """Re-raise with Pydantic validation context."""
    try:
        # v1 style parse_raw (deprecated in v2)
        LegacyUserModel.parse_raw('{"invalid": json}')
    except Exception:
        logger.exception("Pydantic parse failed, re-raising")
        raise


def reraise_with_sqlalchemy_context(session: Session) -> None:
    """Re-raise with SQLAlchemy context."""
    try:
        # SQLAlchemy 1.4 style execute
        session.execute("SELECT * FROM nonexistent_table")
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise DatabaseError("Query execution failed") from e


# =============================================================================
# __cause__ AND __context__ WITH LIBRARY ERRORS
# =============================================================================


def examine_pydantic_exception_chain() -> list[dict[str, Any]]:
    """Examine exception chain from Pydantic errors."""
    try:
        LegacyUserModel.parse_obj({"email": "invalid"})
    except PydanticValidationError as e:
        chain = []
        current: BaseException | None = e

        while current is not None:
            info = {
                "type": type(current).__name__,
                "message": str(current),
                "has_cause": current.__cause__ is not None,
                "has_context": current.__context__ is not None,
            }
            chain.append(info)
            current = current.__cause__ or current.__context__

        return chain

    return []


# =============================================================================
# TRACEBACK MODULE USAGE WITH API ERRORS
# =============================================================================


def capture_api_traceback(url: str) -> str:
    """Capture traceback from API errors."""
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
    except Exception:
        return traceback.format_exc()
    return ""


def extract_validation_traceback(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract traceback from validation errors."""
    try:
        LegacyUserModel.parse_obj(data)
    except PydanticValidationError:
        exc_type, exc_value, exc_tb = sys.exc_info()
        frames = []

        for frame_info in traceback.extract_tb(exc_tb):
            frames.append({
                "filename": frame_info.filename,
                "lineno": frame_info.lineno,
                "name": frame_info.name,
                "line": frame_info.line,
            })

        return frames
    return []


# =============================================================================
# sys.exc_info() PATTERNS WITH LIBRARIES
# =============================================================================


def exc_info_with_database(session: Session) -> tuple[type | None, BaseException | None, Any]:
    """sys.exc_info() with database operations."""
    try:
        session.query(User).filter(User.id == -1).one()
    except Exception:
        return sys.exc_info()
    return (None, None, None)


def exc_info_reraise_with_context(session: Session) -> NoReturn:
    """Re-raise using exc_info with database context."""
    try:
        session.execute("INVALID SQL SYNTAX")
    except Exception:
        exc_info = sys.exc_info()
        new_exc = DatabaseError("SQL execution failed")
        new_exc.__cause__ = exc_info[1]
        raise new_exc


# =============================================================================
# WARNINGS MODULE PATTERNS WITH DEPRECATIONS
# =============================================================================


def emit_pydantic_deprecation_warning() -> None:
    """Emit warning about Pydantic v1 usage."""
    warnings.warn(
        "Using Pydantic v1 patterns. Please migrate to v2 using .model_dump() instead of .dict()",
        DeprecationWarning,
        stacklevel=2,
    )


def emit_sqlalchemy_deprecation_warning() -> None:
    """Emit warning about SQLAlchemy 1.4 usage."""
    warnings.warn(
        "Using SQLAlchemy 1.4 patterns. Please migrate to v2 using select() instead of query()",
        DeprecationWarning,
        stacklevel=2,
    )


def catch_library_warnings() -> None:
    """Catch warnings from library usage."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        try:
            emit_pydantic_deprecation_warning()
        except DeprecationWarning as e:
            logger.warning(f"Deprecation caught: {e}")


# =============================================================================
# DECORATOR PATTERNS FOR EXCEPTION HANDLING
# =============================================================================


def retry_on_network_error(
    max_retries: int = 3,
    delay: float = 1.0,
) -> Callable[[F], F]:
    """Decorator that retries on network errors."""

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (ReqConnectionError, requests.Timeout, NetworkError) as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        import time

                        time.sleep(delay * (attempt + 1))
                    continue

            raise RetryableError(
                f"All {max_retries} retries failed"
            ) from last_exception

        return wrapper  # type: ignore

    return decorator


def validate_with_pydantic(model: type[BaseModel]) -> Callable[[F], F]:
    """Decorator that validates input with Pydantic."""

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if args:
                try:
                    # v1 style validation
                    validated = model.parse_obj(args[0])
                    args = (validated,) + args[1:]
                except PydanticValidationError as e:
                    raise ValidationError(f"Input validation failed: {e}") from e
            return func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator


# =============================================================================
# HELPER FUNCTIONS (Stubs for testing)
# =============================================================================


def risky_operation() -> Any:
    """Placeholder for risky operation."""
    raise ValueError("Simulated error")


async def fetch_user_from_db(user_id: int) -> dict[str, Any]:
    """Placeholder for async database fetch."""
    if user_id < 0:
        raise DatabaseError(f"Invalid user ID: {user_id}")
    return {"id": user_id, "name": "Test User"}


# =============================================================================
# DATACLASS WITH EXCEPTION HANDLING
# =============================================================================


@dataclass
class ErrorReport:
    """Error report dataclass."""

    error_type: str
    message: str
    traceback_str: str
    context: dict[str, Any]

    @classmethod
    def from_exception(cls, exc: Exception) -> ErrorReport:
        """Create ErrorReport from exception."""
        return cls(
            error_type=type(exc).__name__,
            message=str(exc),
            traceback_str=traceback.format_exc(),
            context={
                "cause": str(exc.__cause__) if exc.__cause__ else None,
                "context": str(exc.__context__) if exc.__context__ else None,
            },
        )

    @classmethod
    def from_pydantic_error(cls, exc: PydanticValidationError) -> ErrorReport:
        """Create ErrorReport from Pydantic validation error."""
        return cls(
            error_type="PydanticValidationError",
            message=str(exc),
            traceback_str=traceback.format_exc(),
            context={
                # v1 style errors() method
                "errors": exc.errors(),
            },
        )


# =============================================================================
# MAIN EXECUTION
# =============================================================================


def main() -> None:
    """Main function demonstrating various exception patterns."""
    print("Testing exception patterns with library migrations...")

    # Test Pydantic v1 patterns
    try:
        user = LegacyUserModel(id=1, name="  Test  ", email="TEST@EXAMPLE.COM", age=25)
        print(f"User: {user.dict()}")  # v1 style
    except PydanticValidationError as e:
        print(f"Validation error: {e}")

    # Test exception groups
    try:
        exception_group_with_validation([
            {"id": 1, "name": "Valid", "email": "valid@test.com"},
            {"id": "invalid"},  # Will fail
            {},  # Will fail
        ])
    except ExceptionGroup as eg:
        print(f"ExceptionGroup with {len(eg.exceptions)} errors")

    # Test custom exception hierarchy
    try:
        raise ValidationError("Test error", field="test", code=400)
    except CodeshiftBaseError as e:
        print(f"Custom error: {e.to_dict()}")

    print("All tests completed!")


if __name__ == "__main__":
    main()
