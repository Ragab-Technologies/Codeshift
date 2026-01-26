"""Tests for Pydantic v1 to v2 transforms."""

from codeshift.migrator.transforms.pydantic_v1_to_v2 import (
    transform_pydantic_v1_to_v2,
)
from tests.fixtures.pydantic_v1_samples import (
    CONFIG_MULTIPLE_OPTIONS,
    FIELD_WITH_REGEX,
    METHOD_CALLS,
    MODEL_WITH_ROOT_VALIDATOR,
    MODEL_WITH_VALIDATOR,
    MULTIPLE_VALIDATORS,
)


class TestConfigTransform:
    """Tests for Config class to ConfigDict transformation."""

    def test_basic_config_transform(self):
        """Test transforming a basic Config class."""
        code = """
from pydantic import BaseModel

class User(BaseModel):
    name: str

    class Config:
        orm_mode = True
"""
        transformed, changes = transform_pydantic_v1_to_v2(code)

        assert "model_config = ConfigDict" in transformed
        assert "from_attributes=True" in transformed
        assert "class Config:" not in transformed
        assert "ConfigDict" in transformed

    def test_config_multiple_options(self):
        """Test transforming Config with multiple options."""
        transformed, changes = transform_pydantic_v1_to_v2(CONFIG_MULTIPLE_OPTIONS)

        assert "model_config = ConfigDict" in transformed
        assert "from_attributes=True" in transformed
        assert "validate_assignment=True" in transformed
        assert 'extra="forbid"' in transformed
        assert "frozen=True" in transformed  # allow_mutation=False -> frozen=True

    def test_config_imports_configdict(self):
        """Test that ConfigDict is added to imports."""
        code = """
from pydantic import BaseModel

class User(BaseModel):
    class Config:
        orm_mode = True
"""
        transformed, changes = transform_pydantic_v1_to_v2(code)

        assert "ConfigDict" in transformed
        # Should be in the import line
        assert "from pydantic import" in transformed


class TestValidatorTransform:
    """Tests for @validator to @field_validator transformation."""

    def test_validator_transform(self):
        """Test transforming @validator to @field_validator."""
        transformed, changes = transform_pydantic_v1_to_v2(MODEL_WITH_VALIDATOR)

        assert "@field_validator" in transformed
        assert "@validator" not in transformed
        assert "@classmethod" in transformed

    def test_multiple_validators(self):
        """Test transforming multiple validators."""
        transformed, changes = transform_pydantic_v1_to_v2(MULTIPLE_VALIDATORS)

        # Count occurrences
        assert transformed.count("@field_validator") == 3
        assert transformed.count("@classmethod") == 3
        assert "@validator" not in transformed

    def test_validator_import_updated(self):
        """Test that validator import is updated to field_validator."""
        code = """
from pydantic import BaseModel, validator

class User(BaseModel):
    name: str

    @validator("name")
    def validate_name(cls, v):
        return v
"""
        transformed, changes = transform_pydantic_v1_to_v2(code)

        assert "field_validator" in transformed
        # The import line should have field_validator, not validator
        lines = transformed.split("\n")
        import_line = next(line for line in lines if "from pydantic import" in line)
        assert "field_validator" in import_line


class TestValidatorPreArgTransform:
    """Tests for @validator pre argument to mode transformation."""

    def test_validator_pre_true_to_mode_before(self):
        """Test that @validator with pre=True becomes @field_validator with mode='before'."""
        code = """
from pydantic import BaseModel, validator

class User(BaseModel):
    age: int

    @validator("age", pre=True)
    def parse_age(cls, v):
        return int(v)
"""
        transformed, changes = transform_pydantic_v1_to_v2(code)

        assert '@field_validator("age", mode="before")' in transformed
        assert "@classmethod" in transformed
        assert "pre=True" not in transformed
        assert "@validator" not in transformed

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_validator_pre_false_to_mode_after(self):
        """Test that @validator with pre=False becomes @field_validator with mode='after'."""
        code = """
from pydantic import BaseModel, validator

class User(BaseModel):
    name: str

    @validator("name", pre=False)
    def validate_name(cls, v):
        return v.strip()
"""
        transformed, changes = transform_pydantic_v1_to_v2(code)

        assert '@field_validator("name", mode="after")' in transformed
        assert "@classmethod" in transformed
        assert "pre=False" not in transformed
        assert "@validator" not in transformed

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_validator_without_pre_arg(self):
        """Test that @validator without pre argument transforms correctly (no mode added)."""
        code = """
from pydantic import BaseModel, validator

class User(BaseModel):
    name: str

    @validator("name")
    def validate_name(cls, v):
        return v.strip()
"""
        transformed, changes = transform_pydantic_v1_to_v2(code)

        assert '@field_validator("name")' in transformed
        assert "@classmethod" in transformed
        assert "mode=" not in transformed
        assert "@validator" not in transformed

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_validator_with_pre_and_other_args(self):
        """Test that @validator with pre=True and other args preserves other args."""
        code = """
from pydantic import BaseModel, validator

class User(BaseModel):
    name: str

    @validator("name", pre=True, always=True)
    def validate_name(cls, v):
        return str(v).strip()
"""
        transformed, changes = transform_pydantic_v1_to_v2(code)

        assert "@field_validator" in transformed
        assert 'mode="before"' in transformed
        assert "always=True" in transformed
        assert "pre=True" not in transformed
        assert "@classmethod" in transformed

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestRootValidatorTransform:
    """Tests for @root_validator to @model_validator transformation."""

    def test_root_validator_transform(self):
        """Test transforming @root_validator to @model_validator."""
        transformed, changes = transform_pydantic_v1_to_v2(MODEL_WITH_ROOT_VALIDATOR)

        assert "@model_validator" in transformed
        assert "@root_validator" not in transformed
        assert "@classmethod" in transformed
        assert 'mode="before"' in transformed

    def test_root_validator_with_pre_false(self):
        """Test root_validator with pre=False becomes mode='after'."""
        code = """
from pydantic import BaseModel, root_validator

class User(BaseModel):
    name: str

    @root_validator(pre=False)
    def validate_model(cls, values):
        return values
"""
        transformed, changes = transform_pydantic_v1_to_v2(code)

        assert "@model_validator" in transformed
        assert 'mode="after"' in transformed


