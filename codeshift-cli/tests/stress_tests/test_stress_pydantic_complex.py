"""
Stress Test: Complex Pydantic v1 to v2 Migration

This file contains a VERY complex Pydantic v1 model hierarchy designed to stress-test
the Codeshift migration tool. It includes:

- 5+ nested models with cross-references
- Multiple @validator and @root_validator decorators
- Generic models with TypeVar
- Custom JSON encoders/decoders
- Field aliases, constraints, regex patterns
- Optional, Union, and List types
- Config class with ALL options
- Class inheritance chains
- Private attributes
- Custom __init__ methods
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import (
    Any,
    Generic,
    Literal,
    TypeVar,
)
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.generics import GenericModel

# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================

class UserRole(str, Enum):
    ADMIN = "admin"
    MODERATOR = "moderator"
    USER = "user"
    GUEST = "guest"


class OrderStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class PaymentMethod(str, Enum):
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    PAYPAL = "paypal"
    CRYPTO = "crypto"
    BANK_TRANSFER = "bank_transfer"


# ============================================================================
# TYPE VARIABLES FOR GENERICS
# ============================================================================

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")
ItemType = TypeVar("ItemType", bound="BaseItem")
ResponseType = TypeVar("ResponseType")


# ============================================================================
# CUSTOM JSON ENCODERS
# ============================================================================

class CustomEncoder(json.JSONEncoder):
    """Custom JSON encoder for complex types."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, set):
            return list(obj)
        if isinstance(obj, bytes):
            return obj.decode("utf-8")
        return super().default(obj)


def custom_json_decoder(dct: dict[str, Any]) -> dict[str, Any]:
    """Custom JSON decoder hook."""
    for key, value in dct.items():
        if isinstance(value, str):
            # Try to parse ISO datetime
            try:
                if "T" in value and len(value) >= 19:
                    dct[key] = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass
    return dct


# ============================================================================
# BASE MODELS WITH COMPLEX CONFIG
# ============================================================================

class StrictBaseModel(BaseModel):
    """Base model with strict validation and all Config options."""
    model_config = ConfigDict(from_attributes=True, validate_assignment=True, extra="forbid", frozen=True, str_strip_whitespace=True, min_anystr_length=0, populate_by_name=True, use_enum_values=True, arbitrary_types_allowed=True, copy_on_model_validation="deep", validate_all=True)


