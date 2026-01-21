"""Pytest configuration and shared fixtures."""

from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def temp_project(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary project directory with basic structure."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()

    # Create a basic pyproject.toml
    pyproject = project_dir / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "test-project"
version = "0.1.0"
dependencies = ["pydantic>=1.10,<2.0"]
"""
    )

    # Create src directory
    src_dir = project_dir / "src"
    src_dir.mkdir()

    yield project_dir


@pytest.fixture
def pydantic_v1_model() -> str:
    """Return a sample Pydantic v1 model for testing."""
    return '''
from pydantic import BaseModel, validator, root_validator, Field
from typing import Optional, List

class User(BaseModel):
    """A user model using Pydantic v1 patterns."""

    id: int
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., regex=r"^[\\w.-]+@[\\w.-]+\\.\\w+$")
    age: Optional[int] = None
    tags: List[str] = []

    class Config:
        orm_mode = True
        validate_assignment = True
        extra = "forbid"

    @validator("name")
    def validate_name(cls, v):
        return v.strip()

    @validator("age")
    def validate_age(cls, v):
        if v is not None and v < 0:
            raise ValueError("Age must be non-negative")
        return v

    @root_validator
    def validate_model(cls, values):
        name = values.get("name")
        email = values.get("email")
        if name and email and name.lower() in email.lower():
            raise ValueError("Name should not be part of email")
        return values

def get_user_dict(user: User) -> dict:
    """Get user as dictionary."""
    return user.dict()

def get_user_schema() -> dict:
    """Get user JSON schema."""
    return User.schema()

def parse_user(data: dict) -> User:
    """Parse user from dictionary."""
    return User.parse_obj(data)
'''


@pytest.fixture
def pydantic_v2_model_expected() -> str:
    """Return the expected Pydantic v2 model after transformation."""
    return '''
from pydantic import BaseModel, field_validator, model_validator, Field, ConfigDict
from typing import Optional, List

class User(BaseModel):
    """A user model using Pydantic v2 patterns."""

    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=True,
        extra="forbid",
    )

    id: int
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., pattern=r"^[\\w.-]+@[\\w.-]+\\.\\w+$")
    age: Optional[int] = None
    tags: List[str] = []

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        return v.strip()

    @field_validator("age")
    @classmethod
    def validate_age(cls, v):
        if v is not None and v < 0:
            raise ValueError("Age must be non-negative")
        return v

    @model_validator(mode="before")
    @classmethod
    def validate_model(cls, values):
        name = values.get("name")
        email = values.get("email")
        if name and email and name.lower() in email.lower():
            raise ValueError("Name should not be part of email")
        return values

def get_user_dict(user: User) -> dict:
    """Get user as dictionary."""
    return user.model_dump()

def get_user_schema() -> dict:
    """Get user JSON schema."""
    return User.model_json_schema()

def parse_user(data: dict) -> User:
    """Parse user from dictionary."""
    return User.model_validate(data)
'''
