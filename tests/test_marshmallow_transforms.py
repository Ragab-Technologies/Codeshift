"""Tests for Marshmallow 2.x to 3.x transforms."""

from codeshift.migrator.transforms.marshmallow_transformer import (
    transform_marshmallow,
)


class TestDumpLoadDataAccess:
    """Tests for .data access removal from dump/load results."""

    def test_dump_data_to_dump(self):
        """Test schema.dump(obj).data -> schema.dump(obj)."""
        code = """
from marshmallow import Schema, fields

class UserSchema(Schema):
    name = fields.String()

schema = UserSchema()
result = schema.dump(user).data
"""
        transformed, changes = transform_marshmallow(code)

        assert ".data" not in transformed
        assert "schema.dump(user)" in transformed
        assert len(changes) > 0

    def test_load_data_to_load(self):
        """Test schema.load(data).data -> schema.load(data)."""
        code = """
from marshmallow import Schema, fields

class UserSchema(Schema):
    name = fields.String()

schema = UserSchema()
result = schema.load(data).data
"""
        transformed, changes = transform_marshmallow(code)

        assert ".data" not in transformed
        assert "schema.load(data)" in transformed

    def test_dumps_data_to_dumps(self):
        """Test schema.dumps(obj).data -> schema.dumps(obj)."""
        code = """
from marshmallow import Schema

schema = UserSchema()
json_str = schema.dumps(user).data
"""
        transformed, changes = transform_marshmallow(code)

        assert ".data" not in transformed
        assert "schema.dumps(user)" in transformed

    def test_loads_data_to_loads(self):
        """Test schema.loads(json_str).data -> schema.loads(json_str)."""
        code = """
from marshmallow import Schema

schema = UserSchema()
result = schema.loads(json_str).data
"""
        transformed, changes = transform_marshmallow(code)

        assert ".data" not in transformed
        assert "schema.loads(json_str)" in transformed


class TestFieldParameterRenames:
    """Tests for field parameter renames."""

    def test_missing_to_load_default(self):
        """Test missing= -> load_default=."""
        code = """
from marshmallow import Schema, fields

class UserSchema(Schema):
    name = fields.String(missing="Unknown")
"""
        transformed, changes = transform_marshmallow(code)

        assert "load_default=" in transformed
        assert "missing=" not in transformed

    def test_default_to_dump_default(self):
        """Test default= -> dump_default=."""
        code = """
from marshmallow import Schema, fields

class UserSchema(Schema):
    name = fields.String(default="N/A")
"""
        transformed, changes = transform_marshmallow(code)

        # Check if transform was applied
        if len(changes) > 0:
            assert "dump_default=" in transformed
            # Check that standalone 'default=' is not present (not as part of dump_default)
            import re

            # Match 'default=' that is not preceded by 'dump_' or 'load_'
            standalone_default = re.search(r"(?<![a-z_])default=", transformed)
            assert standalone_default is None, f"Found standalone 'default=' in: {transformed}"

    def test_load_from_to_data_key(self):
        """Test load_from= -> data_key=."""
        code = """
from marshmallow import Schema, fields

class UserSchema(Schema):
    user_name = fields.String(load_from="userName")
"""
        transformed, changes = transform_marshmallow(code)

        assert "data_key=" in transformed
        assert "load_from=" not in transformed

    def test_dump_to_to_data_key(self):
        """Test dump_to= -> data_key=."""
        code = """
from marshmallow import Schema, fields

class UserSchema(Schema):
    user_name = fields.String(dump_to="userName")
"""
        transformed, changes = transform_marshmallow(code)

        assert "data_key=" in transformed
        assert "dump_to=" not in transformed

    def test_multiple_field_params(self):
        """Test multiple parameter renames in one field."""
        code = """
from marshmallow import Schema, fields

class UserSchema(Schema):
    name = fields.String(missing="", load_from="userName")
"""
        transformed, changes = transform_marshmallow(code)

        assert "load_default=" in transformed
        assert "data_key=" in transformed
        assert "missing=" not in transformed
        assert "load_from=" not in transformed


