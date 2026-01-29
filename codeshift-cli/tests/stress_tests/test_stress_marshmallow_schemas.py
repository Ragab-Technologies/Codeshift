"""
Marshmallow 2.x -> 3.x Stress Test File

This file contains VERY complex Marshmallow 2.x code patterns that need to be migrated to 3.x.
It includes:
- 10+ nested schemas with deep hierarchy
- Custom fields with serialize/deserialize methods
- Schema inheritance (multiple levels)
- dump().data and load().data patterns
- Strict mode migration
- many=True patterns
- Pre/post load/dump hooks with pass_many
- Nested field with many=True
- Method fields and Function fields
- Validation with custom validators
- Schema meta options (strict, json_module)
- Context passing between schemas
- Error handling and error messages
- Two-way nesting (circular references)
- Dynamic schema generation
"""

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any

import ujson
from marshmallow import (
    Schema,
    ValidationError,
    fields,
    post_dump,
    post_load,
    pre_dump,
    pre_load,
    validates,
    validates_schema,
)

# ==============================================================================
# SECTION 1: Basic Schema with Strict Mode and Meta Options
# ==============================================================================

class BaseModelSchema(Schema):
    """Base schema with strict mode and json_module (v2 patterns)."""

    class Meta:
        strict = True
        json_module = ujson
        ordered = True

    id = fields.Integer(dump_to="resourceId")
    created_at = fields.DateTime(missing=None)
    updated_at = fields.DateTime(missing=None)


# ==============================================================================
# SECTION 2: Custom Fields with serialize/deserialize
# ==============================================================================

class EnumField(fields.Field):
    """Custom enum field with fail() calls (v2 pattern)."""

    default_error_messages = {
        "invalid": "Invalid enum value: {value}",
        "unknown": "Unknown enum member: {name}",
    }

    def __init__(self, enum_class, **kwargs):
        self.enum_class = enum_class
        super().__init__(**kwargs)

    def _serialize(self, value, attr, obj, **kwargs):
        if value is None:
            return None
        if isinstance(value, self.enum_class):
            return value.value
        self.fail("invalid", value=value)

    def _deserialize(self, value, attr, data, **kwargs):
        if value is None:
            return None
        try:
            return self.enum_class(value)
        except ValueError:
            self.fail("invalid", value=value)


class MoneyField(fields.Field):
    """Custom money field with complex serialization."""

    default_error_messages = {
        "invalid_format": "Money must be a dict with 'amount' and 'currency'",
        "invalid_amount": "Amount must be a valid decimal",
        "missing_currency": "Currency code is required",
    }

    def _serialize(self, value, attr, obj, **kwargs):
        if value is None:
            return None
        return {
            "amount": str(value["amount"]),
            "currency": value["currency"],
        }

    def _deserialize(self, value, attr, data, **kwargs):
        if value is None:
            return None
        if not isinstance(value, dict):
            self.fail("invalid_format")
        if "amount" not in value:
            self.fail("invalid_format")
        if "currency" not in value:
            self.fail("missing_currency")
        try:
            return {
                "amount": Decimal(value["amount"]),
                "currency": value["currency"],
            }
        except (ValueError, TypeError):
            self.fail("invalid_amount")


class SlugField(fields.String):
    """Custom slug field that normalizes input."""

    default_error_messages = {
        "invalid_slug": "Slug contains invalid characters",
    }

    def _deserialize(self, value, attr, data, **kwargs):
        value = super()._deserialize(value, attr, data, **kwargs)
        if value:
            # Normalize the slug
            normalized = value.lower().replace(" ", "-")
            if not normalized.replace("-", "").isalnum():
                self.fail("invalid_slug")
            return normalized
        return value


# ==============================================================================
# SECTION 3: Enums for Custom Fields
# ==============================================================================

class UserStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    BANNED = "banned"


class OrderStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class PaymentMethod(Enum):
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    PAYPAL = "paypal"
    BANK_TRANSFER = "bank_transfer"
    CRYPTO = "crypto"


# ==============================================================================
# SECTION 4: Deeply Nested Schemas (10+ levels)
# ==============================================================================

