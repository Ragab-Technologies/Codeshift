"""
Old attrs patterns that need migration.
Uses deprecated patterns from attrs 20.x that changed in attrs 21.x+ (attrs vs attr)
"""
import attr
from attr import validators, Factory

# Old pattern: Using deprecated @attr.s decorator with old parameters
@attr.s
class Person:
    """Old attrs class pattern."""
    # Deprecated: Using attr.ib() instead of attrs.field()
    name = attr.ib()
    age = attr.ib()
    # Old pattern: Using deprecated validator syntax
    email = attr.ib(validator=validators.instance_of(str))

# Old pattern: Using deprecated auto_attribs with @attr.s
@attr.s(auto_attribs=True)
class PersonAutoAttribs:
    """Old auto_attribs pattern."""
    name: str
    age: int
    # Deprecated: Using attr.Factory instead of attrs.Factory
    tags: list = Factory(list)

# Old pattern: Using deprecated @attr.attrs decorator
@attr.attrs
class OldStyleClass:
    """Using deprecated @attr.attrs decorator."""
    # Deprecated: Using attr.attrib() (old alias)
    value = attr.attrib()
    # Old pattern: Using deprecated convert parameter
    count = attr.attrib(convert=int)  # Deprecated: use converter

# Old pattern: Using deprecated validator decorators
@attr.s
class ValidatedModel:
    """Old validator pattern."""
    value = attr.ib()
    
    # Deprecated: Using @value.validator decorator style
    @value.validator
    def check_value(self, attribute, value):
        if value < 0:
            raise ValueError("Value must be non-negative")

# Old pattern: Using deprecated cmp parameter
@attr.s(cmp=True)  # Deprecated: use eq=True, order=True
class ComparableModel:
    """Old comparison configuration."""
    x = attr.ib()
    y = attr.ib()

# Old pattern: Using deprecated hash parameter combinations
@attr.s(hash=True)  # Deprecated: auto-determined based on eq
class HashableModel:
    """Old hash configuration."""
    id = attr.ib()
    name = attr.ib()

# Old pattern: Using deprecated init=False with attr.ib
@attr.s
class ModelWithDefaults:
    """Old default pattern."""
    # Deprecated: Using init=False with default
    computed = attr.ib(init=False)
    base_value = attr.ib()
    
    # Old pattern: Using @attr.s without __attrs_post_init__
    def __attrs_post_init__(self):
        self.computed = self.base_value * 2

# Old pattern: Using deprecated slots=True with inheritance issues
@attr.s(slots=True)
class SlottedBase:
    """Old slotted class."""
    x = attr.ib()

@attr.s(slots=True)
class SlottedChild(SlottedBase):
    """Old slotted inheritance (can cause issues)."""
    y = attr.ib()

# Old pattern: Using deprecated repr_ns parameter
@attr.s(repr_ns='mymodule')  # Deprecated parameter
class NamespacedModel:
    """Old repr namespace pattern."""
    value = attr.ib()

# Old pattern: Using deprecated these parameter
@attr.s
class PartialModel:
    """Using deprecated these parameter."""
    # Old pattern: Defining attributes outside class with these=
    pass

PartialModel = attr.make_class(
    'PartialModel',
    # Deprecated: Using dict for attributes
    {'x': attr.ib(), 'y': attr.ib(default=0)}
)

# Old pattern: Using deprecated metadata parameter style
@attr.s
class MetadataModel:
    """Old metadata pattern."""
    value = attr.ib(
        # Deprecated: Using metadata dict directly
        metadata={'serializer': str, 'validator': int}
    )

# Old pattern: Using deprecated type parameter with attr.ib
@attr.s
class TypedModelOld:
    """Old type annotation pattern."""
    # Deprecated: Using type parameter instead of annotation
    name = attr.ib(type=str)
    count = attr.ib(type=int, default=0)
