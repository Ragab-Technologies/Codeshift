"""Pydantic v1 to v2 transformation using LibCST."""

from typing import Any, Optional

import libcst as cst
from libcst import matchers as m

from pyresolve.migrator.ast_transforms import BaseTransformer


class PydanticV1ToV2Transformer(BaseTransformer):
    """Transform Pydantic v1 code to v2."""

    def __init__(self) -> None:
        super().__init__()
        # Track what needs to be imported
        self._needs_config_dict = False
        self._needs_field_validator = False
        self._needs_model_validator = False
        self._has_validator_import = False
        self._has_root_validator_import = False
        # Track classes that have inner Config
        self._classes_with_config: dict[str, dict] = {}
        self._current_class: Optional[str] = None
        # Track position info
        self._line_offset = 0

    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
        """Track the current class being visited."""
        self._current_class = node.name.value
        return True

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        """Process class definitions to convert inner Config to model_config."""
        self._current_class = None

        # Check if this class has a Config inner class
        config_class = None
        config_index = -1
        new_body = list(updated_node.body.body)

        for i, item in enumerate(new_body):
            if isinstance(item, cst.ClassDef) and item.name.value == "Config":
                config_class = item
                config_index = i
                break

        if config_class is None:
            return updated_node

        # Extract Config options
        config_dict = self._extract_config_options(config_class)
        if not config_dict:
            return updated_node

        self._needs_config_dict = True

        # Create model_config assignment
        model_config_stmt = self._create_model_config(config_dict)

        # Replace Config class with model_config
        new_body[config_index] = model_config_stmt

        self.record_change(
            description="Convert inner Config class to model_config = ConfigDict(...)",
            line_number=1,  # Approximate
            original="class Config: ...",
            replacement="model_config = ConfigDict(...)",
            transform_name="config_to_configdict",
        )

        return updated_node.with_changes(body=updated_node.body.with_changes(body=new_body))

    def _extract_config_options(self, config_class: cst.ClassDef) -> dict[str, Any]:
        """Extract configuration options from a Config class."""
        options: dict[str, Any] = {}

        for item in config_class.body.body:
            if isinstance(item, cst.SimpleStatementLine):
                for stmt in item.body:
                    if isinstance(stmt, cst.Assign):
                        for target in stmt.targets:
                            if isinstance(target.target, cst.Name):
                                name = target.target.value
                                value = self._extract_value(stmt.value)
                                if value is not None:
                                    # Map v1 options to v2
                                    mapped_name, mapped_value = self._map_config_option(name, value)
                                    if mapped_name:
                                        options[mapped_name] = mapped_value

        return options

    def _map_config_option(self, name: str, value: Any) -> tuple[Optional[str], Any]:
        """Map a v1 Config option to v2 ConfigDict option."""
        # Direct mappings
        mappings = {
            "orm_mode": ("from_attributes", value),
            "validate_assignment": ("validate_assignment", value),
            "extra": ("extra", value),
            "frozen": ("frozen", value),
            "use_enum_values": ("use_enum_values", value),
            "validate_default": ("validate_default", value),
            "populate_by_name": ("populate_by_name", value),
            "str_strip_whitespace": ("str_strip_whitespace", value),
            "str_min_length": ("str_min_length", value),
            "str_max_length": ("str_max_length", value),
            "arbitrary_types_allowed": ("arbitrary_types_allowed", value),
        }

        if name in mappings:
            return mappings[name]

        # Special mappings
        if name == "allow_mutation":
            # allow_mutation=False -> frozen=True
            if value is False:
                return ("frozen", True)
            return (None, None)

        if name == "allow_population_by_field_name":
            return ("populate_by_name", value)

        if name == "anystr_strip_whitespace":
            return ("str_strip_whitespace", value)

        if name == "underscore_attrs_are_private":
            # This is the default in v2
            return (None, None)

        # Return as-is for unknown options (might work)
        return (name, value)

    def _extract_value(self, node: cst.BaseExpression) -> Any:
        """Extract a Python value from a CST node."""
        if isinstance(node, cst.Name):
            if node.value == "True":
                return True
            if node.value == "False":
                return False
            if node.value == "None":
                return None
            return node.value  # Return as string for enums etc.
        if isinstance(node, cst.SimpleString):
            # Remove quotes
            return node.value[1:-1]
        if isinstance(node, cst.Integer):
            return int(node.value)
        if isinstance(node, cst.Float):
            return float(node.value)
        return None

    def _create_model_config(self, config_dict: dict[str, Any]) -> cst.SimpleStatementLine:
        """Create a model_config = ConfigDict(...) statement."""
        args = []
        for key, value in config_dict.items():
            # Create the value node
            value_node: cst.BaseExpression
            if isinstance(value, bool):
                value_node = cst.Name("True" if value else "False")
            elif isinstance(value, str):
                value_node = cst.SimpleString(f'"{value}"')
            elif isinstance(value, int):
                value_node = cst.Integer(str(value))
            elif isinstance(value, float):
                value_node = cst.Float(str(value))
            else:
                value_node = cst.Name(str(value))

            args.append(
                cst.Arg(
                    keyword=cst.Name(key),
                    value=value_node,
                    equal=cst.AssignEqual(
                        whitespace_before=cst.SimpleWhitespace(""),
                        whitespace_after=cst.SimpleWhitespace(""),
                    ),
                )
            )

        # Create ConfigDict call
        config_dict_call = cst.Call(
            func=cst.Name("ConfigDict"),
            args=args,
        )

        # Create the assignment
        return cst.SimpleStatementLine(
            body=[
                cst.Assign(
                    targets=[cst.AssignTarget(target=cst.Name("model_config"))],
                    value=config_dict_call,
                )
            ]
        )

    def leave_Decorator(
        self, original_node: cst.Decorator, updated_node: cst.Decorator
    ) -> cst.Decorator:
        """Transform @validator to @field_validator and @root_validator to @model_validator."""
        # Handle @validator
        if m.matches(
            updated_node.decorator,
            m.Call(func=m.Name("validator")) | m.Name("validator"),
        ):
            self._needs_field_validator = True
            return self._transform_validator_decorator(updated_node)

        # Handle @root_validator
        if m.matches(
            updated_node.decorator,
            m.Call(func=m.Name("root_validator")) | m.Name("root_validator"),
        ):
            self._needs_model_validator = True
            return self._transform_root_validator_decorator(updated_node)

        return updated_node

    def _transform_validator_decorator(self, node: cst.Decorator) -> cst.Decorator:
        """Transform @validator("field") to @field_validator("field")."""
        if isinstance(node.decorator, cst.Call):
            # @validator("field_name", ...)
            new_call = node.decorator.with_changes(func=cst.Name("field_validator"))

            self.record_change(
                description="Convert @validator to @field_validator",
                line_number=1,
                original="@validator(...)",
                replacement="@field_validator(...)",
                transform_name="validator_to_field_validator",
            )

            return node.with_changes(decorator=new_call)
        else:
            # @validator without arguments (shouldn't happen but handle it)
            self.record_change(
                description="Convert @validator to @field_validator",
                line_number=1,
                original="@validator",
                replacement="@field_validator",
                transform_name="validator_to_field_validator",
            )
            return node.with_changes(decorator=cst.Name("field_validator"))

    def _transform_root_validator_decorator(self, node: cst.Decorator) -> cst.Decorator:
        """Transform @root_validator to @model_validator(mode='before')."""
        mode = "before"  # Default for v1 root_validator

        if isinstance(node.decorator, cst.Call):
            # Check for pre=False which means mode='after'
            for arg in node.decorator.args:
                if isinstance(arg.keyword, cst.Name) and arg.keyword.value == "pre":
                    if isinstance(arg.value, cst.Name) and arg.value.value == "False":
                        mode = "after"

        # Create @model_validator(mode="before") or (mode="after")
        new_decorator = cst.Call(
            func=cst.Name("model_validator"),
            args=[
                cst.Arg(
                    keyword=cst.Name("mode"),
                    value=cst.SimpleString(f'"{mode}"'),
                    equal=cst.AssignEqual(
                        whitespace_before=cst.SimpleWhitespace(""),
                        whitespace_after=cst.SimpleWhitespace(""),
                    ),
                )
            ],
        )

        self.record_change(
            description=f"Convert @root_validator to @model_validator(mode='{mode}')",
            line_number=1,
            original="@root_validator",
            replacement=f'@model_validator(mode="{mode}")',
            transform_name="root_validator_to_model_validator",
        )

        return node.with_changes(decorator=new_decorator)

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        """Add @classmethod decorator to validator methods if needed."""
        # Check if this function has @field_validator or @model_validator
        has_field_validator = False
        has_model_validator = False
        has_classmethod = False

        for decorator in updated_node.decorators:
            dec = decorator.decorator
            if isinstance(dec, cst.Call):
                if isinstance(dec.func, cst.Name):
                    if dec.func.value == "field_validator":
                        has_field_validator = True
                    elif dec.func.value == "model_validator":
                        has_model_validator = True
            elif isinstance(dec, cst.Name):
                if dec.value == "classmethod":
                    has_classmethod = True
                elif dec.value == "field_validator":
                    has_field_validator = True
                elif dec.value == "model_validator":
                    has_model_validator = True

        # Add @classmethod if needed
        if (has_field_validator or has_model_validator) and not has_classmethod:
            classmethod_decorator = cst.Decorator(decorator=cst.Name("classmethod"))
            new_decorators = list(updated_node.decorators) + [classmethod_decorator]

            self.record_change(
                description="Add @classmethod decorator to validator",
                line_number=1,
                original="def method(cls, ...)",
                replacement="@classmethod\ndef method(cls, ...)",
                transform_name="add_classmethod",
            )

            return updated_node.with_changes(decorators=new_decorators)

        return updated_node

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.BaseExpression:
        """Transform method calls like .dict() to .model_dump()."""
        # Handle method calls on objects
        if isinstance(updated_node.func, cst.Attribute):
            method_name = updated_node.func.attr.value

            method_mappings = {
                "dict": "model_dump",
                "json": "model_dump_json",
                "copy": "model_copy",
                "parse_obj": "model_validate",
                "parse_raw": "model_validate_json",
                "schema": "model_json_schema",
                "schema_json": "model_json_schema",
                "update_forward_refs": "model_rebuild",
            }

            if method_name in method_mappings:
                new_method = method_mappings[method_name]
                new_attr = updated_node.func.with_changes(attr=cst.Name(new_method))

                self.record_change(
                    description=f"Convert .{method_name}() to .{new_method}()",
                    line_number=1,
                    original=f".{method_name}()",
                    replacement=f".{new_method}()",
                    transform_name=f"{method_name}_to_{new_method}",
                )

                return updated_node.with_changes(func=new_attr)

        # Handle Field(regex=...) -> Field(pattern=...)
        if isinstance(updated_node.func, cst.Name) and updated_node.func.value == "Field":
            new_args = []
            changed = False

            for arg in updated_node.args:
                if isinstance(arg.keyword, cst.Name) and arg.keyword.value == "regex":
                    # Change regex to pattern
                    new_arg = arg.with_changes(keyword=cst.Name("pattern"))
                    new_args.append(new_arg)
                    changed = True

                    self.record_change(
                        description="Convert Field(regex=...) to Field(pattern=...)",
                        line_number=1,
                        original="Field(regex=...)",
                        replacement="Field(pattern=...)",
                        transform_name="field_regex_to_pattern",
                    )
                elif isinstance(arg.keyword, cst.Name) and arg.keyword.value == "min_items":
                    new_arg = arg.with_changes(keyword=cst.Name("min_length"))
                    new_args.append(new_arg)
                    changed = True

                    self.record_change(
                        description="Convert Field(min_items=...) to Field(min_length=...)",
                        line_number=1,
                        original="Field(min_items=...)",
                        replacement="Field(min_length=...)",
                        transform_name="field_min_items_to_min_length",
                    )
                elif isinstance(arg.keyword, cst.Name) and arg.keyword.value == "max_items":
                    new_arg = arg.with_changes(keyword=cst.Name("max_length"))
                    new_args.append(new_arg)
                    changed = True

                    self.record_change(
                        description="Convert Field(max_items=...) to Field(max_length=...)",
                        line_number=1,
                        original="Field(max_items=...)",
                        replacement="Field(max_length=...)",
                        transform_name="field_max_items_to_max_length",
                    )
                else:
                    new_args.append(arg)

            if changed:
                return updated_node.with_changes(args=new_args)

        return updated_node

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.BaseExpression:
        """Transform attribute access like __fields__ to model_fields."""
        attr_name = updated_node.attr.value

        attr_mappings = {
            "__fields__": "model_fields",
            "__validators__": "__pydantic_decorators__",
        }

        if attr_name in attr_mappings:
            new_attr = attr_mappings[attr_name]

            self.record_change(
                description=f"Convert {attr_name} to {new_attr}",
                line_number=1,
                original=attr_name,
                replacement=new_attr,
                transform_name=f"{attr_name}_rename",
            )

            return updated_node.with_changes(attr=cst.Name(new_attr))

        return updated_node

    def leave_ImportFrom(
        self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
    ) -> cst.ImportFrom:
        """Transform imports from pydantic."""
        if updated_node.module is None:
            return updated_node

        module_name = self._get_module_name(updated_node.module)
        if module_name != "pydantic":
            return updated_node

        if isinstance(updated_node.names, cst.ImportStar):
            return updated_node

        new_names = []
        changed = False

        for name in updated_node.names:
            if isinstance(name, cst.ImportAlias):
                imported_name = self._get_name_value(name.name)

                if imported_name == "validator":
                    self._has_validator_import = True
                    new_name = name.with_changes(name=cst.Name("field_validator"))
                    new_names.append(new_name)
                    changed = True

                    self.record_change(
                        description="Convert 'validator' import to 'field_validator'",
                        line_number=1,
                        original="from pydantic import validator",
                        replacement="from pydantic import field_validator",
                        transform_name="import_validator_to_field_validator",
                    )
                elif imported_name == "root_validator":
                    self._has_root_validator_import = True
                    new_name = name.with_changes(name=cst.Name("model_validator"))
                    new_names.append(new_name)
                    changed = True

                    self.record_change(
                        description="Convert 'root_validator' import to 'model_validator'",
                        line_number=1,
                        original="from pydantic import root_validator",
                        replacement="from pydantic import model_validator",
                        transform_name="import_root_validator_to_model_validator",
                    )
                else:
                    new_names.append(name)

        # Add ConfigDict import if needed
        if self._needs_config_dict:
            # Check if ConfigDict is already imported
            has_config_dict = any(
                isinstance(n, cst.ImportAlias) and self._get_name_value(n.name) == "ConfigDict"
                for n in new_names
            )
            if not has_config_dict:
                new_names.append(cst.ImportAlias(name=cst.Name("ConfigDict")))
                changed = True

        if changed:
            return updated_node.with_changes(names=new_names)

        return updated_node

    def _get_module_name(self, node: cst.BaseExpression) -> str:
        """Get the full module name from an Attribute or Name node."""
        if isinstance(node, cst.Name):
            return str(node.value)
        if isinstance(node, cst.Attribute):
            base = self._get_module_name(node.value)
            return f"{base}.{node.attr.value}"
        return ""

    def _get_name_value(self, node: cst.BaseExpression) -> Optional[str]:
        """Extract the string value from a Name node."""
        if isinstance(node, cst.Name):
            return str(node.value)
        return None