class GeoPointSchema(Schema):
    """Level 10: Geographic point."""
    class Meta:
        strict = True

    latitude = fields.Float(load_from="lat")
    longitude = fields.Float(load_from="lng")


class CoordinateSystemSchema(Schema):
    """Level 9: Coordinate system with origin point."""
    class Meta:
        strict = True

    origin = fields.Nested(GeoPointSchema, missing=None)
    reference_system = fields.String(missing="WGS84", load_from="refSystem")


class LocationMetadataSchema(Schema):
    """Level 8: Location metadata."""
    class Meta:
        strict = True
        json_module = ujson

    coordinates = fields.Nested(CoordinateSystemSchema)
    accuracy = fields.Float(missing=0.0)
    timestamp = fields.DateTime(load_from="capturedAt")


class AddressSchema(Schema):
    """Level 7: Address with location metadata."""
    class Meta:
        strict = True

    street = fields.String(load_from="streetAddress")
    city = fields.String()
    state = fields.String(missing="")
    country = fields.String(default="US", dump_to="countryCode")
    postal_code = fields.String(load_from="zipCode", dump_to="postalCode")
    location_metadata = fields.Nested(LocationMetadataSchema, missing=None)


class ContactInfoSchema(Schema):
    """Level 6: Contact information."""
    class Meta:
        strict = True

    phone = fields.String(missing=None, load_from="phoneNumber")
    email = fields.Email()
    fax = fields.String(missing=None)
    address = fields.Nested(AddressSchema)


class DepartmentSchema(Schema):
    """Level 5: Department within organization."""
    class Meta:
        strict = True

    name = fields.String()
    code = fields.String(load_from="deptCode", dump_to="departmentCode")
    contact = fields.Nested(ContactInfoSchema)
    employee_count = fields.Integer(missing=0, load_from="numEmployees")


class OrganizationSchema(Schema):
    """Level 4: Organization with departments."""
    class Meta:
        strict = True
        json_module = ujson

    name = fields.String()
    tax_id = fields.String(load_from="taxIdentifier", dump_to="taxId")
    departments = fields.Nested(DepartmentSchema, many=True, missing=[])
    headquarters = fields.Nested(AddressSchema)


class EmploymentHistorySchema(Schema):
    """Level 3: Employment history entry."""
    class Meta:
        strict = True

    organization = fields.Nested(OrganizationSchema)
    position = fields.String()
    start_date = fields.Date(load_from="startedAt")
    end_date = fields.Date(missing=None, load_from="endedAt")
    salary = MoneyField(missing=None)


class UserProfileSchema(Schema):
    """Level 2: User profile with employment history."""
    class Meta:
        strict = True

    bio = fields.String(missing="")
    website = fields.URL(missing=None)
    employment_history = fields.Nested(EmploymentHistorySchema, many=True, missing=[])
    current_employer = fields.Nested(OrganizationSchema, missing=None)


class UserSchema(BaseModelSchema):
    """Level 1: User schema inheriting from BaseModelSchema."""

    class Meta:
        strict = True
        json_module = ujson

    username = fields.String(load_from="userName")
    email = fields.Email()
    status = EnumField(UserStatus, missing=UserStatus.PENDING)
    profile = fields.Nested(UserProfileSchema)

    @post_load(pass_many=True)
    def process_users(self, data, many, **extra):
        """Post-load hook with pass_many pattern."""
        if many:
            return [self._process_single(d) for d in data]
        return self._process_single(data)

    def _process_single(self, data):
        data["processed"] = True
        return data


# ==============================================================================
# SECTION 5: Schema Inheritance Chain
# ==============================================================================

class BaseAuditSchema(Schema):
    """Base audit schema."""
    class Meta:
        strict = True

    created_by = fields.String(load_from="createdBy")
    modified_by = fields.String(missing=None, load_from="modifiedBy")
    audit_log = fields.List(fields.Dict(), missing=[])


class BaseEntitySchema(BaseAuditSchema):
    """Entity with audit trail."""
    class Meta:
        strict = True
        json_module = ujson

    id = fields.UUID()
    name = fields.String()
    description = fields.String(missing="")

    @validates("name")
    def validate_name(self, value):
        if len(value) < 2:
            raise ValidationError("Name must be at least 2 characters")


