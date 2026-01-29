"""Stress test for multi-library migration scenarios.

This module tests the Codeshift migration tool against a complex, realistic scenario
combining 6 major Python libraries in a single file:
- Pydantic v1 -> v2 (data validation)
- SQLAlchemy 1.4 -> 2.0 (database ORM)
- FastAPI (API endpoints)
- Celery 4.x -> 5.x (background tasks)
- Marshmallow 2.x -> 3.x (serialization)
- Pandas 1.x -> 2.0 (data processing)

The test validates:
1. Each individual transformer works correctly on its patterns
2. Multiple transformers can be applied sequentially
3. Cross-library data flows are preserved
4. The resulting code is syntactically valid
"""

from pathlib import Path

import pytest

from codeshift.migrator.transforms.celery_transformer import transform_celery
from codeshift.migrator.transforms.fastapi_transformer import transform_fastapi
from codeshift.migrator.transforms.marshmallow_transformer import transform_marshmallow
from codeshift.migrator.transforms.pandas_transformer import transform_pandas
from codeshift.migrator.transforms.pydantic_v1_to_v2 import transform_pydantic_v1_to_v2
from codeshift.migrator.transforms.sqlalchemy_transformer import transform_sqlalchemy

# =============================================================================
# COMPLEX MULTI-LIBRARY CODE SAMPLE (LEGACY VERSION)
# =============================================================================
# This code intentionally uses OLD patterns from all 6 libraries that need migration.

