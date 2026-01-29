"""
Stress Test: Complex attrs 20.x -> 23.x Migration

This file contains 15+ complex attrs classes using legacy patterns from attrs 20.x
that should be migrated to the modern attrs 23.x style.

Test coverage includes:
- @attr.s and @attr.ib patterns (legacy style)
- New @attrs.define style (for comparison - should NOT be transformed)
- Validators (instance_of, in_, optional, and_, deep_iterable, deep_mapping)
- Converters (optional, pipe, to_bool)
- Factory defaults
- Frozen classes
- Slots classes
- Auto_attribs pattern
- Inheritance patterns
- eq, order, hash controls
- Field aliases
- Metadata
- Comparison customization (cmp parameter)
- asdict and astuple utilities
- evolve() pattern
- make_class usage
- Nested/composite classes
"""

from typing import Any

import attr


# =============================================================================
# CLASS 1: Basic Legacy @attr.s with @attr.ib
# =============================================================================
@attr.s
class LegacyPerson:
    """Basic person class using legacy attr.s pattern."""
    name = attr.ib()
    age = attr.ib()
    email = attr.ib(default=None)


# =============================================================================
# CLASS 2: Auto Attribs Pattern (should become @attrs.define)
# =============================================================================
@attr.s(auto_attribs=True)
class AutoAttribsUser:
    """User class with auto_attribs=True - default in modern attrs."""
    username: str
    email: str
    active: bool = True
    roles: list[str] = attr.Factory(list)


# =============================================================================
# CLASS 3: Frozen Class (should become @attrs.frozen)
# =============================================================================
@attr.s(frozen=True)
class ImmutableConfig:
    """Immutable configuration object."""
    database_url = attr.ib()
    secret_key = attr.ib()
    debug_mode = attr.ib(default=False)


# =============================================================================
# CLASS 4: Frozen with Auto Attribs
# =============================================================================
@attr.s(auto_attribs=True, frozen=True)
class ImmutablePoint:
    """Immutable 3D point with type hints."""
    x: float
    y: float
    z: float = 0.0


# =============================================================================
# CLASS 5: Slots Class
# =============================================================================
@attr.s(slots=True)
class SlottedVector:
    """Memory-optimized vector with slots."""
    x = attr.ib(type=float)
    y = attr.ib(type=float)
    magnitude = attr.ib(init=False)

    def __attrs_post_init__(self):
        self.magnitude = (self.x ** 2 + self.y ** 2) ** 0.5


# =============================================================================
# CLASS 6: Full Options - slots, frozen, auto_attribs
# =============================================================================
@attr.s(auto_attribs=True, slots=True, frozen=True)
class FullyOptimizedRecord:
    """Fully optimized immutable record."""
    id: int
    name: str
    timestamp: float


# =============================================================================
# CLASS 7: Validators - instance_of
# =============================================================================
@attr.s
class ValidatedEmployee:
    """Employee with type validation."""
    name = attr.ib(validator=attr.validators.instance_of(str))
    employee_id = attr.ib(validator=attr.validators.instance_of(int))
    department = attr.ib(
        validator=attr.validators.instance_of(str),
        default="Engineering"
    )


# =============================================================================
# CLASS 8: Validators - in_ (membership)
# =============================================================================
@attr.s(auto_attribs=True)
class OrderStatus:
    """Order with status validation using in_."""
    order_id: str
    status: str = attr.ib(
        validator=attr.validators.in_(["pending", "processing", "shipped", "delivered", "cancelled"]),
        default="pending"
    )
    priority: str = attr.ib(
        validator=attr.validators.in_(["low", "medium", "high", "critical"]),
        default="medium"
    )


# =============================================================================
# CLASS 9: Validators - optional + combined validators
# =============================================================================
@attr.s
class OptionalFieldsEntity:
    """Entity with optional fields and combined validators."""
    required_field = attr.ib(validator=attr.validators.instance_of(str))
    optional_string = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str))
    )
    optional_number = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of((int, float)))
    )