class AuditableModel(StrictBaseModel):
    """Model with audit fields - demonstrates inheritance."""

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime | None = None
    created_by: str | None = None
    updated_by: str | None = None
    version: int = Field(default=1, ge=1)

    # Private attributes (Pydantic v1 style)
    _internal_id: str = ""
    _cached_hash: int | None = None
    _dirty_fields: set[str] = set()

    @field_validator("updated_at", always=True)
    @classmethod
    def set_updated_at(cls, v: datetime | None, values: dict[str, Any]) -> datetime | None:
        """Automatically set updated_at if not provided."""
        if v is None and "created_at" in values:
            return values["created_at"]
        return v

    @model_validator(mode="before")
    @classmethod
    def audit_pre_validator(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Pre-validation hook for audit fields."""
        if "created_at" not in values:
            values["created_at"] = datetime.utcnow()
        return values


# ============================================================================
# GENERIC MODELS
# ============================================================================

class PaginatedResponse(GenericModel, Generic[T]):
    """Generic paginated response wrapper."""

    items: list[T]
    total: int = Field(ge=0)
    page: int = Field(ge=1, default=1)
    page_size: int = Field(ge=1, le=100, default=20)
    has_next: bool = False
    has_previous: bool = False
    model_config = ConfigDict(from_attributes=True)

    @field_validator("has_next", always=True)
    @classmethod
    def compute_has_next(cls, v: bool, values: dict[str, Any]) -> bool:
        """Compute if there are more pages."""
        if "total" in values and "page" in values and "page_size" in values:
            return values["page"] * values["page_size"] < values["total"]
        return v

    @field_validator("has_previous", always=True)
    @classmethod
    def compute_has_previous(cls, v: bool, values: dict[str, Any]) -> bool:
        """Compute if there are previous pages."""
        return values.get("page", 1) > 1


class KeyValuePair(GenericModel, Generic[K, V]):
    """Generic key-value pair model."""

    key: K
    value: V
    metadata: dict[str, Any] | None = None
    model_config = ConfigDict(from_attributes=True)


class ResultWrapper(GenericModel, Generic[ResponseType]):
    """Generic result wrapper with success/error handling."""

    success: bool = True
    data: ResponseType | None = None
    error: str | None = None
    error_code: str | None = None
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def check_consistency(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Ensure error is set only when success is False."""
        if values.get("success") and values.get("error"):
            raise ValueError("Cannot have error when success is True")
        if not values.get("success") and not values.get("error"):
            values["error"] = "Unknown error"
        return values


# ============================================================================
# NESTED MODELS WITH CROSS-REFERENCES
# ============================================================================

class Address(AuditableModel):
    """Address model with complex validation."""

    street: str = Field(..., min_length=1, max_length=200)
    street2: str | None = Field(None, max_length=200)
    city: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=2, max_length=100)
    postal_code: str = Field(..., pattern=r"^\d{5}(-\d{4})?$")
    country: str = Field(default="US", min_length=2, max_length=2)
    is_primary: bool = False
    address_type: Literal["home", "work", "billing", "shipping"] = "home"
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)

    @field_validator("country")
    @classmethod
    def validate_country(cls, v: str) -> str:
        """Validate country code is uppercase."""
        return v.upper()

    @field_validator("postal_code")
    @classmethod
    def validate_postal_code(cls, v: str, values: dict[str, Any]) -> str:
        """Validate postal code format based on country."""
        country = values.get("country", "US")
        if country == "US" and not re.match(r"^\d{5}(-\d{4})?$", v):
            raise ValueError("Invalid US postal code format")
        return v

    @model_validator(mode="before")
    @classmethod
    def validate_coordinates(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Ensure latitude and longitude are both set or both None."""
        lat = values.get("latitude")
        lon = values.get("longitude")
        if (lat is None) != (lon is None):
            raise ValueError("Latitude and longitude must both be set or both be None")
        return values


class ContactInfo(BaseModel):
    """Contact information with multiple validators."""

    email: str = Field(..., pattern=r"^[\w.-]+@[\w.-]+\.\w+$")
    phone: str | None = Field(None, pattern=r"^\+?1?\d{9,15}$")
    fax: str | None = Field(None, pattern=r"^\+?1?\d{9,15}$")
    website: str | None = None
    preferred_contact: Literal["email", "phone", "fax"] = "email"
    model_config = ConfigDict(from_attributes=True, validate_assignment=True)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        """Normalize email to lowercase."""
        return v.lower().strip()

    @field_validator("website", mode="before")
    @classmethod
    def validate_website(cls, v: str | None) -> str | None:
        """Ensure website has http(s) prefix."""
        if v and not v.startswith(("http://", "https://")):
            return f"https://{v}"
        return v


class BaseItem(AuditableModel):
    """Base item for products with complex constraints."""

    sku: str = Field(..., min_length=3, max_length=50, pattern=r"^[A-Z0-9-]+$")
    name: str = Field(..., min_length=1, max_length=200, alias="item_name")
    description: str | None = Field(None, max_length=5000)
    price: Decimal = Field(..., ge=Decimal("0"), decimal_places=2)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    quantity: int = Field(default=0, ge=0)
    weight: float | None = Field(None, ge=0, description="Weight in kg")
    dimensions: dict[str, float] | None = None
    tags: list[str] = Field(default_factory=list, max_length=20)
    is_active: bool = True
    category_ids: set[int] = Field(default_factory=set)

    @field_validator("sku")
    @classmethod
    def validate_sku(cls, v: str) -> str:
        """Validate and normalize SKU."""
        return v.upper().strip()

    @field_validator("price", mode="before")
    @classmethod
    def parse_price(cls, v: Any) -> Decimal:
        """Parse price from various formats."""
        if isinstance(v, str):
            # Remove currency symbols and commas
            v = re.sub(r"[^\d.]", "", v)
        return Decimal(str(v))

    @field_validator("tags", each_item=True)
    @classmethod
    def normalize_tags(cls, v: str) -> str:
        """Normalize each tag."""
        return v.lower().strip()

    @model_validator(mode="after")
    @classmethod
    def validate_dimensions(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Validate dimensions consistency."""
        dims = values.get("dimensions")
        if dims:
            required = {"length", "width", "height"}
            if not required.issubset(dims.keys()):
                raise ValueError(f"Dimensions must include: {required}")
        return values


class Product(BaseItem):
    """Extended product model with more fields."""

    brand: str | None = Field(None, max_length=100)
    manufacturer: str | None = Field(None, max_length=200)
    model_number: str | None = Field(None, max_length=100)
    warranty_months: int = Field(default=0, ge=0, le=120)
    related_products: list[str] = Field(default_factory=list, description="Related SKUs")
    variants: list[dict[str, Any]] = Field(default_factory=list)

    # Cross-reference to Category
    category: Category | None = None

    @field_validator("related_products", each_item=True)
    @classmethod
    def validate_related_sku(cls, v: str) -> str:
        """Validate related product SKUs."""
        if not re.match(r"^[A-Z0-9-]+$", v.upper()):
            raise ValueError(f"Invalid related SKU format: {v}")
        return v.upper()


class Category(AuditableModel):
    """Product category with self-referential structure."""

    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    description: str | None = Field(None, max_length=1000)
    parent_id: int | None = None
    level: int = Field(default=0, ge=0, le=10)
    is_active: bool = True

    # Self-reference and cross-reference
    parent: Category | None = None
    children: list[Category] = Field(default_factory=list)
    products: list[Product] = Field(default_factory=list)

    @field_validator("slug", mode="before")
    @classmethod
    def generate_slug(cls, v: str | None, values: dict[str, Any]) -> str:
        """Generate slug from name if not provided."""
        if not v and "name" in values:
            return re.sub(r"[^a-z0-9]+", "-", values["name"].lower()).strip("-")
        return v.lower() if v else ""

    @model_validator(mode="before")
    @classmethod
    def validate_hierarchy(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Validate category hierarchy."""
        if values.get("parent_id") and values.get("level", 0) == 0:
            raise ValueError("Category with parent must have level > 0")
        return values


# ============================================================================
# USER AND AUTHENTICATION MODELS
# ============================================================================

class UserProfile(AuditableModel):
    """Complex user profile with nested models."""

    user_id: UUID
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    email: str = Field(..., pattern=r"^[\w.-]+@[\w.-]+\.\w+$")
    display_name: str | None = Field(None, max_length=100)
    bio: str | None = Field(None, max_length=500)
    avatar_url: str | None = None
    role: UserRole = UserRole.USER
    permissions: set[str] = Field(default_factory=set)

    # Nested models
    addresses: list[Address] = Field(default_factory=list, max_length=10)
    contact: ContactInfo | None = None

    # Preferences as nested dict
    preferences: dict[str, Any] = Field(default_factory=dict)

    # Audit
    last_login: datetime | None = None
    login_count: int = Field(default=0, ge=0)
    is_active: bool = True
    is_verified: bool = False

    # Private attributes
    _password_hash: str = ""
    _session_tokens: list[str] = []

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format and reserved words."""
        reserved = {"admin", "root", "system", "api", "null", "undefined"}
        if v.lower() in reserved:
            raise ValueError(f"Username '{v}' is reserved")
        return v.lower()

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Validate and normalize email."""
        return v.lower().strip()

    @field_validator("addresses")
    @classmethod
    def validate_addresses(cls, v: list[Address]) -> list[Address]:
        """Ensure only one primary address."""
        primary_count = sum(1 for addr in v if addr.is_primary)
        if primary_count > 1:
            raise ValueError("Only one primary address allowed")
        return v

    @field_validator("permissions", mode="before")
    @classmethod
    def parse_permissions(cls, v: Any) -> set[str]:
        """Parse permissions from various formats."""
        if isinstance(v, str):
            return set(v.split(","))
        if isinstance(v, (list, tuple)):
            return set(v)
        return v

    @model_validator(mode="before")
    @classmethod
    def validate_profile(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Cross-field validation for profile."""
        role = values.get("role")
        permissions = values.get("permissions", set())

        # Admins get all permissions
        if role == UserRole.ADMIN:
            permissions.update(["read", "write", "delete", "admin"])
            values["permissions"] = permissions

        # Guests have limited permissions
        if role == UserRole.GUEST:
            values["permissions"] = {"read"}

        return values


# ============================================================================
# ORDER AND PAYMENT MODELS
# ============================================================================

class OrderItem(BaseModel):
    """Individual item in an order."""

    product_sku: str = Field(..., pattern=r"^[A-Z0-9-]+$")
    product_name: str
    quantity: int = Field(..., ge=1)
    unit_price: Decimal = Field(..., ge=Decimal("0"))
    discount: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    tax: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))

    # Computed fields
    subtotal: Decimal | None = None
    total: Decimal | None = None
    model_config = ConfigDict(from_attributes=True, validate_assignment=True)

    @field_validator("subtotal", always=True)
    @classmethod
    def compute_subtotal(cls, v: Decimal | None, values: dict[str, Any]) -> Decimal:
        """Compute subtotal from quantity and unit_price."""
        qty = values.get("quantity", 0)
        price = values.get("unit_price", Decimal("0"))
        return Decimal(qty) * price

    @field_validator("total", always=True)
    @classmethod
    def compute_total(cls, v: Decimal | None, values: dict[str, Any]) -> Decimal:
        """Compute total including tax and discount."""
        subtotal = values.get("subtotal", Decimal("0"))
        discount = values.get("discount", Decimal("0"))
        tax = values.get("tax", Decimal("0"))
        return subtotal - discount + tax