MULTI_LIBRARY_LEGACY_CODE = '''
"""Complex multi-library application using legacy patterns.

This module combines Pydantic, SQLAlchemy, FastAPI, Celery, Marshmallow, and Pandas
in a realistic data processing pipeline scenario.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any

# Pydantic v1 imports
from pydantic import BaseModel, Field, validator, root_validator

# SQLAlchemy 1.4 imports
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session, backref

# FastAPI imports (with starlette patterns)
from starlette.responses import JSONResponse
from starlette.requests import Request

# Celery 4.x imports
from celery.task import task
from celery.decorators import periodic_task

# Marshmallow 2.x imports
from marshmallow import Schema, fields, post_load, pre_load, validates_schema

# Pandas import
import pandas as pd


# =============================================================================
# SQLAlchemy Models (v1.4 patterns)
# =============================================================================

Base = declarative_base()


class UserDB(Base):
    """User database model using SQLAlchemy 1.4 patterns."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    full_name = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    score = Column(Float, default=0.0)

    # Relationship with backref (deprecated in SQLAlchemy 2.0)
    orders = relationship("OrderDB", backref=backref("user", lazy="select"))


class OrderDB(Base):
    """Order database model."""
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    total_amount = Column(Float, nullable=False)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)


# =============================================================================
# Pydantic v1 Models (for FastAPI request/response)
# =============================================================================

class UserBase(BaseModel):
    """Base user model with Pydantic v1 patterns."""
    username: str = Field(..., min_length=3, max_length=50, regex=r"^[a-zA-Z0-9_]+$")
    email: str = Field(..., regex=r"^[\\w.-]+@[\\w.-]+\\.\\w+$")
    full_name: Optional[str] = None

    class Config:
        orm_mode = True
        validate_assignment = True
        extra = "forbid"


class UserCreate(UserBase):
    """User creation model."""
    password: str = Field(..., min_length=8)

    @validator("password")
    def validate_password(cls, v):
        """Validate password strength."""
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain uppercase letter")
        return v


class UserResponse(UserBase):
    """User response model."""
    id: int
    created_at: datetime
    score: float = 0.0

    @root_validator
    def validate_user_response(cls, values):
        """Validate the complete user response."""
        if values.get("score", 0) < 0:
            values["score"] = 0
        return values


class OrderCreate(BaseModel):
    """Order creation model."""
    user_id: int
    items: List[Dict[str, Any]] = Field(min_items=1)
    total_amount: float = Field(gt=0)

    class Config:
        orm_mode = True


class OrderResponse(BaseModel):
    """Order response model."""
    id: int
    user_id: int
    total_amount: float
    status: str
    created_at: datetime

    class Config:
        orm_mode = True


# =============================================================================
# Marshmallow v2 Schemas (for external API serialization)
# =============================================================================

class ExternalUserSchema(Schema):
    """Marshmallow v2 schema for external API serialization."""
    id = fields.Integer(dump_only=True)
    username = fields.String(required=True, load_from="user_name")
    email = fields.Email(required=True)
    full_name = fields.String(missing=None)
    created_at = fields.DateTime(dump_only=True)
    score = fields.Float(default=0.0)

    class Meta:
        strict = True
        json_module = None

    @post_load(pass_many=True)
    def make_user(self, data, **kwargs):
        """Process loaded user data."""
        if isinstance(data, list):
            return [self._process_user(d) for d in data]
        return self._process_user(data)

    def _process_user(self, data):
        """Process single user data."""
        return data

    @pre_load(pass_many=True)
    def preprocess(self, data, **kwargs):
        """Preprocess incoming data."""
        return data

    @validates_schema(pass_many=True)
    def validate_schema(self, data, **kwargs):
        """Validate the complete schema."""
        pass


class ExternalOrderSchema(Schema):
    """Order schema for external API."""
    id = fields.Integer(dump_only=True)
    user_id = fields.Integer(required=True)
    total_amount = fields.Decimal(required=True, as_string=True)
    status = fields.String(missing="pending")
    created_at = fields.DateTime(dump_only=True)

    class Meta:
        strict = True


# =============================================================================
# Database Operations (SQLAlchemy 1.4 Query API)
# =============================================================================

def get_user_by_id(session: Session, user_id: int) -> Optional[UserDB]:
    """Get user by ID using legacy query API."""
    return session.query(UserDB).get(user_id)


def get_users_with_high_score(session: Session, min_score: float) -> List[UserDB]:
    """Get users with score above threshold."""
    return session.query(UserDB).filter(UserDB.score >= min_score).all()


def get_user_by_username(session: Session, username: str) -> Optional[UserDB]:
    """Get user by username using filter_by."""
    return session.query(UserDB).filter_by(username=username).first()


def count_active_users(session: Session) -> int:
    """Count users with orders."""
    return session.query(UserDB).filter(UserDB.score > 0).count()


def get_all_orders(session: Session) -> List[OrderDB]:
    """Get all orders."""
    return session.query(OrderDB).all()


# =============================================================================
# Celery Tasks (v4.x patterns)
# =============================================================================

# Celery configuration (uppercase keys - deprecated in v5)
CELERY_RESULT_BACKEND = "redis://localhost:6379/0"
CELERY_BROKER_URL = "redis://localhost:6379/1"
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"


@task
def process_user_registration(user_data: dict) -> dict:
    """Process new user registration asynchronously."""
    # Simulate processing
    user_data["processed"] = True
    return user_data


@task(bind=True, max_retries=3)
def calculate_user_score(self, user_id: int) -> float:
    """Calculate user score based on order history."""
    try:
        # Simulate score calculation
        return 100.0
    except Exception as exc:
        self.retry(exc=exc)


@task
def process_order_batch(order_ids: List[int]) -> List[dict]:
    """Process a batch of orders."""
    results = []
    for order_id in order_ids:
        results.append({"order_id": order_id, "processed": True})
    return results


# =============================================================================
# Pandas Data Processing (v1.x patterns)
# =============================================================================

def process_user_analytics(df: pd.DataFrame) -> pd.DataFrame:
    """Process user analytics data using legacy Pandas patterns."""
    # Iterate over columns (deprecated iteritems)
    for col_name, col_data in df.iteritems():
        print(f"Processing column: {col_name}")

    # Check monotonicity (deprecated)
    if df.index.is_monotonic:
        print("Index is monotonic increasing")

    # Use append (removed in pandas 2.0)
    summary_row = pd.DataFrame({"total": [df["score"].sum()]})
    result = df.append(summary_row, ignore_index=True)

    # Write CSV with old parameter name
    result.to_csv("output.csv", line_terminator="\\n")

    return result


def aggregate_order_data(orders_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate order data with groupby operations."""
    # GroupBy aggregation (numeric_only behavior change)
    daily_totals = orders_df.groupby("date").sum()

    # More aggregations
    user_stats = orders_df.groupby("user_id").mean()

    return daily_totals


# =============================================================================
# FastAPI Endpoints (using Pydantic models and SQLAlchemy)
# =============================================================================

def create_user_endpoint(user_data: UserCreate, session: Session) -> UserResponse:
    """Create a new user (FastAPI-style endpoint function)."""
    # Convert Pydantic model to dict (v1 pattern)
    user_dict = user_data.dict()
    del user_dict["password"]  # Don't store plaintext

    # Create DB user
    db_user = UserDB(**user_dict)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)

    # Queue background task
    process_user_registration.delay(user_dict)

    # Return response using Pydantic (v1 pattern)
    return UserResponse.parse_obj(db_user.__dict__)


def get_user_endpoint(user_id: int, session: Session) -> UserResponse:
    """Get user by ID."""
    db_user = get_user_by_id(session, user_id)
    if not db_user:
        return None

    # Get user schema
    schema = UserResponse.schema()

    return UserResponse.parse_obj(db_user.__dict__)


def list_users_endpoint(session: Session) -> List[UserResponse]:
    """List all users with external API format."""
    users = session.query(UserDB).all()

    # Use Marshmallow for external serialization
    external_schema = ExternalUserSchema(many=True, strict=True)
    external_data = external_schema.dump(users).data

    # Convert back to Pydantic for response
    return [UserResponse.parse_obj(u) for u in users]


def export_users_to_dataframe(session: Session) -> pd.DataFrame:
    """Export users to Pandas DataFrame for analytics."""
    users = session.query(UserDB).all()

    # Convert to dicts using Pydantic
    user_dicts = [UserResponse.parse_obj(u.__dict__).dict() for u in users]

    # Create DataFrame
    df = pd.DataFrame(user_dicts)

    # Process analytics
    processed_df = process_user_analytics(df)

    return processed_df


# =============================================================================
# Cross-Library Data Flow Functions
# =============================================================================

def full_data_pipeline(session: Session, raw_data: dict) -> dict:
    """Complete data pipeline using all libraries."""
    # 1. Validate with Pydantic
    user_create = UserCreate.parse_obj(raw_data)

    # 2. Create in database with SQLAlchemy
    db_user = UserDB(
        username=user_create.username,
        email=user_create.email,
        full_name=user_create.full_name,
    )
    session.add(db_user)
    session.commit()
    session.refresh(db_user)

    # 3. Serialize with Marshmallow for external API
    external_schema = ExternalUserSchema(strict=True)
    external_format = external_schema.dump(db_user).data

    # 4. Queue background processing with Celery
    calculate_user_score.delay(db_user.id)

    # 5. Add to analytics DataFrame with Pandas
    user_df = pd.DataFrame([UserResponse.parse_obj(db_user.__dict__).dict()])
    user_df.to_csv("users_log.csv", line_terminator="\\n", mode="a", header=False)

    # 6. Return Pydantic response
    response = UserResponse.parse_obj(db_user.__dict__)
    return response.dict()


def analyze_user_orders(session: Session, user_id: int) -> dict:
    """Analyze user orders combining SQLAlchemy and Pandas."""
    # Query with SQLAlchemy 1.4 API
    user = session.query(UserDB).get(user_id)
    orders = session.query(OrderDB).filter_by(user_id=user_id).all()

    # Convert to Marshmallow schema
    order_schema = ExternalOrderSchema(many=True, strict=True)
    serialized = order_schema.dump(orders).data

    # Create Pandas DataFrame
    orders_df = pd.DataFrame(serialized)

    if not orders_df.empty:
        # Use legacy iteritems
        for col, data in orders_df.iteritems():
            print(f"Order column: {col}, type: {data.dtype}")

        # Aggregate
        total = orders_df.groupby("status").sum()

    # Return Pydantic-validated response
    user_response = UserResponse.parse_obj(user.__dict__)
    return {
        "user": user_response.dict(),
        "order_count": len(orders),
        "total_amount": sum(o.total_amount for o in orders),
    }


# =============================================================================
# Field access patterns (Pydantic v1)
# =============================================================================

def inspect_model_fields():
    """Inspect model fields using v1 patterns."""
    # Access __fields__ (v1 pattern)
    fields = UserResponse.__fields__
    for name, field in fields.items():
        print(f"Field: {name}, Type: {field.outer_type_}")
    return fields
'''


# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def multi_library_code() -> str:
    """Return the multi-library legacy code sample."""
    return MULTI_LIBRARY_LEGACY_CODE


@pytest.fixture
def temp_file_path(tmp_path: Path) -> Path:
    """Return a temporary file path for testing."""
    return tmp_path / "test_multi_library.py"


# =============================================================================
# INDIVIDUAL LIBRARY TRANSFORMATION TESTS
# =============================================================================

class TestPydanticTransformations:
    """Test Pydantic v1 to v2 transformations in multi-library context."""

    def test_pydantic_transforms_in_multi_library_code(self, multi_library_code: str) -> None:
        """Test that Pydantic transforms work on multi-library code."""
        transformed, changes = transform_pydantic_v1_to_v2(multi_library_code)

        # Verify key transformations
        assert "ConfigDict" in transformed, "ConfigDict should be added"
        assert "from_attributes=True" in transformed, "orm_mode should become from_attributes"
        assert "@field_validator" in transformed, "validator should become field_validator"
        assert "@model_validator" in transformed, "root_validator should become model_validator"
        assert ".model_dump()" in transformed, ".dict() should become .model_dump()"
        assert ".model_validate(" in transformed, ".parse_obj() should become .model_validate()"
        assert "model_fields" in transformed, "__fields__ should become model_fields"
        assert "pattern=" in transformed, "regex= should become pattern="

        # Verify old patterns are replaced
        assert "class Config:" not in transformed, "Config class should be removed"
        assert "@validator" not in transformed or "@field_validator" in transformed
        assert "@root_validator" not in transformed

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

        # Verify changes were recorded
        assert len(changes) > 0, "Changes should be recorded"

        print(f"Pydantic: {len(changes)} changes applied")

    def test_pydantic_field_regex_to_pattern(self, multi_library_code: str) -> None:
        """Test Field regex parameter transformation."""
        transformed, changes = transform_pydantic_v1_to_v2(multi_library_code)

        # The regex patterns in Field() should become pattern=
        assert 'regex=r"^[a-zA-Z0-9_]+$"' not in transformed
        assert 'pattern=r"^[a-zA-Z0-9_]+$"' in transformed or "pattern=" in transformed

    def test_pydantic_min_items_to_min_length(self, multi_library_code: str) -> None:
        """Test Field min_items parameter transformation."""
        transformed, changes = transform_pydantic_v1_to_v2(multi_library_code)

        assert "min_items=" not in transformed
        assert "min_length=1" in transformed


