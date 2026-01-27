"""Marshmallow 2.x to 3.x transformation using LibCST."""

import libcst as cst

from codeshift.migrator.ast_transforms import BaseTransformer


class MarshmallowTransformer(BaseTransformer):
    """Transform Marshmallow 2.x code to 3.x."""

    def __init__(self) -> None:
        super().__init__()
        # Track methods decorated with pass_many for signature update
        self._methods_needing_kwargs: set[str] = set()
        # Track current decorator being processed
        self._current_decorator_has_pass_many = False

    def leave_Decorator(
        self, original_node: cst.Decorator, updated_node: cst.Decorator
    ) -> cst.Decorator:
        """Transform decorators that have pass_many parameter.

        Handles:
        - @post_load(pass_many=True) -> @post_load
        - @pre_load(pass_many=True) -> @pre_load
        - @post_dump(pass_many=True) -> @post_dump
        - @pre_dump(pass_many=True) -> @pre_dump
        - @validates_schema(pass_many=True) -> @validates_schema
        """
        self._current_decorator_has_pass_many = False

        # Check if decorator is a Call with pass_many argument
        if not isinstance(updated_node.decorator, cst.Call):
            return updated_node

        call = updated_node.decorator
        func_name = self._get_decorator_name(call.func)

        if func_name not in {
            "post_load",
            "pre_load",
            "post_dump",
            "pre_dump",
            "validates_schema",
        }:
            return updated_node

        # Check for pass_many argument
        new_args = []
        found_pass_many = False

        for arg in call.args:
            if isinstance(arg.keyword, cst.Name) and arg.keyword.value == "pass_many":
                found_pass_many = True
                self._current_decorator_has_pass_many = True
                self.record_change(
                    description=f"Remove pass_many parameter from @{func_name}",
                    line_number=1,
                    original=f"@{func_name}(pass_many=True)",
                    replacement=f"@{func_name}",
                    transform_name=f"{func_name}_pass_many",
                )
            else:
                new_args.append(arg)

        if found_pass_many:
            if new_args:
                # Still have other arguments, keep as call
                return updated_node.with_changes(decorator=call.with_changes(args=new_args))
            else:
                # No more arguments, simplify to just the name
                return updated_node.with_changes(decorator=call.func)

        return updated_node

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        """Add **kwargs to methods that had pass_many decorators."""
        # Check if this function has a marshmallow decorator that had pass_many
        has_marshmallow_decorator = False
        for decorator in updated_node.decorators:
            dec = decorator.decorator
            func_name = None
            if isinstance(dec, cst.Call):
                func_name = self._get_decorator_name(dec.func)
            elif isinstance(dec, cst.Name):
                func_name = dec.value

            if func_name in {
                "post_load",
                "pre_load",
                "post_dump",
                "pre_dump",
                "validates_schema",
            }:
                has_marshmallow_decorator = True
                break

        if not has_marshmallow_decorator:
            return updated_node

        # Check if **kwargs already exists
        params = updated_node.params
        if params.star_kwarg is not None:
            return updated_node

        # Add **kwargs to the parameters
        new_star_kwarg = cst.Param(name=cst.Name("kwargs"))
        new_params = params.with_changes(star_kwarg=new_star_kwarg)

        self.record_change(
            description="Add **kwargs to method signature for many/partial args",
            line_number=1,
            original=f"def {updated_node.name.value}(self, ...)",
            replacement=f"def {updated_node.name.value}(self, ..., **kwargs)",
            transform_name="add_kwargs_to_decorated_method",
        )

        return updated_node.with_changes(params=new_params)

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.BaseExpression:
        """Transform method calls and field instantiations."""
        # Handle Schema().dump().data and Schema().load().data patterns
        transformed = self._transform_data_access(updated_node)
        if transformed is not updated_node:
            return transformed

        # Handle Field parameter renames
        transformed = self._transform_field_params(updated_node)
        if transformed is not updated_node:
            return transformed

        # Handle Schema instantiation with strict parameter
        transformed = self._transform_schema_instantiation(updated_node)
        if transformed is not updated_node:
            return transformed

        # Handle self.fail() -> raise self.make_error()
        transformed = self._transform_fail_to_make_error(updated_node)
        if transformed is not updated_node:
            return transformed

        return updated_node

    def _transform_data_access(self, node: cst.Call) -> cst.BaseExpression:
        """Transform schema.dump(obj).data and schema.load(data).data patterns.

        In v2: result = schema.dump(obj).data
        In v3: result = schema.dump(obj)
        """
        # This is handled in leave_Attribute for the .data access pattern
        return node

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.BaseExpression:
        """Transform .data attribute access on dump/load results."""
        # Check if this is .data access
        if updated_node.attr.value != "data":
            return updated_node

        # Check if the value is a Call to dump, load, dumps, or loads
        if not isinstance(updated_node.value, cst.Call):
            return updated_node

        call = updated_node.value
        if not isinstance(call.func, cst.Attribute):
            return updated_node

        method_name = call.func.attr.value
        if method_name not in {"dump", "load", "dumps", "loads"}:
            return updated_node

        # This is schema.dump(obj).data or schema.load(data).data
        # Transform to just schema.dump(obj) or schema.load(data)
        self.record_change(
            description=f"Remove .data access from {method_name}() - v3 returns data directly",
            line_number=1,
            original=f"schema.{method_name}(...).data",
            replacement=f"schema.{method_name}(...)",
            transform_name=f"{method_name}_data_to_{method_name}",
        )

        return call

    def _transform_field_params(self, node: cst.Call) -> cst.Call:
        """Transform field parameter renames.

        - missing -> load_default
        - default -> dump_default
        - load_from -> data_key
        - dump_to -> data_key
        """
        # Check if this is a fields.* call or a Field-like call
        func_name = self._get_call_func_name(node.func)
        if func_name is None:
            return node

        # Common field types and Field itself
        field_types = {
            "Field",
            "String",
            "Str",
            "Integer",
            "Int",
            "Float",
            "Boolean",
            "Bool",
            "DateTime",
            "Date",
            "Time",
            "TimeDelta",
            "Decimal",
            "UUID",
            "Email",
            "URL",
            "Url",
            "Method",
            "Function",
            "Nested",
            "List",
            "Dict",
            "Tuple",
            "Mapping",
            "Raw",
            "Number",
            "Pluck",
            "Constant",
        }

        if func_name not in field_types:
            return node

        new_args = []
        changed = False
        param_mappings = {
            "missing": "load_default",
            "default": "dump_default",
            "load_from": "data_key",
            "dump_to": "data_key",
        }

        for arg in node.args:
            if isinstance(arg.keyword, cst.Name) and arg.keyword.value in param_mappings:
                old_name = arg.keyword.value
                new_name = param_mappings[old_name]
                new_arg = arg.with_changes(keyword=cst.Name(new_name))
                new_args.append(new_arg)
                changed = True

                self.record_change(
                    description=f"Rename field parameter '{old_name}' to '{new_name}'",
                    line_number=1,
                    original=f"{func_name}({old_name}=...)",
                    replacement=f"{func_name}({new_name}=...)",
                    transform_name=f"{old_name}_to_{new_name}",
                )
            else:
                new_args.append(arg)

        if changed:
            return node.with_changes(args=new_args)

        return node

    def _transform_schema_instantiation(self, node: cst.Call) -> cst.Call:
        """Remove strict parameter from schema instantiation.

        In v2: UserSchema(strict=True)
        In v3: UserSchema()  # strict is always True
        """
        # Check for strict argument
        new_args = []
        changed = False

        for arg in node.args:
            if isinstance(arg.keyword, cst.Name) and arg.keyword.value == "strict":
                changed = True
                self.record_change(
                    description="Remove 'strict' parameter - schemas are always strict in v3",
                    line_number=1,
                    original="Schema(strict=True)",
                    replacement="Schema()",
                    transform_name="remove_schema_strict",
                )
            else:
                new_args.append(arg)

        if changed:
            # Fix trailing comma if needed
            if new_args:
                last_arg = new_args[-1]
                if last_arg.comma != cst.MaybeSentinel.DEFAULT:
                    new_args[-1] = last_arg.with_changes(comma=cst.MaybeSentinel.DEFAULT)
            return node.with_changes(args=new_args)

        return node

    def _transform_fail_to_make_error(self, node: cst.Call) -> cst.BaseExpression:
        """Transform self.fail(key) to self.make_error(key).

        Note: The caller should wrap this in a raise statement.
        This transform returns the make_error call; wrapping in Raise
        is handled separately if needed (or flagged for manual review).
        """
        if not isinstance(node.func, cst.Attribute):
            return node

        if node.func.attr.value != "fail":
            return node

        # Check if it's self.fail
        if not isinstance(node.func.value, cst.Name):
            return node

        if node.func.value.value != "self":
            return node

        # Transform self.fail(...) to self.make_error(...)
        new_func = node.func.with_changes(attr=cst.Name("make_error"))

        self.record_change(
            description="Replace self.fail() with self.make_error() - wrap in raise",
            line_number=1,
            original="self.fail(key)",
            replacement="raise self.make_error(key)",
            transform_name="fail_to_make_error",
            notes="The call should be wrapped in a raise statement",
        )

        return node.with_changes(func=new_func)

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        """Transform Schema classes to remove Meta.strict and Meta.json_module."""
        # Check if this class has a Meta inner class
        meta_class = None
        meta_index = -1
        new_body = list(updated_node.body.body)

        for i, item in enumerate(new_body):
            if isinstance(item, cst.ClassDef) and item.name.value == "Meta":
                meta_class = item
                meta_index = i
                break

        if meta_class is None:
            return updated_node

        # Process Meta class body
        transformed_meta = self._transform_meta_class(meta_class)
        if transformed_meta is not meta_class:
            new_body[meta_index] = transformed_meta
            return updated_node.with_changes(body=updated_node.body.with_changes(body=new_body))

        return updated_node

    def _transform_meta_class(self, meta_class: cst.ClassDef) -> cst.ClassDef:
        """Transform Meta class attributes.

        - Remove strict = True
        - Rename json_module to render_module
        """
        new_body_items: list[cst.BaseStatement | cst.BaseSmallStatement] = []
        changed = False

        for item in meta_class.body.body:
            if isinstance(item, cst.SimpleStatementLine):
                transformed_stmt, was_changed = self._transform_meta_statement(item)
                if was_changed:
                    changed = True
                    if transformed_stmt is not None:
                        new_body_items.append(transformed_stmt)
                else:
                    new_body_items.append(item)
            else:
                new_body_items.append(item)

        if changed:
            # If all statements were removed, add pass
            if not new_body_items:
                new_body_items = [cst.SimpleStatementLine(body=[cst.Pass()])]

            return meta_class.with_changes(body=meta_class.body.with_changes(body=new_body_items))

        return meta_class

    def _transform_meta_statement(
        self, stmt: cst.SimpleStatementLine
    ) -> tuple[cst.SimpleStatementLine | None, bool]:
        """Transform a Meta class statement.

        Returns:
            Tuple of (transformed_statement or None if removed, was_changed)
        """
        new_body: list[cst.BaseSmallStatement] = []
        changed = False

        for s in stmt.body:
            if isinstance(s, cst.Assign):
                skip_statement = False
                transformed_statement = None

                for target in s.targets:
                    if isinstance(target.target, cst.Name):
                        name = target.target.value

                        if name == "strict":
                            # Remove strict assignment
                            changed = True
                            skip_statement = True
                            self.record_change(
                                description="Remove Meta.strict - schemas are always strict in v3",
                                line_number=1,
                                original="strict = True",
                                replacement="# removed",
                                transform_name="remove_meta_strict",
                            )
                            break

                        if name == "json_module":
                            # Rename to render_module
                            changed = True
                            new_target = target.with_changes(target=cst.Name("render_module"))
                            transformed_statement = s.with_changes(targets=[new_target])
                            self.record_change(
                                description="Rename Meta.json_module to Meta.render_module",
                                line_number=1,
                                original="json_module = ...",
                                replacement="render_module = ...",
                                transform_name="json_module_to_render_module",
                            )
                            break

                if skip_statement:
                    continue
                elif transformed_statement:
                    new_body.append(transformed_statement)
                else:
                    new_body.append(s)
            else:
                new_body.append(s)

        if changed:
            if new_body:
                return stmt.with_changes(body=new_body), True
            return None, True

        return stmt, False

    def _get_decorator_name(self, node: cst.BaseExpression) -> str | None:
        """Get the name of a decorator."""
        if isinstance(node, cst.Name):
            return str(node.value)
        if isinstance(node, cst.Attribute):
            return str(node.attr.value)
        return None

    def _get_call_func_name(self, node: cst.BaseExpression) -> str | None:
        """Get the function name from a call's func attribute."""
        if isinstance(node, cst.Name):
            return str(node.value)
        if isinstance(node, cst.Attribute):
            # Handle fields.String, etc.
            return str(node.attr.value)
        return None


class MarshmallowImportTransformer(BaseTransformer):
    """Handle import transformations for Marshmallow.

    This runs after the main transformer.
    """

    def __init__(self) -> None:
        super().__init__()

    def leave_ImportFrom(
        self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
    ) -> cst.ImportFrom:
        """Transform marshmallow imports if needed.

        Currently no import changes are required for v2 to v3 migration
        as the module structure remains the same.
        """
        return updated_node


def transform_marshmallow(source_code: str) -> tuple[str, list]:
    """Transform Marshmallow code from 2.x to 3.x.

    Args:
        source_code: The source code to transform

    Returns:
        Tuple of (transformed_code, list of changes)
    """
    try:
        tree = cst.parse_module(source_code)
    except cst.ParserSyntaxError as e:
        raise SyntaxError(f"Invalid Python syntax: {e}") from e

    # Main transformation pass
    transformer = MarshmallowTransformer()
    transformer.set_source(source_code)
    transformed_tree = tree.visit(transformer)

    # Import transformation pass (currently minimal)
    import_transformer = MarshmallowImportTransformer()
    final_tree = transformed_tree.visit(import_transformer)

    all_changes = transformer.changes + import_transformer.changes
    return final_tree.code, all_changes