class PaymentInfo(BaseModel):
    """Payment information with sensitive data handling."""

    method: PaymentMethod
    card_last_four: str | None = Field(None, pattern=r"^\d{4}$")
    card_brand: str | None = None
    billing_address: Address | None = None
    transaction_id: str | None = None
    authorized_amount: Decimal = Field(..., ge=Decimal("0"))
    captured_amount: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    refunded_amount: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    currency: str = Field(default="USD", min_length=3, max_length=3)

    # Private - never serialized
    _full_card_number: str = ""
    _cvv: str = ""
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    @field_validator("card_last_four")
    @classmethod
    def validate_card_requirement(cls, v: str | None, values: dict[str, Any]) -> str | None:
        """Validate card info is present for card payments."""
        method = values.get("method")
        if method in (PaymentMethod.CREDIT_CARD, PaymentMethod.DEBIT_CARD):
            if not v:
                raise ValueError("Card last four digits required for card payments")
        return v

    @model_validator(mode="before")
    @classmethod
    def validate_amounts(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Validate payment amounts are consistent."""
        authorized = values.get("authorized_amount", Decimal("0"))
        captured = values.get("captured_amount", Decimal("0"))
        refunded = values.get("refunded_amount", Decimal("0"))

        if captured > authorized:
            raise ValueError("Captured amount cannot exceed authorized amount")
        if refunded > captured:
            raise ValueError("Refunded amount cannot exceed captured amount")

        return values


class Order(AuditableModel):
    """Complex order model with nested items and payments."""

    order_number: str = Field(..., pattern=r"^ORD-\d{10}$")
    customer_id: UUID
    customer_email: str = Field(..., pattern=r"^[\w.-]+@[\w.-]+\.\w+$")

    # Nested models
    items: list[OrderItem] = Field(..., min_length=1)
    shipping_address: Address
    billing_address: Address | None = None
    payment: PaymentInfo

    # Order details
    status: OrderStatus = OrderStatus.PENDING
    notes: str | None = Field(None, max_length=1000)

    # Computed totals
    subtotal: Decimal | None = None
    discount_total: Decimal | None = None
    tax_total: Decimal | None = None
    shipping_cost: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    grand_total: Decimal | None = None

    # Timestamps
    ordered_at: datetime = Field(default_factory=datetime.utcnow)
    shipped_at: datetime | None = None
    delivered_at: datetime | None = None
    cancelled_at: datetime | None = None

    @field_validator("billing_address", always=True)
    @classmethod
    def default_billing_address(
        cls, v: Address | None, values: dict[str, Any]
    ) -> Address | None:
        """Use shipping address as billing if not provided."""
        if v is None:
            return values.get("shipping_address")
        return v

    @field_validator("subtotal", always=True)
    @classmethod
    def compute_subtotal(cls, v: Decimal | None, values: dict[str, Any]) -> Decimal:
        """Compute order subtotal from items."""
        items = values.get("items", [])
        return sum(item.subtotal or Decimal("0") for item in items)

    @field_validator("discount_total", always=True)
    @classmethod
    def compute_discount_total(cls, v: Decimal | None, values: dict[str, Any]) -> Decimal:
        """Compute total discount from items."""
        items = values.get("items", [])
        return sum(item.discount for item in items)

    @field_validator("tax_total", always=True)
    @classmethod
    def compute_tax_total(cls, v: Decimal | None, values: dict[str, Any]) -> Decimal:
        """Compute total tax from items."""
        items = values.get("items", [])
        return sum(item.tax for item in items)

    @field_validator("grand_total", always=True)
    @classmethod
    def compute_grand_total(cls, v: Decimal | None, values: dict[str, Any]) -> Decimal:
        """Compute grand total."""
        subtotal = values.get("subtotal", Decimal("0"))
        discount = values.get("discount_total", Decimal("0"))
        tax = values.get("tax_total", Decimal("0"))
        shipping = values.get("shipping_cost", Decimal("0"))
        return subtotal - discount + tax + shipping

    @model_validator(mode="before")
    @classmethod
    def generate_order_number(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Generate order number if not provided."""
        if "order_number" not in values:
            import random
            values["order_number"] = f"ORD-{random.randint(1000000000, 9999999999)}"
        return values

    @model_validator(mode="before")
    @classmethod
    def validate_order_status_timestamps(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Validate status-timestamp consistency."""
        status = values.get("status")

        if status == OrderStatus.SHIPPED and not values.get("shipped_at"):
            values["shipped_at"] = datetime.utcnow()

        if status == OrderStatus.DELIVERED and not values.get("delivered_at"):
            values["delivered_at"] = datetime.utcnow()

        if status == OrderStatus.CANCELLED and not values.get("cancelled_at"):
            values["cancelled_at"] = datetime.utcnow()

        return values


# ============================================================================
# CUSTOM __init__ MODELS
# ============================================================================

class ConfigurableModel(BaseModel):
    """Model with custom __init__ that accepts extra configuration."""

    name: str
    value: Any
    metadata: dict[str, Any] = Field(default_factory=dict)
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

    def __init__(self, name: str, value: Any, *, logger: Any = None, **kwargs: Any) -> None:
        """Custom init that accepts a logger."""
        super().__init__(name=name, value=value, **kwargs)
        self._logger = logger

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate name is not empty."""
        if not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()


class LazyLoadModel(BaseModel):
    """Model that demonstrates lazy loading pattern."""

    id: int
    name: str
    _related_data: dict[str, Any] | None = None
    _loaded: bool = False
    model_config = ConfigDict(from_attributes=True)

    def __init__(self, **data: Any) -> None:
        """Initialize with lazy loading support."""
        super().__init__(**data)
        self._loaded = False
        self._related_data = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: int) -> int:
        """Validate ID is positive."""
        if v <= 0:
            raise ValueError("ID must be positive")
        return v


# ============================================================================
# COMPLEX INHERITANCE CHAIN
# ============================================================================

class TimestampMixin(BaseModel):
    """Mixin for timestamp fields."""

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)

    @field_validator("updated_at", always=True, mode="after")
    @classmethod
    def auto_update_timestamp(cls, v: datetime | None) -> datetime:
        """Auto-set updated_at to now."""
        return v or datetime.utcnow()