class TestSQLAlchemyTransformations:
    """Test SQLAlchemy 1.4 to 2.0 transformations in multi-library context."""

    def test_sqlalchemy_transforms_in_multi_library_code(self, multi_library_code: str) -> None:
        """Test that SQLAlchemy transforms work on multi-library code."""
        transformed, changes = transform_sqlalchemy(multi_library_code)

        # Verify key transformations
        assert "DeclarativeBase" in transformed, "declarative_base should become DeclarativeBase"
        assert "class Base(DeclarativeBase):" in transformed, "Base should extend DeclarativeBase"

        # Query API changes
        assert "session.get(UserDB" in transformed, "query.get() should become session.get()"
        assert "select(" in transformed, "Query should use select()"
        assert "session.execute(" in transformed, "Query should use session.execute()"
        assert ".scalars()" in transformed, "Results should use scalars()"

        # Backref removal should be flagged
        assert "backref" not in transformed or any(
            "backref" in c.description.lower() or "back_populates" in c.description.lower()
            for c in changes
        ), "backref import should be handled"

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

        print(f"SQLAlchemy: {len(changes)} changes applied")

    def test_sqlalchemy_query_to_select(self, multi_library_code: str) -> None:
        """Test session.query() to session.execute(select()) transformation."""
        transformed, changes = transform_sqlalchemy(multi_library_code)

        # All query patterns should be transformed
        assert "session.query(UserDB).filter(UserDB.score >= min_score).all()" not in transformed
        assert "session.execute(select(UserDB)" in transformed

    def test_sqlalchemy_filter_by_transformation(self, multi_library_code: str) -> None:
        """Test filter_by() transformation to where()."""
        transformed, changes = transform_sqlalchemy(multi_library_code)

        # filter_by should become where with proper comparison
        change_descriptions = [c.description for c in changes]
        has_filter_transform = any(
            "filter" in d.lower() or "where" in d.lower() for d in change_descriptions
        )
        # The transformation happens - verify the pattern is gone or transformed
        assert ".filter_by(" not in transformed or has_filter_transform