class TestMethodCallTransforms:
    """Tests for method call transformations."""

    def test_dict_to_model_dump(self):
        """Test .dict() to .model_dump() transformation."""
        transformed, changes = transform_pydantic_v1_to_v2(METHOD_CALLS)

        assert ".model_dump()" in transformed
        assert ".dict()" not in transformed

    def test_json_to_model_dump_json(self):
        """Test .json() to .model_dump_json() transformation."""
        transformed, changes = transform_pydantic_v1_to_v2(METHOD_CALLS)

        assert ".model_dump_json()" in transformed
        assert ".json()" not in transformed or ".model_dump_json()" in transformed

    def test_schema_to_model_json_schema(self):
        """Test .schema() to .model_json_schema() transformation."""
        transformed, changes = transform_pydantic_v1_to_v2(METHOD_CALLS)

        assert ".model_json_schema()" in transformed

    def test_parse_obj_to_model_validate(self):
        """Test .parse_obj() to .model_validate() transformation."""
        transformed, changes = transform_pydantic_v1_to_v2(METHOD_CALLS)

        assert ".model_validate(" in transformed
        assert ".parse_obj(" not in transformed


class TestFieldTransforms:
    """Tests for Field parameter transformations."""

    def test_field_regex_to_pattern(self):
        """Test Field(regex=...) to Field(pattern=...) transformation."""
        transformed, changes = transform_pydantic_v1_to_v2(FIELD_WITH_REGEX)

        assert "pattern=" in transformed
        assert "regex=" not in transformed

    def test_field_min_max_items(self):
        """Test min_items/max_items to min_length/max_length."""
        code = """
from pydantic import BaseModel, Field
from typing import List

class User(BaseModel):
    tags: List[str] = Field(min_items=1, max_items=10)
"""
        transformed, changes = transform_pydantic_v1_to_v2(code)

        assert "min_length=1" in transformed
        assert "max_length=10" in transformed
        assert "min_items" not in transformed
        assert "max_items" not in transformed


class TestAttributeTransforms:
    """Tests for attribute access transformations."""

    def test_dunder_fields(self):
        """Test __fields__ to model_fields transformation."""
        code = """
from pydantic import BaseModel

class User(BaseModel):
    name: str

fields = User.__fields__
"""
        transformed, changes = transform_pydantic_v1_to_v2(code)

        assert "model_fields" in transformed
        assert "__fields__" not in transformed


class TestComplexTransforms:
    """Tests for complex code with multiple transformations."""

    def test_full_model_transformation(self, pydantic_v1_model):
        """Test transforming a complete Pydantic v1 model."""
        transformed, changes = transform_pydantic_v1_to_v2(pydantic_v1_model)

        # Check all major transformations
        assert "ConfigDict" in transformed
        assert "from_attributes=True" in transformed
        assert "@field_validator" in transformed
        assert "@model_validator" in transformed
        assert ".model_dump()" in transformed
        assert ".model_json_schema()" in transformed
        assert ".model_validate(" in transformed
        assert "pattern=" in transformed

        # Check old patterns are gone
        assert "class Config:" not in transformed
        assert "@validator" not in transformed or "@field_validator" in transformed
        assert "@root_validator" not in transformed
        assert "orm_mode" not in transformed

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_preserves_comments_and_docstrings(self):
        """Test that comments and docstrings are preserved."""
        code = '''
from pydantic import BaseModel

class User(BaseModel):
    """A user model."""
    name: str  # The user's name

    class Config:
        """Configuration."""
        orm_mode = True
'''
        transformed, changes = transform_pydantic_v1_to_v2(code)

        assert '"""A user model."""' in transformed
        assert "# The user's name" in transformed

    def test_change_tracking(self):
        """Test that changes are properly tracked."""
        code = """
from pydantic import BaseModel, validator

class User(BaseModel):
    name: str

    class Config:
        orm_mode = True

    @validator("name")
    def validate_name(cls, v):
        return v
"""
        transformed, changes = transform_pydantic_v1_to_v2(code)

        # Should have multiple changes tracked
        assert len(changes) > 0

        # Check that change descriptions are meaningful
        descriptions = [c.description for c in changes]
        assert any("Config" in d or "ConfigDict" in d for d in descriptions)
        assert any("validator" in d.lower() for d in descriptions)