class PydanticImportTransformer(BaseTransformer):
    """Separate transformer for handling import additions.

    This runs after the main transformer to add any missing imports.
    """

    def __init__(
        self,
        needs_config_dict: bool = False,
        needs_field_validator: bool = False,
        needs_model_validator: bool = False,
    ) -> None:
        super().__init__()
        self.needs_config_dict = needs_config_dict
        self.needs_field_validator = needs_field_validator
        self.needs_model_validator = needs_model_validator
        self._found_pydantic_import = False
        self._has_config_dict = False
        self._has_field_validator = False
        self._has_model_validator = False

    def visit_ImportFrom(self, node: cst.ImportFrom) -> bool:
        """Check existing pydantic imports."""
        if node.module is None:
            return True

        if self._get_module_name(node.module) == "pydantic":
            self._found_pydantic_import = True

            # Check for existing imports (handle both tuple and list after transforms)
            if not isinstance(node.names, cst.ImportStar):
                for name in node.names:
                    if isinstance(name, cst.ImportAlias):
                        imported = self._get_name_value(name.name)
                        if imported == "ConfigDict":
                            self._has_config_dict = True
                        elif imported == "field_validator":
                            self._has_field_validator = True
                        elif imported == "model_validator":
                            self._has_model_validator = True

        return True

    def leave_ImportFrom(
        self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
    ) -> cst.ImportFrom:
        """Add missing imports to pydantic import statement."""
        if updated_node.module is None:
            return updated_node

        if self._get_module_name(updated_node.module) != "pydantic":
            return updated_node

        if isinstance(updated_node.names, cst.ImportStar):
            return updated_node

        new_names = list(updated_node.names)
        changed = False

        if self.needs_config_dict and not self._has_config_dict:
            new_names.append(cst.ImportAlias(name=cst.Name("ConfigDict")))
            self._has_config_dict = True
            changed = True

        if self.needs_field_validator and not self._has_field_validator:
            new_names.append(cst.ImportAlias(name=cst.Name("field_validator")))
            self._has_field_validator = True
            changed = True

        if self.needs_model_validator and not self._has_model_validator:
            new_names.append(cst.ImportAlias(name=cst.Name("model_validator")))
            self._has_model_validator = True
            changed = True

        if changed:
            return updated_node.with_changes(names=new_names)

        return updated_node

    def _get_module_name(self, node: cst.BaseExpression) -> str:
        """Get the full module name from an Attribute or Name node."""
        if isinstance(node, cst.Name):
            return str(node.value)
        if isinstance(node, cst.Attribute):
            base = self._get_module_name(node.value)
            return f"{base}.{node.attr.value}"
        return ""

    def _get_name_value(self, node: cst.BaseExpression) -> Optional[str]:
        """Extract the string value from a Name node."""
        if isinstance(node, cst.Name):
            return str(node.value)
        return None


def transform_pydantic_v1_to_v2(source_code: str) -> tuple[str, list]:
    """Transform Pydantic v1 code to v2.

    Args:
        source_code: The source code to transform

    Returns:
        Tuple of (transformed_code, list of changes)
    """
    try:
        tree = cst.parse_module(source_code)
    except cst.ParserSyntaxError as e:
        raise SyntaxError(f"Invalid Python syntax: {e}") from e

    # First pass: main transformations
    transformer = PydanticV1ToV2Transformer()
    transformer.set_source(source_code)
    transformed_tree = tree.visit(transformer)

    # Second pass: add missing imports
    import_transformer = PydanticImportTransformer(
        needs_config_dict=transformer._needs_config_dict,
        needs_field_validator=transformer._needs_field_validator,
        needs_model_validator=transformer._needs_model_validator,
    )
    final_tree = transformed_tree.visit(import_transformer)

    return final_tree.code, transformer.changes
