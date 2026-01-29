"""Request and response models for code migration endpoints."""

import logging
import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

# Semver pattern: major.minor.patch with optional pre-release and build metadata
SEMVER_PATTERN = re.compile(
    r"^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(-((0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(\.(0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(\+([0-9a-zA-Z-]+(\.[0-9a-zA-Z-]+)*))?$"
)

# Library name pattern: starts with letter, followed by alphanumeric, underscore, hyphen, or dot
LIBRARY_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_\-\.]*$")

# Maximum combined size for code + context (600KB)
MAX_COMBINED_SIZE_BYTES = 600 * 1024

# Known libraries that are commonly migrated
KNOWN_LIBRARIES: frozenset[str] = frozenset(
    {
        # Web frameworks
        "django",
        "flask",
        "fastapi",
        "starlette",
        "tornado",
        "aiohttp",
        "sanic",
        "bottle",
        "pyramid",
        "falcon",
        # Data processing
        "pandas",
        "numpy",
        "scipy",
        "polars",
        "dask",
        "vaex",
        # Machine learning
        "scikit-learn",
        "sklearn",
        "tensorflow",
        "torch",
        "pytorch",
        "keras",
        "xgboost",
        "lightgbm",
        "transformers",
        # Database
        "sqlalchemy",
        "alembic",
        "pymongo",
        "redis",
        "psycopg2",
        "asyncpg",
        "aiosqlite",
        "motor",
        # HTTP/API clients
        "requests",
        "httpx",
        "urllib3",
        "aiohttp",
        "httplib2",
        # Testing
        "pytest",
        "unittest",
        "nose",
        "mock",
        "hypothesis",
        "factory_boy",
        "faker",
        # CLI/Config
        "click",
        "typer",
        "argparse",
        "pydantic",
        "pydantic-settings",
        "dynaconf",
        "python-dotenv",
        # Async
        "celery",
        "dramatiq",
        "rq",
        "asyncio",
        "trio",
        "anyio",
        # Serialization
        "marshmallow",
        "attrs",
        "cattrs",
        "orjson",
        "ujson",
        # Cloud/Infrastructure
        "boto3",
        "google-cloud-storage",
        "azure-storage-blob",
        # Logging/Monitoring
        "structlog",
        "loguru",
        "sentry-sdk",
        "opentelemetry",
        # Misc
        "pillow",
        "beautifulsoup4",
        "lxml",
        "jinja2",
        "cryptography",
        "pyjwt",
        "python-dateutil",
        "arrow",
        "pendulum",
    }
)


class MigrateCodeRequest(BaseModel):
    """Request model for code migration endpoint."""

    code: str = Field(
        ...,
        max_length=500000,
        description="Source code to migrate",
    )
    library: str = Field(
        ...,
        max_length=100,
        pattern=r"^[a-zA-Z][a-zA-Z0-9_\-\.]*$",
        description="Library being upgraded (e.g., 'django', 'pandas')",
    )
    from_version: str = Field(
        ...,
        max_length=50,
        description="Current version of the library (semver format)",
    )
    to_version: str = Field(
        ...,
        max_length=50,
        description="Target version of the library (semver format)",
    )
    context: Optional[str] = Field(
        default=None,
        max_length=10000,
        description="Additional context about the codebase or migration requirements",
    )

    @field_validator("from_version", "to_version")
    @classmethod
    def validate_semver(cls, v: str) -> str:
        """Validate that version strings follow semver format."""
        if not SEMVER_PATTERN.match(v):
            raise ValueError(
                f"Invalid version format: '{v}'. Expected semver format (e.g., '1.0.0', '2.1.0-beta.1')"
            )
        return v

    @field_validator("library")
    @classmethod
    def validate_library(cls, v: str) -> str:
        """Validate library name and warn if unknown."""
        # Normalize to lowercase for comparison
        normalized = v.lower()
        if normalized not in KNOWN_LIBRARIES:
            logger.warning(
                "Unknown library '%s' requested for migration. "
                "This may be a valid library not in our known list, "
                "or a potential typo.",
                v,
            )
        return v

    @model_validator(mode="after")
    def validate_combined_size(self) -> "MigrateCodeRequest":
        """Ensure combined size of code and context doesn't exceed 600KB."""
        code_size = len(self.code.encode("utf-8"))
        context_size = len(self.context.encode("utf-8")) if self.context else 0
        combined_size = code_size + context_size

        if combined_size > MAX_COMBINED_SIZE_BYTES:
            raise ValueError(
                f"Combined size of code and context ({combined_size:,} bytes) "
                f"exceeds maximum allowed size ({MAX_COMBINED_SIZE_BYTES:,} bytes / 600KB)"
            )
        return self


class MigrateCodeResponse(BaseModel):
    """Response model for code migration endpoint."""

    request_id: str = Field(
        ...,
        description="Unique request ID for tracking this migration",
    )
    migrated_code: str = Field(
        ...,
        description="Migrated source code",
    )
    changes_made: list[str] = Field(
        default_factory=list,
        description="List of changes applied during migration",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Warnings or notes about the migration",
    )