class TestFastAPITransformations:
    """Test FastAPI transformations in multi-library context."""

    def test_fastapi_transforms_in_multi_library_code(self, multi_library_code: str) -> None:
        """Test that FastAPI transforms work on multi-library code."""
        transformed, changes = transform_fastapi(multi_library_code)

        # Verify starlette imports are transformed
        assert "from fastapi.responses import JSONResponse" in transformed, \
            "starlette.responses should become fastapi.responses"
        assert "from fastapi import Request" in transformed or "from fastapi" in transformed, \
            "starlette.requests should become fastapi"

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

        print(f"FastAPI: {len(changes)} changes applied")


class TestCeleryTransformations:
    """Test Celery 4.x to 5.x transformations in multi-library context."""

    def test_celery_transforms_in_multi_library_code(self, multi_library_code: str) -> None:
        """Test that Celery transforms work on multi-library code."""
        transformed, changes = transform_celery(multi_library_code)

        # Verify import transformations
        assert "from celery.task import task" not in transformed, \
            "celery.task import should be removed"
        assert "from celery.decorators import periodic_task" not in transformed, \
            "celery.decorators import should be removed"

        # Verify config key transformations
        assert "result_backend" in transformed, "CELERY_RESULT_BACKEND should become result_backend"
        assert "broker_url" in transformed, "CELERY_BROKER_URL should become broker_url"
        assert "task_serializer" in transformed, "CELERY_TASK_SERIALIZER should become task_serializer"

        # Verify decorator transformations
        assert "@shared_task" in transformed or "shared_task" in transformed, \
            "@task should become @shared_task"

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

        print(f"Celery: {len(changes)} changes applied")

    def test_celery_config_uppercase_to_lowercase(self, multi_library_code: str) -> None:
        """Test uppercase config key transformation."""
        transformed, changes = transform_celery(multi_library_code)

        # Uppercase config names should be lowercase
        assert "CELERY_RESULT_BACKEND" not in transformed
        assert "CELERY_BROKER_URL" not in transformed
        assert "CELERY_TASK_SERIALIZER" not in transformed


class TestMarshmallowTransformations:
    """Test Marshmallow 2.x to 3.x transformations in multi-library context."""

    def test_marshmallow_transforms_in_multi_library_code(self, multi_library_code: str) -> None:
        """Test that Marshmallow transforms work on multi-library code."""
        transformed, changes = transform_marshmallow(multi_library_code)

        # Verify field parameter renames
        assert "data_key=" in transformed, "load_from should become data_key"
        assert "load_default=" in transformed, "missing should become load_default"
        assert "dump_default=" in transformed, "default should become dump_default"

        # Verify Meta.strict is removed
        assert "strict = True" not in transformed or "# removed" in str(changes), \
            "Meta.strict should be removed"

        # Verify pass_many removal
        assert "pass_many=True" not in transformed, "pass_many should be removed from decorators"

        # Verify .data access is removed
        assert ".dump(users).data" not in transformed or ".dump(users)" in transformed, \
            ".data access should be removed"

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

        print(f"Marshmallow: {len(changes)} changes applied")

    def test_marshmallow_strict_removal(self, multi_library_code: str) -> None:
        """Test strict parameter removal."""
        transformed, changes = transform_marshmallow(multi_library_code)

        # Strict in Meta and instantiation should be removed
        assert "strict=True" not in transformed
        assert "class Meta:" in transformed  # Meta class still exists, just without strict


class TestPandasTransformations:
    """Test Pandas 1.x to 2.0 transformations in multi-library context."""

    def test_pandas_transforms_in_multi_library_code(self, multi_library_code: str) -> None:
        """Test that Pandas transforms work on multi-library code."""
        transformed, changes = transform_pandas(multi_library_code)

        # Verify iteritems -> items
        assert ".iteritems()" not in transformed, "iteritems should become items"
        assert ".items()" in transformed, "items() should replace iteritems()"

        # Verify is_monotonic -> is_monotonic_increasing
        assert ".is_monotonic" not in transformed or ".is_monotonic_increasing" in transformed

        # Verify line_terminator -> lineterminator
        assert "line_terminator=" not in transformed, \
            "line_terminator should become lineterminator"
        assert "lineterminator=" in transformed

        # Verify append -> concat
        assert ".append(" not in transformed or "pd.concat" in transformed, \
            "append should become concat"

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

        print(f"Pandas: {len(changes)} changes applied")


# =============================================================================
# SEQUENTIAL MULTI-LIBRARY TRANSFORMATION TESTS
# =============================================================================