# =============================================================================
# CLASS 10: Complex Validators - and_, deep_iterable
# =============================================================================
@attr.s(auto_attribs=True)
class TaggedDocument:
    """Document with complex nested validation."""
    title: str = attr.ib(validator=attr.validators.instance_of(str))
    tags: list[str] = attr.ib(
        validator=attr.validators.deep_iterable(
            member_validator=attr.validators.instance_of(str),
            iterable_validator=attr.validators.instance_of(list)
        ),
        factory=list
    )
    metadata: dict[str, Any] = attr.ib(factory=dict)


# =============================================================================
# CLASS 11: Converters - optional, pipe
# =============================================================================
@attr.s
class ConverterDemo:
    """Demonstrates various converter patterns."""
    # Simple converter
    count = attr.ib(converter=int)

    # Optional converter
    maybe_float = attr.ib(
        default=None,
        converter=attr.converters.optional(float)
    )

    # Pipe converters (chain)
    processed_text = attr.ib(
        converter=attr.converters.pipe(str.strip, str.lower)
    )


# =============================================================================
# CLASS 12: Factory Defaults
# =============================================================================
@attr.s(auto_attribs=True)
class FactoryDefaults:
    """Class demonstrating factory defaults."""
    items: list[str] = attr.Factory(list)
    counts: dict[str, int] = attr.Factory(dict)
    unique_items: set = attr.Factory(set)

    # Factory with self reference
    computed: dict[str, Any] = attr.Factory(
        lambda self: {"name": getattr(self, "name", "unknown")},
        takes_self=True
    )
    name: str = "default"


# =============================================================================
# CLASS 13: Comparison Customization (cmp parameter - deprecated)
# =============================================================================
@attr.s(cmp=True)
class ComparableItem:
    """Item with full comparison support using deprecated cmp."""
    priority = attr.ib()
    value = attr.ib()


@attr.s(cmp=False)
class NonComparableItem:
    """Item without comparison operators using deprecated cmp=False."""
    data = attr.ib()


# =============================================================================
# CLASS 14: eq, order, hash controls
# =============================================================================
@attr.s(eq=True, order=True, hash=True)
class SortableEntity:
    """Entity with explicit eq, order, hash controls."""
    sort_key = attr.ib()
    name = attr.ib()

    # Field-level comparison control
    cached_value = attr.ib(default=None, eq=False, hash=False, repr=False)


@attr.s(eq=True, order=False, hash=None)
class HashableOnlyEntity:
    """Entity that's hashable but not orderable."""
    key = attr.ib()


# =============================================================================
# CLASS 15: Inheritance Patterns
# =============================================================================
@attr.s
class BaseModel:
    """Base model with common fields."""
    id = attr.ib(validator=attr.validators.instance_of(int))
    created_at = attr.ib(factory=lambda: 0.0)
    updated_at = attr.ib(factory=lambda: 0.0)


@attr.s
class ExtendedModel(BaseModel):
    """Extended model inheriting from BaseModel."""
    name = attr.ib(validator=attr.validators.instance_of(str))
    description = attr.ib(default="")


@attr.s(auto_attribs=True)
class TypedExtendedModel(BaseModel):
    """Extended model with auto_attribs."""
    name: str
    tags: list[str] = attr.Factory(list)


# =============================================================================
# CLASS 16: Field Aliases (repr_str parameter)
# =============================================================================
@attr.s(auto_attribs=True)
class AliasedFields:
    """Class with field aliases for repr."""
    internal_id: str = attr.ib(repr=True)
    _private_data: str = attr.ib(repr=False)
    display_name: str = attr.ib(repr=lambda x: f"<{x}>")


# =============================================================================
# CLASS 17: Metadata
# =============================================================================
@attr.s(auto_attribs=True)
class MetadataRichClass:
    """Class with rich metadata on fields."""
    username: str = attr.ib(
        metadata={
            "description": "The user's login name",
            "max_length": 255,
            "required": True,
        }
    )
    email: str = attr.ib(
        metadata={
            "description": "Primary email address",
            "format": "email",
            "unique": True,
        }
    )
    password_hash: str = attr.ib(
        repr=False,
        metadata={
            "description": "Hashed password - never expose!",
            "sensitive": True,
        }
    )


# =============================================================================
# CLASS 18: Using attr.attrs decorator (alternative to attr.s)
# =============================================================================
@attr.attrs
class AlternativeDecoratorClass:
    """Using @attr.attrs instead of @attr.s."""
    name = attr.attrib()
    value = attr.attrib(default=0)


