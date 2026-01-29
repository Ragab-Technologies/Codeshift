"""Tests for Pydantic v1 to v2 type inference to prevent false positives."""

from codeshift.migrator.transforms.pydantic_v1_to_v2 import (
    transform_pydantic_v1_to_v2,
)


class TestTypeInferenceFalsePositives:
    """Tests to ensure we don't transform non-Pydantic objects."""

    def test_requests_response_json_not_transformed(self):
        """Test that response.json() on requests.Response is NOT transformed."""
        code = """
import requests
from pydantic import BaseModel

class User(BaseModel):
    name: str

# This should NOT be transformed - it's a requests.Response
response = requests.get("https://api.example.com")
data = response.json()

# This SHOULD be transformed - it's a Pydantic model instance
user = User(name="test")
user_data = user.json()
"""
        transformed, changes = transform_pydantic_v1_to_v2(code)

        # response.json() should NOT be transformed
        assert (
            "response.json()" in transformed
        ), "requests.Response.json() should NOT be transformed"

        # user.json() SHOULD be transformed
        assert (
            "user.model_dump_json()" in transformed
        ), "Pydantic model .json() should be transformed"

    def test_dict_copy_not_transformed(self):
        """Test that dict.copy() is NOT transformed."""
        code = """
from pydantic import BaseModel

class User(BaseModel):
    name: str

# This should NOT be transformed - it's a plain dict
data = {"name": "test"}
data_copy = data.copy()

# This SHOULD be transformed - it's a Pydantic model instance
user = User(name="test")
user_copy = user.copy()
"""
        transformed, changes = transform_pydantic_v1_to_v2(code)

        # data.copy() should NOT be transformed
        assert "data.copy()" in transformed, "dict.copy() should NOT be transformed"

        # user.copy() SHOULD be transformed
        assert "user.model_copy()" in transformed, "Pydantic model .copy() should be transformed"

    def test_arbitrary_object_methods_not_transformed(self):
        """Test that methods on arbitrary objects are NOT transformed."""
        code = """
from pydantic import BaseModel

class User(BaseModel):
    name: str

# These should NOT be transformed - unknown objects
some_obj = get_some_object()
result1 = some_obj.json()
result2 = some_obj.dict()
result3 = some_obj.copy()
"""
        transformed, changes = transform_pydantic_v1_to_v2(code)

        # All these should remain unchanged
        assert "some_obj.json()" in transformed
        assert "some_obj.dict()" in transformed
        assert "some_obj.copy()" in transformed

    def test_pydantic_instance_from_function_param(self):
        """Test that function parameters with Pydantic type hints are recognized."""
        code = """
from pydantic import BaseModel

class User(BaseModel):
    name: str

def process_user(user: User) -> dict:
    return user.dict()

def process_response(response) -> dict:
    # This should NOT be transformed - no type hint
    return response.json()
"""
        transformed, changes = transform_pydantic_v1_to_v2(code)

        # user.dict() should be transformed (has User type hint)
        assert "user.model_dump()" in transformed

        # response.json() should NOT be transformed (no type hint, unknown type)
        assert "response.json()" in transformed

    def test_direct_model_instantiation_then_method(self):
        """Test that Model(...).json() is properly transformed."""
        code = """
from pydantic import BaseModel

class User(BaseModel):
    name: str

# Direct instantiation and method call
data = User(name="test").json()
"""
        transformed, changes = transform_pydantic_v1_to_v2(code)

        # Should be transformed
        assert 'User(name="test").model_dump_json()' in transformed

    def test_class_methods_still_transformed(self):
        """Test that class methods like parse_obj, schema are still transformed."""
        code = """
from pydantic import BaseModel

class User(BaseModel):
    name: str

# Class methods should be transformed
data = User.parse_obj({"name": "test"})
schema = User.schema()
"""
        transformed, changes = transform_pydantic_v1_to_v2(code)

        # Class methods should be transformed
        assert "User.model_validate(" in transformed
        assert "User.model_json_schema()" in transformed

    def test_fields_only_on_pydantic_classes(self):
        """Test that __fields__ is only transformed on Pydantic model classes."""
        code = """
from pydantic import BaseModel

class User(BaseModel):
    name: str

# Should be transformed - known Pydantic class
fields = User.__fields__

# Should NOT be transformed - unknown object
class SomeOtherClass:
    __fields__ = {}

other_fields = SomeOtherClass.__fields__
"""
        transformed, changes = transform_pydantic_v1_to_v2(code)

        # User.__fields__ should be transformed
        assert "User.model_fields" in transformed

        # SomeOtherClass.__fields__ should NOT be transformed
        assert "SomeOtherClass.__fields__" in transformed

    def test_variable_name_heuristic(self):
        """Test that variable names matching model class names are recognized."""
        code = """
from pydantic import BaseModel

class UserModel(BaseModel):
    name: str

# Variable name matches class name (lowercase) - should be transformed
usermodel = get_user()
data = usermodel.dict()
"""
        transformed, changes = transform_pydantic_v1_to_v2(code)

        # usermodel.dict() should be transformed (name matches UserModel)
        assert "usermodel.model_dump()" in transformed

    def test_mixed_pydantic_and_requests(self):
        """Test a realistic scenario with both Pydantic and requests usage."""
        code = """
import requests
from pydantic import BaseModel

class ApiResponse(BaseModel):
    status: str
    data: dict

def fetch_and_parse(url: str) -> ApiResponse:
    # requests.Response - should NOT be transformed
    response = requests.get(url)
    raw_data = response.json()

    # Pydantic model - should be transformed
    parsed = ApiResponse.parse_obj(raw_data)
    return parsed

def serialize_response(resp: ApiResponse) -> str:
    # Should be transformed - has ApiResponse type hint
    return resp.json()
"""
        transformed, changes = transform_pydantic_v1_to_v2(code)

        # requests.Response.json() should NOT be transformed
        assert "response.json()" in transformed

        # ApiResponse.parse_obj() should be transformed
        assert "ApiResponse.model_validate(" in transformed

        # resp.json() should be transformed (has ApiResponse type hint)
        assert "resp.model_dump_json()" in transformed

    def test_inherited_models(self):
        """Test that models inheriting from other Pydantic models are recognized."""
        code = """
from pydantic import BaseModel

class BaseUser(BaseModel):
    name: str

class AdminUser(BaseUser):
    admin_level: int

admin = AdminUser(name="test", admin_level=1)
data = admin.dict()
"""
        transformed, changes = transform_pydantic_v1_to_v2(code)

        # admin.dict() should be transformed - AdminUser inherits from BaseUser
        assert "admin.model_dump()" in transformed