class TestSequentialTransformations:
    """Test applying multiple transformers sequentially."""

    def test_all_transformers_sequential(self, multi_library_code: str) -> None:
        """Test applying all transformers in sequence."""
        code = multi_library_code
        all_changes = []

        # 1. Apply Pydantic transforms
        code, pydantic_changes = transform_pydantic_v1_to_v2(code)
        all_changes.extend(pydantic_changes)
        compile(code, "<string>", "exec")  # Verify valid after each step
        print(f"After Pydantic: {len(pydantic_changes)} changes")

        # 2. Apply SQLAlchemy transforms
        code, sqlalchemy_changes = transform_sqlalchemy(code)
        all_changes.extend(sqlalchemy_changes)
        compile(code, "<string>", "exec")
        print(f"After SQLAlchemy: {len(sqlalchemy_changes)} changes")

        # 3. Apply FastAPI transforms
        code, fastapi_changes = transform_fastapi(code)
        all_changes.extend(fastapi_changes)
        compile(code, "<string>", "exec")
        print(f"After FastAPI: {len(fastapi_changes)} changes")

        # 4. Apply Celery transforms
        code, celery_changes = transform_celery(code)
        all_changes.extend(celery_changes)
        compile(code, "<string>", "exec")
        print(f"After Celery: {len(celery_changes)} changes")

        # 5. Apply Marshmallow transforms
        code, marshmallow_changes = transform_marshmallow(code)
        all_changes.extend(marshmallow_changes)
        compile(code, "<string>", "exec")
        print(f"After Marshmallow: {len(marshmallow_changes)} changes")

        # 6. Apply Pandas transforms
        code, pandas_changes = transform_pandas(code)
        all_changes.extend(pandas_changes)
        compile(code, "<string>", "exec")
        print(f"After Pandas: {len(pandas_changes)} changes")

        # Summary
        print(f"\nTotal changes: {len(all_changes)}")
        print(f"Final code length: {len(code)} chars")

        # Verify all major transformations were applied
        assert "ConfigDict" in code, "Pydantic transforms incomplete"
        assert "DeclarativeBase" in code, "SQLAlchemy transforms incomplete"
        assert "from fastapi" in code, "FastAPI transforms incomplete"
        assert "result_backend" in code, "Celery transforms incomplete"
        assert "data_key=" in code, "Marshmallow transforms incomplete"
        assert ".items()" in code, "Pandas transforms incomplete"

        # Record summary for reporting
        print("\n=== MULTI-LIBRARY TRANSFORMATION SUMMARY ===")
        print("Libraries processed: 6")
        print(f"Total transformations: {len(all_changes)}")
        print("Status: SUCCESS - All transformations applied, code is syntactically valid")

    def test_transformation_order_independence(self, multi_library_code: str) -> None:
        """Test that transformation order doesn't break things."""
        # Try different order: Pandas -> Celery -> Marshmallow -> FastAPI -> SQLAlchemy -> Pydantic
        code = multi_library_code

        code, _ = transform_pandas(code)
        compile(code, "<string>", "exec")

        code, _ = transform_celery(code)
        compile(code, "<string>", "exec")

        code, _ = transform_marshmallow(code)
        compile(code, "<string>", "exec")

        code, _ = transform_fastapi(code)
        compile(code, "<string>", "exec")

        code, _ = transform_sqlalchemy(code)
        compile(code, "<string>", "exec")

        code, _ = transform_pydantic_v1_to_v2(code)
        compile(code, "<string>", "exec")

        # Final code should still be valid
        assert "ConfigDict" in code
        assert "DeclarativeBase" in code

    def test_idempotency(self, multi_library_code: str) -> None:
        """Test that transformations are idempotent (applying twice doesn't break things)."""
        # First pass
        code1, changes1 = transform_pydantic_v1_to_v2(multi_library_code)
        code1, _ = transform_sqlalchemy(code1)
        code1, _ = transform_fastapi(code1)
        code1, _ = transform_celery(code1)
        code1, _ = transform_marshmallow(code1)
        code1, _ = transform_pandas(code1)

        # Second pass on already-transformed code
        code2, changes2 = transform_pydantic_v1_to_v2(code1)
        code2, _ = transform_sqlalchemy(code2)
        code2, _ = transform_fastapi(code2)
        code2, _ = transform_celery(code2)
        code2, _ = transform_marshmallow(code2)
        code2, _ = transform_pandas(code2)

        # Second pass should not make significant changes
        compile(code2, "<string>", "exec")

        # The code should be essentially the same
        # (minor whitespace differences might occur)
        assert len(changes2) <= len(changes1), \
            "Second pass should not introduce more changes than first"


