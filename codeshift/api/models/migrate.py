"""Migration models for the PyResolve API."""

from typing import Any

from pydantic import BaseModel, Field


class MigrateCodeRequest(BaseModel):
    """Request to migrate code using LLM."""

    code: str = Field(..., description="Source code to migrate")
    library: str = Field(..., description="Library being upgraded (e.g., 'pydantic')")
    from_version: str = Field(..., description="Current version (e.g., '1.10.0')")
    to_version: str = Field(..., description="Target version (e.g., '2.5.0')")
    context: str | None = Field(None, description="Optional context about the migration")


class MigrateCodeResponse(BaseModel):
    """Response from LLM migration."""

    success: bool
    migrated_code: str
    original_code: str
    error: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
    cached: bool = False


class ExplainChangeRequest(BaseModel):
    """Request to explain a migration change."""

    original_code: str = Field(..., description="Original code before migration")
    transformed_code: str = Field(..., description="Transformed code after migration")
    library: str = Field(..., description="Library being upgraded")


class ExplainChangeResponse(BaseModel):
    """Response with explanation of changes."""

    success: bool
    explanation: str | None = None
    error: str | None = None