class ProductCategorySchema(BaseEntitySchema):
    """Product category inheriting from entity."""

    slug = SlugField()
    parent_id = fields.UUID(missing=None, load_from="parentId")
    display_order = fields.Integer(missing=0, load_from="displayOrder")


class ProductSchema(BaseEntitySchema):
    """Product with category."""

    sku = fields.String()
    price = MoneyField()
    category = fields.Nested(ProductCategorySchema)
    tags = fields.List(fields.String(), missing=[])

    @post_load
    def make_product(self, data, **kwargs):
        data["type"] = "product"
        return data


# ==============================================================================
# SECTION 6: Two-Way Nesting (Circular References)
# ==============================================================================

class CommentSchema(Schema):
    """Comment that can reference a post and replies."""
    class Meta:
        strict = True

    id = fields.Integer()
    content = fields.String()
    author_id = fields.Integer(load_from="authorId")
    # Forward reference to avoid circular import
    replies = fields.Nested(lambda: CommentSchema, many=True, missing=[])

    @post_dump(pass_many=True)
    def add_metadata(self, data, many, **extra):
        """Add metadata after dump."""
        if many:
            return {"comments": data, "count": len(data)}
        return data


class PostSchema(Schema):
    """Post with comments - creates circular reference with CommentSchema."""
    class Meta:
        strict = True
        json_module = ujson

    id = fields.Integer()
    title = fields.String()
    body = fields.String()
    author = fields.Nested(UserSchema, only=("id", "username", "email"))
    comments = fields.Nested(CommentSchema, many=True, missing=[])
    related_posts = fields.Nested(lambda: PostSchema, many=True, exclude=("related_posts",), missing=[])

    @pre_load(pass_many=True)
    def preprocess_posts(self, data, many, **extra):
        """Preprocess posts before loading."""
        if many:
            return [self._preprocess_single(d) for d in data]
        return self._preprocess_single(data)

    def _preprocess_single(self, data):
        if "body" not in data and "content" in data:
            data["body"] = data.pop("content")
        return data


# ==============================================================================
# SECTION 7: Method Fields and Function Fields
# ==============================================================================

def calculate_age(user):
    """Function for Function field."""
    if user.get("birth_date"):
        today = date.today()
        birth = user["birth_date"]
        return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
    return None


def format_full_name(user):
    """Format user's full name."""
    return f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()


class UserDetailSchema(Schema):
    """User detail schema with Method and Function fields."""
    class Meta:
        strict = True

    id = fields.Integer()
    first_name = fields.String(load_from="firstName")
    last_name = fields.String(load_from="lastName")
    birth_date = fields.Date(missing=None, load_from="birthDate")

    # Method fields
    full_name = fields.Method("get_full_name", dump_only=True)
    age = fields.Method("get_age", dump_only=True)

    # Function fields
    computed_name = fields.Function(lambda obj: format_full_name(obj), dump_only=True)
    computed_age = fields.Function(lambda obj: calculate_age(obj), dump_only=True)

    # Field with both serialization and deserialization
    nickname = fields.Method("get_nickname", "set_nickname")

    def get_full_name(self, obj):
        return format_full_name(obj)

    def get_age(self, obj):
        return calculate_age(obj)

    def get_nickname(self, obj):
        return obj.get("nickname", "").upper()

    def set_nickname(self, value):
        return value.lower() if value else None


# ==============================================================================
# SECTION 8: Complex Validation with Custom Validators
# ==============================================================================

class PasswordPolicySchema(Schema):
    """Schema with complex validation rules."""
    class Meta:
        strict = True

    min_length = fields.Integer(missing=8)
    require_uppercase = fields.Boolean(missing=True)
    require_lowercase = fields.Boolean(missing=True)
    require_digits = fields.Boolean(missing=True)
    require_special_chars = fields.Boolean(missing=False)