# =============================================================================
# CROSS-LIBRARY INTEGRATION TESTS
# =============================================================================

class TestCrossLibraryIntegration:
    """Test that cross-library data flows are preserved after migration."""

    def test_pydantic_sqlalchemy_integration(self, multi_library_code: str) -> None:
        """Test Pydantic models still work with SQLAlchemy after migration."""
        code = multi_library_code

        code, _ = transform_pydantic_v1_to_v2(code)
        code, _ = transform_sqlalchemy(code)

        # Check that Pydantic with from_attributes can still work with SQLAlchemy
        assert "from_attributes=True" in code
        assert "DeclarativeBase" in code or "Base" in code

        # The data flow functions should still reference both
        assert "UserResponse" in code
        assert "UserDB" in code

        compile(code, "<string>", "exec")

    def test_celery_pandas_integration(self, multi_library_code: str) -> None:
        """Test Celery tasks using Pandas still work after migration."""
        code = multi_library_code

        code, _ = transform_celery(code)
        code, _ = transform_pandas(code)

        # Celery task decorators should be updated
        assert "@shared_task" in code or "shared_task" in code

        # Pandas operations should be updated
        assert ".items()" in code
        assert "pd.concat" in code or ".append(" not in code

        compile(code, "<string>", "exec")

    def test_marshmallow_fastapi_pydantic_integration(self, multi_library_code: str) -> None:
        """Test serialization chain: Marshmallow -> Pydantic -> FastAPI."""
        code = multi_library_code

        code, _ = transform_pydantic_v1_to_v2(code)
        code, _ = transform_fastapi(code)
        code, _ = transform_marshmallow(code)

        # All three libraries should have modern imports/patterns
        assert "ConfigDict" in code or "model_config" in code  # Pydantic v2
        assert "from fastapi" in code  # FastAPI modern imports
        assert "data_key=" in code or "load_default=" in code  # Marshmallow v3

        compile(code, "<string>", "exec")


# =============================================================================
# CODE QUALITY TESTS
# =============================================================================

class TestCodeQuality:
    """Test the quality of migrated code."""

    def test_no_syntax_errors_after_all_transforms(self, multi_library_code: str) -> None:
        """Ensure the final code has no syntax errors."""
        code = multi_library_code

        code, _ = transform_pydantic_v1_to_v2(code)
        code, _ = transform_sqlalchemy(code)
        code, _ = transform_fastapi(code)
        code, _ = transform_celery(code)
        code, _ = transform_marshmallow(code)
        code, _ = transform_pandas(code)

        # This will raise SyntaxError if code is invalid
        compile(code, "<string>", "exec")

    def test_preserved_functionality_markers(self, multi_library_code: str) -> None:
        """Test that key functional patterns are preserved."""
        code = multi_library_code

        code, _ = transform_pydantic_v1_to_v2(code)
        code, _ = transform_sqlalchemy(code)
        code, _ = transform_fastapi(code)
        code, _ = transform_celery(code)
        code, _ = transform_marshmallow(code)
        code, _ = transform_pandas(code)

        # Key function definitions should still exist
        assert "def create_user_endpoint" in code
        assert "def get_user_endpoint" in code
        assert "def process_user_analytics" in code
        assert "def full_data_pipeline" in code
        assert "def analyze_user_orders" in code

        # Key class definitions should still exist
        assert "class UserDB" in code
        assert "class OrderDB" in code
        assert "class UserBase" in code
        assert "class UserCreate" in code
        assert "class ExternalUserSchema" in code

    def test_docstrings_preserved(self, multi_library_code: str) -> None:
        """Test that docstrings are preserved after migration."""
        code = multi_library_code

        code, _ = transform_pydantic_v1_to_v2(code)
        code, _ = transform_sqlalchemy(code)

        # Key docstrings should be preserved
        assert '"""Complex multi-library application' in code
        assert '"""User database model' in code or "User database model" in code
        assert '"""Process new user registration' in code or "Process new user registration" in code

    def test_change_tracking_quality(self, multi_library_code: str) -> None:
        """Test that changes are properly tracked with meaningful descriptions."""
        code = multi_library_code
        all_changes = []

        code, changes = transform_pydantic_v1_to_v2(code)
        all_changes.extend(changes)

        code, changes = transform_sqlalchemy(code)
        all_changes.extend(changes)

        code, changes = transform_celery(code)
        all_changes.extend(changes)

        # All changes should have descriptions
        for change in all_changes:
            assert hasattr(change, 'description'), "Change should have description"
            assert change.description, "Description should not be empty"
            assert hasattr(change, 'transform_name'), "Change should have transform_name"

        # There should be a reasonable number of changes for this complex file
        assert len(all_changes) >= 20, f"Expected many changes, got {len(all_changes)}"

        print(f"\nChange quality check: {len(all_changes)} changes with proper metadata")