# =============================================================================
# CLASS 19: attr.attrib (alternative to attr.ib)
# =============================================================================
@attr.s
class AttribStyleClass:
    """Using attr.attrib instead of attr.ib."""
    name = attr.attrib(validator=attr.validators.instance_of(str))
    count = attr.attrib(converter=int, default=0)


# =============================================================================
# UTILITY FUNCTIONS - asdict, astuple, evolve, fields, has
# =============================================================================

def demonstrate_utilities():
    """Demonstrate attrs utility functions that need migration."""

    # Create instances
    person = LegacyPerson(name="Alice", age=30)
    config = ImmutableConfig(database_url="postgres://...", secret_key="secret")
    user = AutoAttribsUser(username="alice", email="alice@example.com")

    # attr.asdict -> attrs.asdict
    person_dict = attr.asdict(person)
    config_dict = attr.asdict(config)

    # attr.astuple -> attrs.astuple
    person_tuple = attr.astuple(person)

    # attr.evolve -> attrs.evolve (immutable update)
    updated_config = attr.evolve(config, debug_mode=True)
    older_person = attr.evolve(person, age=25)

    # attr.fields -> attrs.fields
    person_fields = attr.fields(LegacyPerson)
    config_fields = attr.fields(ImmutableConfig)

    # attr.has -> attrs.has (check if class is attrs class)
    is_attrs_person = attr.has(LegacyPerson)
    is_attrs_string = attr.has(str)

    # attr.validate -> attrs.validate
    try:
        attr.validate(ValidatedEmployee(name="Bob", employee_id=123))
    except Exception:
        pass

    return {
        "person_dict": person_dict,
        "person_tuple": person_tuple,
        "updated_config": updated_config,
        "person_fields": person_fields,
        "is_attrs_person": is_attrs_person,
    }


# =============================================================================
# NESTED/COMPOSITE CLASSES
# =============================================================================
@attr.s(auto_attribs=True)
class Address:
    """Nested address component."""
    street: str
    city: str
    country: str = "USA"
    postal_code: str = attr.ib(
        default="",
        validator=attr.validators.optional(attr.validators.instance_of(str))
    )


@attr.s(auto_attribs=True)
class Company:
    """Nested company component."""
    name: str
    industry: str = "Technology"
    founded_year: int = attr.ib(default=2020, converter=int)


@attr.s(auto_attribs=True, frozen=True)
class CompleteProfile:
    """Complex profile with nested attrs classes."""
    user: AutoAttribsUser
    home_address: Address
    work_address: Address | None = None
    employer: Company | None = None
    tags: list[str] = attr.Factory(list)
    preferences: dict[str, Any] = attr.Factory(dict)


# =============================================================================
# VALIDATORS MODULE USAGE
# =============================================================================
@attr.s
class ValidatorsShowcase:
    """Showcase of attr.validators module patterns."""

    # Using full path attr.validators.*
    name = attr.ib(validator=attr.validators.instance_of(str))

    # Multiple validators with and_
    age = attr.ib(
        validator=attr.validators.and_(
            attr.validators.instance_of(int),
            attr.validators.ge(0),
            attr.validators.le(150)
        )
    )

    # Deep mapping validator
    settings = attr.ib(
        default=attr.Factory(dict),
        validator=attr.validators.deep_mapping(
            key_validator=attr.validators.instance_of(str),
            value_validator=attr.validators.instance_of((str, int, bool)),
        )
    )


# =============================================================================
# CONVERTERS MODULE USAGE
# =============================================================================
@attr.s
class ConvertersShowcase:
    """Showcase of attr.converters module patterns."""

    # Using full path attr.converters.*
    enabled = attr.ib(converter=attr.converters.to_bool)

    # Optional converter
    maybe_count = attr.ib(
        default=None,
        converter=attr.converters.optional(int)
    )

    # Default if None
    value = attr.ib(
        default=0,
        converter=attr.converters.default_if_none(0)
    )