class RegistrationSchema(Schema):
    """Registration schema with cross-field validation."""
    class Meta:
        strict = True
        json_module = ujson

    username = fields.String(load_from="userName")
    email = fields.Email()
    password = fields.String(load_only=True)
    confirm_password = fields.String(load_only=True, load_from="confirmPassword")
    terms_accepted = fields.Boolean(missing=False, load_from="termsAccepted")
    newsletter = fields.Boolean(missing=False)

    password_policy = fields.Nested(PasswordPolicySchema, missing=None)

    @validates("username")
    def validate_username(self, value):
        if len(value) < 3:
            raise ValidationError("Username must be at least 3 characters")
        if not value[0].isalpha():
            raise ValidationError("Username must start with a letter")

    @validates("password")
    def validate_password(self, value):
        if len(value) < 8:
            raise ValidationError("Password must be at least 8 characters")

    @validates_schema(pass_many=True)
    def validate_schema(self, data, many, partial, **extra):
        """Cross-field validation with pass_many."""
        if many:
            for item in data:
                self._validate_single(item)
        else:
            self._validate_single(data)

    def _validate_single(self, data):
        if data.get("password") != data.get("confirm_password"):
            raise ValidationError("Passwords do not match", field_names=["password"])
        if not data.get("terms_accepted"):
            raise ValidationError("You must accept the terms", field_names=["terms_accepted"])


# ==============================================================================
# SECTION 9: Order Processing with Multiple Nested Schemas
# ==============================================================================

class LineItemSchema(Schema):
    """Order line item."""
    class Meta:
        strict = True

    product = fields.Nested(ProductSchema)
    quantity = fields.Integer()
    unit_price = MoneyField(load_from="unitPrice")
    discount = fields.Float(missing=0.0)

    @post_load
    def calculate_total(self, data, **kwargs):
        """Calculate line item total."""
        if data.get("unit_price") and data.get("quantity"):
            amount = data["unit_price"]["amount"]
            quantity = data["quantity"]
            discount = data.get("discount", 0)
            data["total"] = amount * quantity * (1 - discount)
        return data


class ShippingInfoSchema(Schema):
    """Shipping information."""
    class Meta:
        strict = True

    address = fields.Nested(AddressSchema)
    method = fields.String(missing="standard")
    tracking_number = fields.String(missing=None, load_from="trackingNumber")
    estimated_delivery = fields.Date(missing=None, load_from="estimatedDelivery")


class PaymentInfoSchema(Schema):
    """Payment information."""
    class Meta:
        strict = True
        json_module = ujson

    method = EnumField(PaymentMethod)
    amount = MoneyField()
    transaction_id = fields.String(missing=None, load_from="transactionId")
    processed_at = fields.DateTime(missing=None, load_from="processedAt")
    billing_address = fields.Nested(AddressSchema, missing=None, load_from="billingAddress")


class OrderSchema(BaseAuditSchema):
    """Complex order schema with multiple nested schemas."""

    class Meta:
        strict = True
        json_module = ujson

    order_number = fields.String(load_from="orderNumber", dump_to="orderNum")
    status = EnumField(OrderStatus, missing=OrderStatus.PENDING)
    customer = fields.Nested(UserSchema)
    line_items = fields.Nested(LineItemSchema, many=True, load_from="lineItems")
    shipping = fields.Nested(ShippingInfoSchema, missing=None)
    payment = fields.Nested(PaymentInfoSchema)

    subtotal = MoneyField(dump_only=True)
    tax = MoneyField(dump_only=True)
    total = MoneyField(dump_only=True)

    notes = fields.String(missing="")

    @pre_dump(pass_many=True)
    def prepare_for_dump(self, data, many, **extra):
        """Calculate totals before dumping."""
        if many:
            return [self._calculate_totals(d) for d in data]
        return self._calculate_totals(data)

    def _calculate_totals(self, data):
        if "line_items" in data:
            subtotal = sum(item.get("total", 0) for item in data["line_items"])
            data["subtotal"] = {"amount": subtotal, "currency": "USD"}
            data["tax"] = {"amount": subtotal * Decimal("0.08"), "currency": "USD"}
            data["total"] = {"amount": subtotal * Decimal("1.08"), "currency": "USD"}
        return data

    @post_load
    def finalize_order(self, data, **kwargs):
        """Finalize order after loading."""
        data["finalized"] = True
        return data

    @validates_schema
    def validate_order(self, data, **kwargs):
        """Validate the entire order."""
        if not data.get("line_items"):
            raise ValidationError("Order must have at least one line item")