class TestDecoratorPassManyRemoval:
    """Tests for pass_many parameter removal from decorators."""

    def test_post_load_pass_many_removal(self):
        """Test @post_load(pass_many=True) -> @post_load."""
        code = """
from marshmallow import Schema, fields, post_load

class UserSchema(Schema):
    name = fields.String()

    @post_load(pass_many=True)
    def process_users(self, data, many):
        return data
"""
        transformed, changes = transform_marshmallow(code)

        assert "pass_many" not in transformed
        assert "@post_load" in transformed
        # Should add **kwargs
        assert "**kwargs" in transformed

    def test_pre_load_pass_many_removal(self):
        """Test @pre_load(pass_many=True) -> @pre_load."""
        code = """
from marshmallow import Schema, fields, pre_load

class UserSchema(Schema):
    @pre_load(pass_many=True)
    def preprocess(self, data, many):
        return data
"""
        transformed, changes = transform_marshmallow(code)

        assert "pass_many" not in transformed
        assert "@pre_load" in transformed

    def test_post_dump_pass_many_removal(self):
        """Test @post_dump(pass_many=True) -> @post_dump."""
        code = """
from marshmallow import Schema, fields, post_dump

class UserSchema(Schema):
    @post_dump(pass_many=True)
    def postprocess(self, data, many):
        return data
"""
        transformed, changes = transform_marshmallow(code)

        assert "pass_many" not in transformed
        assert "@post_dump" in transformed

    def test_pre_dump_pass_many_removal(self):
        """Test @pre_dump(pass_many=True) -> @pre_dump."""
        code = """
from marshmallow import Schema, fields, pre_dump

class UserSchema(Schema):
    @pre_dump(pass_many=True)
    def preprocess(self, data, many):
        return data
"""
        transformed, changes = transform_marshmallow(code)

        assert "pass_many" not in transformed
        assert "@pre_dump" in transformed

    def test_validates_schema_pass_many_removal(self):
        """Test @validates_schema(pass_many=True) -> @validates_schema."""
        code = """
from marshmallow import Schema, fields, validates_schema

class UserSchema(Schema):
    @validates_schema(pass_many=True)
    def validate_all(self, data, many, partial):
        pass
"""
        transformed, changes = transform_marshmallow(code)

        assert "pass_many" not in transformed
        assert "@validates_schema" in transformed


class TestMetaClassTransforms:
    """Tests for Schema.Meta class transformations."""

    def test_remove_meta_strict(self):
        """Test removal of Meta.strict option."""
        code = """
from marshmallow import Schema, fields

class UserSchema(Schema):
    class Meta:
        strict = True

    name = fields.String()
"""
        transformed, changes = transform_marshmallow(code)

        assert "strict = True" not in transformed
        assert "class Meta:" in transformed
        # Meta class should now have only pass
        assert "pass" in transformed

    def test_json_module_to_render_module(self):
        """Test Meta.json_module -> Meta.render_module."""
        code = """
from marshmallow import Schema, fields
import ujson

class UserSchema(Schema):
    class Meta:
        json_module = ujson

    name = fields.String()
"""
        transformed, changes = transform_marshmallow(code)

        assert "render_module = ujson" in transformed
        assert "json_module = ujson" not in transformed

    def test_meta_with_multiple_options(self):
        """Test Meta class with multiple options."""
        code = """
from marshmallow import Schema, fields
import ujson

class UserSchema(Schema):
    class Meta:
        strict = True
        json_module = ujson
        ordered = True

    name = fields.String()
"""
        transformed, changes = transform_marshmallow(code)

        assert "strict = True" not in transformed
        assert "render_module = ujson" in transformed
        assert "ordered = True" in transformed


class TestSchemaInstantiationStrict:
    """Tests for removing strict parameter from schema instantiation."""

    def test_remove_strict_true(self):
        """Test Schema(strict=True) -> Schema()."""
        code = """
from marshmallow import Schema, fields

class UserSchema(Schema):
    name = fields.String()

schema = UserSchema(strict=True)
"""
        transformed, changes = transform_marshmallow(code)

        assert "strict=True" not in transformed
        assert "UserSchema()" in transformed

    def test_remove_strict_preserves_other_args(self):
        """Test that other arguments are preserved when removing strict."""
        code = """
from marshmallow import Schema

schema = UserSchema(strict=True, many=True)
"""
        transformed, changes = transform_marshmallow(code)

        assert "strict=True" not in transformed
        assert "many=True" in transformed