# =============================================================================
# MODERN STYLE (should NOT be transformed - for comparison)
# =============================================================================
try:
    import attrs

    @attrs.define
    class ModernClass:
        """Modern attrs.define class - should NOT be transformed."""
        name: str
        value: int = attrs.field(default=0)
        items: list[str] = attrs.Factory(list)

    @attrs.frozen
    class ModernFrozen:
        """Modern attrs.frozen class - should NOT be transformed."""
        key: str
        data: dict[str, Any] = attrs.Factory(dict)

    def modern_utilities():
        """Modern attrs utilities - should NOT be transformed."""
        obj = ModernClass(name="test")
        d = attrs.asdict(obj)
        t = attrs.astuple(obj)
        obj2 = attrs.evolve(obj, value=10)
        return d, t, obj2

except ImportError:
    # attrs module might not be available with new-style imports
    pass


# =============================================================================
# from attr import ... style imports (test import transformation)
# =============================================================================
from attr import Factory as AttrFactory
from attr import ib, s
from attr import validators as v


@s
class FromImportStyle:
    """Using from attr import s, ib style."""
    name = ib(validator=v.instance_of(str))
    count = ib(converter=int, default=0)
    items = ib(default=AttrFactory(list))


# =============================================================================
# Complex Real-World Example: API Response Model
# =============================================================================
@attr.s(auto_attribs=True, slots=True)
class APIResponse:
    """Complex API response model with all features."""

    status_code: int = attr.ib(
        validator=attr.validators.instance_of(int),
        metadata={"description": "HTTP status code"}
    )

    success: bool = attr.ib(
        validator=attr.validators.instance_of(bool),
        converter=attr.converters.to_bool
    )

    data: dict[str, Any] | None = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(dict))
    )

    errors: list[str] = attr.ib(
        factory=list,
        validator=attr.validators.deep_iterable(
            member_validator=attr.validators.instance_of(str)
        )
    )

    headers: dict[str, str] = attr.ib(
        factory=dict,
        validator=attr.validators.deep_mapping(
            key_validator=attr.validators.instance_of(str),
            value_validator=attr.validators.instance_of(str)
        )
    )

    request_id: str = attr.ib(
        default="",
        metadata={"tracking": True}
    )

    # Non-compared fields
    _cached_response: bytes | None = attr.ib(
        default=None,
        repr=False,
        eq=False,
        hash=False
    )


# =============================================================================
# Test Driver
# =============================================================================
def run_stress_test():
    """Run the stress test by creating instances of all classes."""

    results = {}

    # Test basic classes
    results["LegacyPerson"] = LegacyPerson(name="Alice", age=30)
    results["AutoAttribsUser"] = AutoAttribsUser(username="alice", email="alice@example.com")
    results["ImmutableConfig"] = ImmutableConfig(database_url="db://", secret_key="key")
    results["ImmutablePoint"] = ImmutablePoint(x=1.0, y=2.0, z=3.0)
    results["SlottedVector"] = SlottedVector(x=3.0, y=4.0)
    results["FullyOptimizedRecord"] = FullyOptimizedRecord(id=1, name="test", timestamp=0.0)

    # Test validated classes
    results["ValidatedEmployee"] = ValidatedEmployee(name="Bob", employee_id=123)
    results["OrderStatus"] = OrderStatus(order_id="ORD-001")
    results["OptionalFieldsEntity"] = OptionalFieldsEntity(required_field="required")
    results["TaggedDocument"] = TaggedDocument(title="Doc", tags=["a", "b"])

    # Test converters
    results["ConverterDemo"] = ConverterDemo(count="42", processed_text="  HELLO  ")

    # Test factories
    results["FactoryDefaults"] = FactoryDefaults()

    # Test comparison
    results["ComparableItem"] = ComparableItem(priority=1, value="test")
    results["SortableEntity"] = SortableEntity(sort_key=1, name="test")

    # Test inheritance
    results["ExtendedModel"] = ExtendedModel(id=1, name="test")

    # Test utilities
    results["utilities"] = demonstrate_utilities()

    # Test nested
    user = AutoAttribsUser(username="test", email="test@test.com")
    addr = Address(street="123 Main St", city="Boston")
    results["CompleteProfile"] = CompleteProfile(user=user, home_address=addr)

    # Test API response
    results["APIResponse"] = APIResponse(status_code=200, success=True)

    print("Stress test completed successfully!")
    print(f"Created {len(results)} test instances")

    return results


if __name__ == "__main__":
    run_stress_test()