# ==============================================================================
# SECTION 10: Dynamic Schema Generation
# ==============================================================================

def create_dynamic_schema(field_definitions: dict[str, Any]) -> type:
    """Dynamically create a schema based on field definitions."""

    field_mapping = {
        "string": fields.String,
        "integer": fields.Integer,
        "float": fields.Float,
        "boolean": fields.Boolean,
        "date": fields.Date,
        "datetime": fields.DateTime,
        "email": fields.Email,
        "url": fields.URL,
        "uuid": fields.UUID,
    }

    schema_fields = {}

    for name, config in field_definitions.items():
        field_type = config.get("type", "string")
        field_class = field_mapping.get(field_type, fields.String)

        # Build field kwargs using v2 patterns
        field_kwargs = {}
        if "default" in config:
            field_kwargs["default"] = config["default"]
        if "missing" in config:
            field_kwargs["missing"] = config["missing"]
        if "load_from" in config:
            field_kwargs["load_from"] = config["load_from"]
        if "dump_to" in config:
            field_kwargs["dump_to"] = config["dump_to"]
        if "required" in config:
            field_kwargs["required"] = config["required"]

        schema_fields[name] = field_class(**field_kwargs)

    # Create the schema class dynamically
    schema_class = type(
        "DynamicSchema",
        (Schema,),
        {
            **schema_fields,
            "Meta": type("Meta", (), {"strict": True}),
        }
    )

    return schema_class


# ==============================================================================
# SECTION 11: Context Passing Between Schemas
# ==============================================================================

class LocalizedStringSchema(Schema):
    """Schema that uses context for localization."""
    class Meta:
        strict = True

    key = fields.String()
    translations = fields.Dict(keys=fields.String(), values=fields.String())

    @post_dump
    def localize(self, data, **kwargs):
        """Return localized string based on context."""
        lang = self.context.get("language", "en")
        translations = data.get("translations", {})
        data["value"] = translations.get(lang, translations.get("en", data["key"]))
        return data


class LocalizedContentSchema(Schema):
    """Content with localized fields."""
    class Meta:
        strict = True
        json_module = ujson

    id = fields.Integer()
    title = fields.Nested(LocalizedStringSchema)
    description = fields.Nested(LocalizedStringSchema, missing=None)
    tags = fields.Nested(LocalizedStringSchema, many=True, missing=[])

    @post_dump
    def apply_context(self, data, **kwargs):
        """Pass context to nested schemas."""
        # Context is automatically passed in v3
        return data


# ==============================================================================
# SECTION 12: Error Handling Patterns
# ==============================================================================

class StrictValidationSchema(Schema):
    """Schema demonstrating error handling patterns."""
    class Meta:
        strict = True

    required_field = fields.String()
    validated_field = fields.Integer()

    @validates("validated_field")
    def validate_range(self, value):
        if value < 0 or value > 100:
            raise ValidationError("Value must be between 0 and 100")


class ErrorCollectorSchema(Schema):
    """Schema that collects multiple errors."""
    class Meta:
        strict = True

    items = fields.Nested(StrictValidationSchema, many=True)

    @validates_schema
    def collect_errors(self, data, **kwargs):
        """Collect all validation errors."""
        errors = []
        for i, item in enumerate(data.get("items", [])):
            if not item.get("required_field"):
                errors.append(f"Item {i}: required_field is missing")
        if errors:
            raise ValidationError(errors)


# ==============================================================================
# SECTION 13: Usage Examples with dump().data and load().data patterns
# ==============================================================================

