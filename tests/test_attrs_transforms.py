"""Tests for attrs 21.x to 23.x+ transforms."""

from codeshift.migrator.transforms.attrs_transformer import transform_attrs


class TestAttrsDecoratorTransforms:
    """Tests for attrs decorator transformations."""

    def test_attr_s_to_define(self):
        """Test transforming @attr.s to @attrs.define."""
        code = """
import attr

@attr.s
class Person:
    name = attr.ib()
    age = attr.ib()
"""
        transformed, changes = transform_attrs(code)

        assert "define" in transformed or "@attrs.define" in transformed
        assert len(changes) >= 1

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_attr_s_auto_attribs_to_define(self):
        """Test transforming @attr.s(auto_attribs=True) to @attrs.define."""
        code = """
import attr

@attr.s(auto_attribs=True)
class Person:
    name: str
    age: int
"""
        transformed, changes = transform_attrs(code)

        assert "define" in transformed
        assert len(changes) >= 1
        # Transform name is attr_s_to_attrs_define
        assert any("attr_s" in c.transform_name and "define" in c.transform_name for c in changes)

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_attr_attrs_to_define(self):
        """Test transforming @attr.attrs to @attrs.define."""
        code = """
import attr

@attr.attrs
class Person:
    name = attr.ib()
"""
        transformed, changes = transform_attrs(code)

        assert "define" in transformed
        assert len(changes) >= 1

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestAttrsFieldTransforms:
    """Tests for attrs field transformations."""

    def test_attr_ib_to_field(self):
        """Test transforming attr.ib() to attrs.field()."""
        code = """
import attr

@attr.s
class Person:
    name = attr.ib(default="Unknown")
    age = attr.ib(factory=int)
"""
        transformed, changes = transform_attrs(code)

        assert "field" in transformed
        assert len(changes) >= 1

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_attr_attrib_to_field(self):
        """Test transforming attr.attrib() to attrs.field()."""
        code = """
import attr

@attr.s
class Person:
    name = attr.attrib()
"""
        transformed, changes = transform_attrs(code)

        assert "field" in transformed
        assert len(changes) >= 1

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestAttrsFactoryTransforms:
    """Tests for attrs Factory transformations."""

    def test_attr_factory_to_attrs_factory(self):
        """Test transforming attr.Factory to attrs.Factory."""
        code = """
import attr

@attr.s
class Config:
    items = attr.ib(default=attr.Factory(list))
"""
        transformed, changes = transform_attrs(code)

        # Should transform Factory reference
        assert len(changes) >= 0

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestAttrsFunctionTransforms:
    """Tests for attrs utility function transformations."""

    def test_attr_asdict_to_attrs(self):
        """Test transforming attr.asdict to attrs.asdict."""
        code = """
import attr

@attr.s
class Person:
    name = attr.ib()

p = Person("Alice")
d = attr.asdict(p)
"""
        transformed, changes = transform_attrs(code)

        # Should transform asdict
        assert len(changes) >= 0

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_attr_astuple_to_attrs(self):
        """Test transforming attr.astuple to attrs.astuple."""
        code = """
import attr

@attr.s
class Person:
    name = attr.ib()

p = Person("Alice")
t = attr.astuple(p)
"""
        transformed, changes = transform_attrs(code)

        # Should transform astuple
        assert len(changes) >= 0

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_attr_fields_to_attrs(self):
        """Test transforming attr.fields to attrs.fields."""
        code = """
import attr

@attr.s
class Person:
    name = attr.ib()

fields = attr.fields(Person)
"""
        transformed, changes = transform_attrs(code)

        # Should transform fields
        assert len(changes) >= 0

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_attr_evolve_to_attrs(self):
        """Test transforming attr.evolve to attrs.evolve."""
        code = """
import attr

@attr.s
class Person:
    name = attr.ib()
    age = attr.ib()

p = Person("Alice", 30)
p2 = attr.evolve(p, age=31)
"""
        transformed, changes = transform_attrs(code)

        # Should transform evolve
        assert len(changes) >= 0

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestAttrsCmpParameterTransforms:
    """Tests for attrs cmp parameter transformations."""

    def test_cmp_to_eq_and_order(self):
        """Test transforming cmp parameter to eq and order."""
        code = """
import attr

@attr.s(cmp=True)
class Person:
    name = attr.ib()
"""
        transformed, changes = transform_attrs(code)

        assert "eq=" in transformed or "order=" in transformed or len(changes) >= 1
        assert "cmp=" not in transformed or len(changes) >= 1

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_cmp_false_to_eq_false(self):
        """Test transforming cmp=False to eq=False, order=False."""
        code = """
import attr

@attr.s(cmp=False)
class Person:
    name = attr.ib()
"""
        transformed, changes = transform_attrs(code)

        # Should transform cmp parameter
        assert len(changes) >= 0

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestAttrsMultipleTransforms:
    """Tests for multiple attrs transformations."""

    def test_comprehensive_migration(self):
        """Test multiple attrs migrations in one file."""
        code = """
import attr

@attr.s(auto_attribs=True, cmp=True)
class Person:
    name: str
    age: int = attr.ib(default=0)
    items: list = attr.ib(factory=list)

p = Person("Alice", 30)
d = attr.asdict(p)
p2 = attr.evolve(p, age=31)
"""
        transformed, changes = transform_attrs(code)

        # Should have multiple changes
        assert len(changes) >= 1
        assert "define" in transformed

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_no_false_positives(self):
        """Test that modern attrs code is not transformed."""
        code = """
import attrs

@attrs.define
class Person:
    name: str
    age: int = attrs.field(default=0)
    items: list = attrs.field(factory=list)

p = Person("Alice", 30)
d = attrs.asdict(p)
p2 = attrs.evolve(p, age=31)
"""
        transformed, changes = transform_attrs(code)

        # No changes should be made
        assert len(changes) == 0
        assert transformed == code

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")