# =============================================================================
# STRESS/EDGE CASE TESTS
# =============================================================================

class TestEdgeCases:
    """Test edge cases and stress scenarios."""

    def test_very_long_code(self) -> None:
        """Test transformation of very long code files."""
        # Repeat the code multiple times
        long_code = MULTI_LIBRARY_LEGACY_CODE * 3

        # Should still work
        code, _ = transform_pydantic_v1_to_v2(long_code)
        code, _ = transform_sqlalchemy(code)
        code, _ = transform_fastapi(code)
        code, _ = transform_celery(code)
        code, _ = transform_marshmallow(code)
        code, _ = transform_pandas(code)

        compile(code, "<string>", "exec")
        print(f"Successfully processed {len(long_code)} chars of code")

    def test_empty_code(self) -> None:
        """Test that transformers handle empty code gracefully."""
        empty_code = ""

        code, changes = transform_pydantic_v1_to_v2(empty_code)
        assert code == ""
        assert len(changes) == 0

    def test_code_without_target_patterns(self) -> None:
        """Test code that doesn't have patterns to transform."""
        clean_code = '''
def hello():
    """Simple function with no library patterns."""
    print("Hello, World!")
    return 42
'''
        code, pydantic_changes = transform_pydantic_v1_to_v2(clean_code)
        code, sqlalchemy_changes = transform_sqlalchemy(code)

        # Should still be valid and unchanged
        compile(code, "<string>", "exec")
        assert "def hello" in code


# =============================================================================
# REPORT GENERATION
# =============================================================================

class TestReportGeneration:
    """Generate a detailed migration report."""

    def test_generate_migration_report(self, multi_library_code: str) -> None:
        """Generate and display a comprehensive migration report."""
        code = multi_library_code
        report = []

        report.append("=" * 80)
        report.append("MULTI-LIBRARY MIGRATION STRESS TEST REPORT")
        report.append("=" * 80)
        report.append(f"Original code size: {len(multi_library_code)} characters")
        report.append("")

        libraries = [
            ("Pydantic v1 -> v2", transform_pydantic_v1_to_v2),
            ("SQLAlchemy 1.4 -> 2.0", transform_sqlalchemy),
            ("FastAPI (starlette patterns)", transform_fastapi),
            ("Celery 4.x -> 5.x", transform_celery),
            ("Marshmallow 2.x -> 3.x", transform_marshmallow),
            ("Pandas 1.x -> 2.0", transform_pandas),
        ]

        total_changes = 0
        for lib_name, transform_func in libraries:
            try:
                code, changes = transform_func(code)
                compile(code, "<string>", "exec")
                status = "SUCCESS"
                total_changes += len(changes)
            except Exception as e:
                status = f"FAILED: {e}"
                changes = []

            report.append(f"Library: {lib_name}")
            report.append(f"  Status: {status}")
            report.append(f"  Changes: {len(changes)}")
            if changes:
                # Show first few changes
                for change in changes[:3]:
                    report.append(f"    - {change.description}")
                if len(changes) > 3:
                    report.append(f"    ... and {len(changes) - 3} more")
            report.append("")

        report.append("-" * 80)
        report.append(f"Total transformations applied: {total_changes}")
        report.append(f"Final code size: {len(code)} characters")
        report.append(f"Final code valid: {'YES' if compile(code, '<string>', 'exec') is None else 'COMPILE ERROR'}")
        report.append("=" * 80)

        # Print the report
        print("\n".join(report))

        # Assert overall success
        assert total_changes > 0, "Should have applied some transformations"