def example_usage():
    """Example usage with v2 patterns that need migration."""

    # Create schemas with strict=True
    user_schema = UserSchema(strict=True)
    users_schema = UserSchema(strict=True, many=True)
    order_schema = OrderSchema(strict=True)

    # Sample user data
    user_data = {
        "userName": "john_doe",
        "email": "john@example.com",
        "profile": {
            "bio": "Software developer",
            "website": "https://johndoe.com",
            "employment_history": [],
        }
    }

    # Load with .data access (v2 pattern)
    result = user_schema.load(user_data)
    user = result.data

    # Dump with .data access (v2 pattern)
    output = user_schema.dump(user)
    json_data = output.data

    # dumps with .data access
    json_string = user_schema.dumps(user).data

    # loads with .data access
    loaded_user = user_schema.loads(json_string).data

    # Multiple users with many=True
    users_data = [user_data, user_data]
    users_result = users_schema.load(users_data)
    users = users_result.data

    # Dynamic schema creation and usage
    DynamicSchema = create_dynamic_schema({
        "name": {"type": "string", "missing": "default"},
        "age": {"type": "integer", "load_from": "userAge"},
        "email": {"type": "email", "dump_to": "emailAddress"},
    })
    dynamic_schema = DynamicSchema(strict=True)

    dynamic_data = {"name": "Test", "userAge": 25, "email": "test@example.com"}
    dynamic_result = dynamic_schema.load(dynamic_data)
    dynamic_obj = dynamic_result.data

    # Context passing
    localized_schema = LocalizedContentSchema(strict=True)
    localized_schema.context = {"language": "es"}

    content_data = {
        "id": 1,
        "title": {
            "key": "greeting",
            "translations": {"en": "Hello", "es": "Hola", "fr": "Bonjour"}
        }
    }
    localized_result = localized_schema.load(content_data)
    localized_content = localized_result.data

    return {
        "user": user,
        "json_data": json_data,
        "users": users,
        "dynamic_obj": dynamic_obj,
        "localized_content": localized_content,
    }


def process_order(order_json: str) -> dict:
    """Process an order with validation and transformation."""
    schema = OrderSchema(strict=True)

    # Load the order
    result = schema.loads(order_json)
    order = result.data

    # Validate and process
    if order.get("status") == OrderStatus.PENDING:
        order["status"] = OrderStatus.PROCESSING

    # Dump back to dict
    output = schema.dump(order)
    return output.data


def batch_process_users(users_json: str) -> list[dict]:
    """Batch process users with many=True."""
    schema = UserSchema(strict=True, many=True)

    result = schema.loads(users_json)
    users = result.data

    processed = []
    for user in users:
        output = UserSchema(strict=True).dump(user)
        processed.append(output.data)

    return processed


# ==============================================================================
# SECTION 14: Complex Nested with all field parameter patterns
# ==============================================================================

class CompleteFieldTestSchema(Schema):
    """Schema testing all field parameter migrations."""
    class Meta:
        strict = True
        json_module = ujson

    # missing -> load_default
    field_with_missing = fields.String(missing="default_value")
    nullable_missing = fields.String(missing=None)
    list_missing = fields.List(fields.Integer(), missing=[])
    dict_missing = fields.Dict(missing={})

    # default -> dump_default
    field_with_default = fields.String(default="dump_default")
    nullable_default = fields.String(default=None)

    # load_from -> data_key
    loaded_from_key = fields.String(load_from="sourceKey")
    loaded_from_camel = fields.String(load_from="camelCaseKey")

    # dump_to -> data_key
    dumped_to_key = fields.Integer(dump_to="targetKey")
    dumped_to_camel = fields.Integer(dump_to="camelCaseOutput")

    # Combined patterns
    complex_field = fields.String(
        missing="default",
        load_from="inputField",
    )
    another_complex = fields.Integer(
        missing=0,
        dump_to="outputNumber",
    )

    # Nested with various patterns
    nested_with_missing = fields.Nested(AddressSchema, missing=None)
    nested_list_with_missing = fields.Nested(
        ContactInfoSchema,
        many=True,
        missing=[],
        load_from="contacts"
    )


# ==============================================================================
# If run directly, execute examples
# ==============================================================================

if __name__ == "__main__":

    print("Running Marshmallow 2.x stress test examples...")

    try:
        results = example_usage()
        print("Examples executed successfully!")
        print(f"User: {results['user']}")
    except Exception as e:
        print(f"Error running examples: {e}")
