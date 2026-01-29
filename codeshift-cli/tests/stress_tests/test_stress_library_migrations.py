"""
Stress test file: Complex library migration patterns for Codeshift.

This file contains COMPLEX patterns from multiple libraries that Codeshift
should be able to migrate. It tests:
- Pydantic v1 -> v2 patterns
- SQLAlchemy 1.x -> 2.x patterns
- Requests -> HTTPX patterns
- Flask 2.x -> 3.x patterns
- And combinations of these

Run with:
    cd /Users/youssefragab/Desktop/Projects/Codeshift/codeshift-cli
    source .venv/bin/activate
    codeshift upgrade pydantic --target 2.5.0 --file tests/stress_tests/test_stress_library_migrations.py --verbose
"""

from __future__ import annotations

import builtins
import json
from datetime import datetime
from typing import Any, Generic, TypeVar

# =============================================================================
# PYDANTIC V1 PATTERNS - Need migration to v2
# =============================================================================
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from pydantic.generics import GenericModel  # Deprecated in v2


# Basic model with v1 patterns
class UserV1(BaseModel):
    """User model with Pydantic v1 patterns."""

    id: int
    name: str
    email: str
    age: int | None = None
    is_active: bool = True
    tags: list[str] = []
    metadata: builtins.dict[str, Any] = {}
    model_config = ConfigDict(from_attributes=True, validate_assignment=True, extra="forbid")

    @field_validator("email")  # Should be @field_validator in v2
    @classmethod
    def validate_email(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError("Invalid email format")
        return v.lower()

    @field_validator("name", always=True, mode="before")  # pre and always args changed
    @classmethod
    def normalize_name(cls, v: str) -> str:
        return v.strip().title()

    @field_validator("tags", each_item=True)  # each_item removed in v2
    @classmethod
    def validate_tag(cls, v: str) -> str:
        return v.lower()

    @model_validator(mode="before")  # Should be @model_validator in v2
    @classmethod
    def validate_user(cls, values: dict) -> dict:
        if values.get("age") and values.get("age") < 0:
            raise ValueError("Age must be positive")
        return values

    def dict(self, **kwargs) -> dict:  # Renamed to model_dump in v2
        return super().model_dump(**kwargs)

    def json(self, **kwargs) -> str:  # Renamed to model_dump_json in v2
        return super().model_dump_json(**kwargs)

    def copy(self, **kwargs) -> UserV1:  # Renamed to model_copy in v2
        return super().model_copy(**kwargs)

    @classmethod
    def parse_obj(cls, obj: Any) -> UserV1:  # Renamed to model_validate in v2
        return super().model_validate(obj)

    @classmethod
    def parse_raw(cls, data: str) -> UserV1:  # Renamed to model_validate_json in v2
        return super().model_validate_json(data)

    @classmethod
    def schema(cls) -> dict:  # Renamed to model_json_schema in v2
        return super().model_json_schema()

    @classmethod
    def update_forward_refs(cls) -> None:  # Renamed to model_rebuild in v2
        super().model_rebuild()


# Complex nested model
class AddressV1(BaseModel):
    street: str
    city: str
    country: str = "USA"
    zip_code: str | None = Field(None, pattern=r"^\d{5}(-\d{4})?$")  # regex renamed to pattern
    model_config = ConfigDict(from_attributes=True)


class CompanyV1(BaseModel):
    name: str
    address: AddressV1
    employees: list[UserV1] = []
    founded: datetime | None = None
    model_config = ConfigDict(from_attributes=True)

    @field_validator("employees")
    @classmethod
    def at_least_one_employee(cls, v: list) -> list:
        # Complex validator logic
        if not v:
            pass  # Allow empty for now
        return v

    @model_validator(mode="before")
    @classmethod
    def process_input(cls, values: dict) -> dict:
        # Pre-processing
        if "name" in values and isinstance(values["name"], str):
            values["name"] = values["name"].upper()
        return values


# Generic model (changed significantly in v2)
T = TypeVar("T")


class ResponseV1(GenericModel, Generic[T]):  # GenericModel deprecated
    """Generic response wrapper."""
    data: T
    success: bool = True
    error: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    model_config = ConfigDict(from_attributes=True)


# Model with __fields__ access (changed to model_fields in v2)
class DynamicModel(BaseModel):
    value: int

    def get_field_names(self) -> list:
        return list(self.model_fields.keys())  # __fields__ -> model_fields

    def get_field_info(self, name: str) -> Any:
        return self.model_fields[name]  # __fields__ -> model_fields


# Model with constrained types
from pydantic import ConfigDict, confloat, conint, conlist, constr  # Some deprecated


class ConstrainedModel(BaseModel):
    positive_int: conint(gt=0)  # Should use Annotated in v2
    short_string: constr(max_length=10)
    float_range: confloat(ge=0.0, le=1.0)
    string_list: conlist(str, min_items=1, max_items=10)  # min_items -> min_length


# =============================================================================
# SQLALCHEMY 1.x PATTERNS - Need migration to 2.x
# =============================================================================

from sqlalchemy import Column, ForeignKey, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base  # Deprecated location
from sqlalchemy.orm import relationship, sessionmaker

# Old declarative base pattern
Base = declarative_base()  # Should use DeclarativeBase class in 2.x


class UserDB(Base):
    """SQLAlchemy model with 1.x patterns."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)  # Should use mapped_column
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True)

    # Old relationship syntax
    posts = relationship("PostDB", back_populates="author")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, name={self.name})>"


class PostDB(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    content = Column(String)
    author_id = Column(Integer, ForeignKey("users.id"))

    author = relationship("UserDB", back_populates="posts")


# Session factory pattern
engine = create_engine("sqlite:///:memory:", echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db_session():
    """Get database session - old pattern."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Query patterns that changed in 2.x
def query_users_old_style(session, name_filter: str) -> list:
    """Old-style query patterns."""
    # Query via session.query() - deprecated in 2.x
    users = session.query(UserDB).filter(UserDB.name.like(f"%{name_filter}%")).all()

    # Query with filter_by
    active_users = session.query(UserDB).filter_by(is_active=True).first()

    # Scalar query
    count = session.query(UserDB).count()

    return users


# =============================================================================
# REQUESTS PATTERNS - Could migrate to HTTPX
# =============================================================================

import requests
from requests.exceptions import ConnectionError, RequestException, Timeout


class APIClient:
    """API client using requests - could use httpx."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        })

    def get(self, endpoint: str, params: dict | None = None) -> dict:
        """GET request."""
        try:
            response = self.session.get(
                f"{self.base_url}/{endpoint}",
                params=params,
                timeout=30
            )
            response.raise_for_status()
            return response.model_dump_json()
        except Timeout:
            raise RuntimeError("Request timed out")
        except ConnectionError:
            raise RuntimeError("Connection failed")
        except RequestException as e:
            raise RuntimeError(f"Request failed: {e}")

    def post(self, endpoint: str, data: dict) -> dict:
        """POST request."""
        response = self.session.post(
            f"{self.base_url}/{endpoint}",
            json=data,
            timeout=30
        )
        response.raise_for_status()
        return response.model_dump_json()

    def download_file(self, url: str, filepath: str) -> None:
        """Download file with streaming."""
        with self.session.get(url, stream=True) as response:
            response.raise_for_status()
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)


# =============================================================================
# FLASK PATTERNS - 2.x to 3.x
# =============================================================================

# Note: These imports might fail if Flask is not installed
try:
    from flask import Flask, g, jsonify, request
    from flask.views import MethodView

    app = Flask(__name__)


    @app.route("/users", methods=["GET", "POST"])
    def users():
        """User endpoint with Flask 2.x patterns."""
        if request.method == "GET":
            # Old pattern for getting JSON
            data = request.get_json(force=True, silent=True) or {}
            return jsonify({"users": [], "query": data})
        elif request.method == "POST":
            user_data = request.get_json()
            return jsonify(user_data), 201


    @app.before_request
    def before_request():
        """Before request hook."""
        g.request_start = datetime.utcnow()


    @app.after_request
    def after_request(response):
        """After request hook."""
        return response


    class UserAPI(MethodView):
        """Class-based view."""

        def get(self, user_id: int):
            return jsonify({"id": user_id})

        def post(self):
            data = request.get_json()
            return jsonify(data), 201

        def put(self, user_id: int):
            data = request.get_json()
            return jsonify({"id": user_id, **data})

        def delete(self, user_id: int):
            return "", 204

except ImportError:
    pass  # Flask not installed


# =============================================================================
# COMPLEX COMBINED PATTERNS
# =============================================================================

class DataService:
    """Service combining multiple library patterns."""

    def __init__(self, api_url: str, api_key: str):
        self.api_client = APIClient(api_url, api_key)

    def fetch_and_validate_user(self, user_id: int) -> UserV1:
        """Fetch user from API and validate with Pydantic."""
        data = self.api_client.get(f"users/{user_id}")
        # Using Pydantic v1 parse_obj
        return UserV1.model_validate(data)

    def save_user_to_db(self, user: UserV1, session) -> UserDB:
        """Save Pydantic model to SQLAlchemy."""
        # Using v1 dict() method
        user_data = user.model_dump(exclude_unset=True)
        db_user = UserDB(**user_data)
        session.add(db_user)
        session.commit()
        return db_user

    def get_users_as_models(self, session) -> list[UserV1]:
        """Query DB and convert to Pydantic models."""
        # Old SQLAlchemy query style
        db_users = session.query(UserDB).all()
        # Using Pydantic v1 from_orm (requires orm_mode)
        return [UserV1.from_orm(u) for u in db_users]


# =============================================================================
# EDGE CASES AND COMPLEX SCENARIOS
# =============================================================================

class ComplexValidatorModel(BaseModel):
    """Model with complex validator scenarios."""

    items: list[dict[str, Any]]
    config_data: dict[str, str | int | list[str]]

    @field_validator("items", mode="before")
    @classmethod
    def parse_items(cls, v):
        """Complex pre-validator."""
        if isinstance(v, str):
            return json.loads(v)
        return v

    @field_validator("items")
    @classmethod
    def validate_items(cls, v, values, field):
        """Validator with values and field access."""
        # In v2, signature changed to use ValidationInfo
        for item in v:
            if "id" not in item:
                raise ValueError("Each item must have an id")
        return v

    @model_validator(mode="after")
    @classmethod
    def final_validation(cls, values):
        """Post root validator."""
        items = values.get("items", [])
        config = values.get("config_data", {})

        if len(items) > config.get("max_items", 100):
            raise ValueError("Too many items")

        return values


class ModelWithPrivateAttrs(BaseModel):
    """Model with private attributes."""
    name: str

    # Private attributes pattern changed in v2
    _processed: bool = False
    _cache: dict = {}

    class Config:
        underscore_attrs_are_private = True  # Changed in v2


class InheritedModel(UserV1):
    """Model inheriting from another."""
    role: str = "user"
    permissions: list[str] = []

    class Config(UserV1.Config):
        # Inheriting Config - pattern changed in v2
        pass

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        allowed = ["user", "admin", "moderator"]
        if v not in allowed:
            raise ValueError(f"Role must be one of {allowed}")
        return v


# Using __get_validators__ (removed in v2)
class CustomType:
    """Custom type with v1 validator pattern."""

    def __init__(self, value: str):
        self.value = value

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise TypeError("string required")
        return cls(v)

    def __repr__(self):
        return f"CustomType({self.value!r})"


class ModelWithCustomType(BaseModel):
    custom: CustomType


# =============================================================================
# TEST EXECUTION
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Library Migration Stress Test")
    print("=" * 60)

    # Test Pydantic models
    print("\n1. Testing Pydantic v1 patterns...")

    try:
        user = UserV1(
            id=1,
            name="  john doe  ",
            email="JOHN@EXAMPLE.COM",
            age=30,
            tags=["Developer", "Python"]
        )
        print(f"   Created user: {user.name}")
        print(f"   User dict: {user.model_dump()}")
        print(f"   User JSON: {user.model_dump_json()}")
        print(f"   Schema: {UserV1.model_json_schema()}")
    except ValidationError as e:
        print(f"   Validation error: {e}")

    # Test nested models
    print("\n2. Testing nested models...")
    address = AddressV1(street="123 Main St", city="Boston")
    company = CompanyV1(
        name="acme corp",
        address=address,
        employees=[user]
    )
    print(f"   Company: {company.name}")
    print(f"   Address: {company.address.model_dump()}")

    # Test generic model
    print("\n3. Testing generic model...")
    response = ResponseV1[UserV1](data=user)
    print(f"   Response success: {response.success}")
    print(f"   Response data: {response.data.name}")

    # Test constrained model
    print("\n4. Testing constrained types...")
    try:
        constrained = ConstrainedModel(
            positive_int=5,
            short_string="hello",
            float_range=0.5,
            string_list=["a", "b", "c"]
        )
        print(f"   Constrained model: {constrained.model_dump()}")
    except ValidationError as e:
        print(f"   Validation error: {e}")

    # Test dynamic model
    print("\n5. Testing model field access...")
    dynamic = DynamicModel(value=42)
    print(f"   Field names: {dynamic.get_field_names()}")

    print("\n" + "=" * 60)
    print("Stress test complete!")
    print("=" * 60)