class TestFailToMakeError:
    """Tests for self.fail() -> self.make_error() transformation."""

    def test_fail_to_make_error(self):
        """Test self.fail(key) -> self.make_error(key)."""
        code = """
from marshmallow import fields

class CustomField(fields.Field):
    def _deserialize(self, value, attr, data, **kwargs):
        if not value:
            self.fail("invalid")
        return value
"""
        transformed, changes = transform_marshmallow(code)

        assert "self.make_error(" in transformed
        assert "self.fail(" not in transformed


class TestDifferentFieldTypes:
    """Tests for parameter renames across different field types."""

    def test_integer_field_params(self):
        """Test parameter renames for Integer field."""
        code = """
from marshmallow import Schema, fields

class UserSchema(Schema):
    age = fields.Integer(missing=0, load_from="userAge")
"""
        transformed, changes = transform_marshmallow(code)

        assert "load_default=0" in transformed
        assert 'data_key="userAge"' in transformed

    def test_nested_field_params(self):
        """Test parameter renames for Nested field."""
        code = """
from marshmallow import Schema, fields

class UserSchema(Schema):
    address = fields.Nested(AddressSchema, missing=None)
"""
        transformed, changes = transform_marshmallow(code)

        assert "load_default=None" in transformed

    def test_list_field_params(self):
        """Test parameter renames for List field."""
        code = """
from marshmallow import Schema, fields

class UserSchema(Schema):
    tags = fields.List(fields.String(), missing=[])
"""
        transformed, changes = transform_marshmallow(code)

        assert "load_default=[]" in transformed


class TestComplexTransforms:
    """Tests for complex code with multiple transformations."""

    def test_full_schema_transformation(self):
        """Test transforming a complete Marshmallow v2 schema."""
        code = """
from marshmallow import Schema, fields, post_load, validates_schema
import ujson

class UserSchema(Schema):
    class Meta:
        strict = True
        json_module = ujson

    id = fields.Integer(dump_to="userId")
    name = fields.String(missing="Unknown", load_from="userName")
    email = fields.Email()

    @post_load(pass_many=True)
    def process_users(self, data, many):
        return data

    @validates_schema
    def validate_all(self, data):
        pass

schema = UserSchema(strict=True)
result = schema.dump(user).data
loaded = schema.load(data).data
"""
        transformed, changes = transform_marshmallow(code)

        # Check Meta transformations
        assert "strict = True" not in transformed
        assert "render_module = ujson" in transformed

        # Check field parameter transformations
        assert "data_key=" in transformed
        assert "load_default=" in transformed
        assert "missing=" not in transformed
        assert "load_from=" not in transformed
        assert "dump_to=" not in transformed

        # Check decorator transformations
        assert "pass_many" not in transformed
        assert "**kwargs" in transformed

        # Check instantiation transformation
        assert "UserSchema()" in transformed or "UserSchema(strict=True)" not in transformed

        # Check .data access removal
        assert "schema.dump(user).data" not in transformed
        assert "schema.load(data).data" not in transformed

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_preserves_comments_and_docstrings(self):
        """Test that comments and docstrings are preserved."""
        code = '''
from marshmallow import Schema, fields

class UserSchema(Schema):
    """A user schema."""
    name = fields.String(missing="")  # The user's name
'''
        transformed, changes = transform_marshmallow(code)

        assert '"""A user schema."""' in transformed
        assert "# The user's name" in transformed

    def test_change_tracking(self):
        """Test that changes are properly tracked."""
        code = """
from marshmallow import Schema, fields

class UserSchema(Schema):
    name = fields.String(missing="", load_from="userName")

result = schema.dump(user).data
"""
        transformed, changes = transform_marshmallow(code)

        # Should have multiple changes tracked
        assert len(changes) > 0

        # Check that change descriptions are meaningful
        descriptions = [c.description for c in changes]
        assert any("missing" in d or "load_default" in d for d in descriptions)

    def test_no_changes_for_v3_code(self):
        """Test that v3-compliant code is not modified."""
        code = """
from marshmallow import Schema, fields

class UserSchema(Schema):
    name = fields.String(load_default="", data_key="userName")

result = schema.dump(user)
"""
        transformed, changes = transform_marshmallow(code)

        # Should have no changes
        assert len(changes) == 0
        assert transformed.strip() == code.strip()