class SoftDeleteMixin(BaseModel):
    """Mixin for soft delete functionality."""

    is_deleted: bool = False
    deleted_at: datetime | None = None
    deleted_by: str | None = None
    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def validate_soft_delete(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Ensure deleted_at is set when is_deleted is True."""
        if values.get("is_deleted") and not values.get("deleted_at"):
            values["deleted_at"] = datetime.utcnow()
        return values


class VersionedMixin(BaseModel):
    """Mixin for optimistic locking."""

    version: int = Field(default=1, ge=1)
    last_modified_by: str | None = None
    model_config = ConfigDict(from_attributes=True)


class FullAuditModel(TimestampMixin, SoftDeleteMixin, VersionedMixin):
    """Model combining all mixins - demonstrates multiple inheritance."""

    id: int
    name: str
    description: str | None = None
    model_config = ConfigDict(from_attributes=True, validate_assignment=True, extra="forbid", frozen=True, use_enum_values=True)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate name is not empty."""
        return v.strip()

    @model_validator(mode="before")
    @classmethod
    def final_validation(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Final cross-field validation."""
        if values.get("is_deleted") and not values.get("deleted_by"):
            raise ValueError("deleted_by is required when is_deleted is True")
        return values


# ============================================================================
# FORWARD REFERENCES UPDATE
# ============================================================================

# Update forward references for cross-referential models
Product.model_rebuild()
Category.model_rebuild()


# ============================================================================
# USAGE EXAMPLES (for testing the migration)
# ============================================================================

def example_usage() -> None:
    """Example usage demonstrating various Pydantic v1 features."""

    # Create instances using .dict() and .json()
    address = Address(
        street="123 Main St",
        city="Springfield",
        state="IL",
        postal_code="62701",
    )

    # v1 method calls that should be migrated
    address_dict = address.model_dump()
    address_json = address.model_dump_json()

    # .parse_obj() usage
    address2 = Address.model_validate({
        "street": "456 Oak Ave",
        "city": "Chicago",
        "state": "IL",
        "postal_code": "60601",
    })

    # .schema() usage
    schema = Address.model_json_schema()

    # __fields__ access
    fields = Address.model_fields

    # Generic model usage
    paginated: PaginatedResponse[Address] = PaginatedResponse(
        items=[address, address2],
        total=2,
        page=1,
        page_size=20,
    )

    paginated_dict = paginated.model_dump()
    paginated_json = paginated.model_dump_json()

    # Order creation
    order = Order(
        customer_id=UUID("12345678-1234-5678-1234-567812345678"),
        customer_email="test@example.com",
        items=[
            OrderItem(
                product_sku="ABC-123",
                product_name="Test Product",
                quantity=2,
                unit_price=Decimal("29.99"),
            )
        ],
        shipping_address=address,
        payment=PaymentInfo(
            method=PaymentMethod.CREDIT_CARD,
            card_last_four="1234",
            authorized_amount=Decimal("59.98"),
        ),
    )

    order_dict = order.model_dump()
    order_json = order.model_dump_json()
    order_schema = Order.model_json_schema()


if __name__ == "__main__":
    example_usage()
