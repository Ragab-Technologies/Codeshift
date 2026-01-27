"""attrs 21.x to 23.x+ transformation using LibCST.

Transforms legacy attr namespace to modern attrs namespace:
- @attr.s -> @attrs.define
- @attr.attrs -> @attrs.define
- @attr.s(frozen=True) -> @attrs.frozen
- attr.ib() -> attrs.field()
- attr.attrib() -> attrs.field()
- attr.Factory -> attrs.Factory
- attr.asdict/astuple/fields/has/evolve -> attrs.*
- attr.validators.* -> attrs.validators.*
- attr.converters.* -> attrs.converters.*
- cmp parameter -> eq and order parameters
"""

import libcst as cst

from codeshift.migrator.ast_transforms import BaseTransformer


class AttrsTransformer(BaseTransformer):
    """Transform attrs 21.x code to 23.x+."""

    def __init__(self) -> None:
        super().__init__()
        self._needs_attrs_import = False
        self._needs_define_import = False
        self._needs_frozen_import = False
        self._needs_field_import = False
        self._needs_factory_import = False
        self._has_attr_import = False
        self._has_attrs_import = False

    def visit_Import(self, node: cst.Import) -> bool:
        """Track import attr statements."""
        if isinstance(node.names, cst.ImportStar):
            return True
        for name in node.names:
            if isinstance(name, cst.ImportAlias):
                if isinstance(name.name, cst.Name):
                    if name.name.value == "attr":
                        self._has_attr_import = True
                    elif name.name.value == "attrs":
                        self._has_attrs_import = True
        return True

    def visit_ImportFrom(self, node: cst.ImportFrom) -> bool:
        """Track from attr/attrs import statements."""
        if node.module is None:
            return True
        module_name = self._get_module_name(node.module)
        if module_name == "attr" or module_name.startswith("attr."):
            self._has_attr_import = True
        elif module_name == "attrs" or module_name.startswith("attrs."):
            self._has_attrs_import = True
        return True

    def leave_Import(self, original_node: cst.Import, updated_node: cst.Import) -> cst.Import:
        """Transform import attr to import attrs."""
        if isinstance(updated_node.names, cst.ImportStar):
            return updated_node

        new_names = []
        changed = False

        for name in updated_node.names:
            if isinstance(name, cst.ImportAlias):
                if isinstance(name.name, cst.Name) and name.name.value == "attr":
                    # Transform import attr to import attrs
                    new_names.append(name.with_changes(name=cst.Name("attrs")))
                    changed = True
                    self.record_change(
                        description="Change 'import attr' to 'import attrs'",
                        line_number=1,
                        original="import attr",
                        replacement="import attrs",
                        transform_name="import_attr_to_attrs",
                    )
                else:
                    new_names.append(name)
            else:
                new_names.append(name)

        if changed:
            return updated_node.with_changes(names=new_names)
        return updated_node

    def leave_ImportFrom(
        self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
    ) -> cst.ImportFrom:
        """Transform from attr import ... to from attrs import ..."""
        if updated_node.module is None:
            return updated_node

        module_name = self._get_module_name(updated_node.module)

        # Transform from attr import ...
        if module_name == "attr":
            self.record_change(
                description="Change 'from attr import' to 'from attrs import'",
                line_number=1,
                original="from attr import ...",
                replacement="from attrs import ...",
                transform_name="from_attr_to_attrs",
            )
            # Also transform imported names
            names = updated_node.names
            if not isinstance(names, cst.ImportStar):
                names = tuple(names)
            new_names = self._transform_import_names(names)
            return updated_node.with_changes(module=cst.Name("attrs"), names=new_names)

        # Transform from attr.validators import ...
        if module_name == "attr.validators":
            self.record_change(
                description="Change 'from attr.validators' to 'from attrs.validators'",
                line_number=1,
                original="from attr.validators import ...",
                replacement="from attrs.validators import ...",
                transform_name="attr_validators_to_attrs_validators",
            )
            return updated_node.with_changes(
                module=cst.Attribute(value=cst.Name("attrs"), attr=cst.Name("validators"))
            )

        # Transform from attr.converters import ...
        if module_name == "attr.converters":
            self.record_change(
                description="Change 'from attr.converters' to 'from attrs.converters'",
                line_number=1,
                original="from attr.converters import ...",
                replacement="from attrs.converters import ...",
                transform_name="attr_converters_to_attrs_converters",
            )
            return updated_node.with_changes(
                module=cst.Attribute(value=cst.Name("attrs"), attr=cst.Name("converters"))
            )

        return updated_node

    def _transform_import_names(
        self, names: cst.ImportStar | tuple[cst.ImportAlias, ...]
    ) -> cst.ImportStar | list[cst.ImportAlias]:
        """Transform imported names from attr to attrs naming conventions."""
        if isinstance(names, cst.ImportStar):
            return names

        new_names = []
        name_mappings = {
            "s": "define",
            "attrs": "define",
            "ib": "field",
            "attrib": "field",
        }

        for name in names:
            if isinstance(name, cst.ImportAlias) and isinstance(name.name, cst.Name):
                old_name = name.name.value
                if old_name in name_mappings:
                    new_name = name_mappings[old_name]
                    new_names.append(name.with_changes(name=cst.Name(new_name)))
                    self.record_change(
                        description=f"Rename import '{old_name}' to '{new_name}'",
                        line_number=1,
                        original=old_name,
                        replacement=new_name,
                        transform_name=f"import_{old_name}_to_{new_name}",
                    )
                else:
                    new_names.append(name)
            else:
                new_names.append(name)

        return new_names

    def leave_Decorator(
        self, original_node: cst.Decorator, updated_node: cst.Decorator
    ) -> cst.Decorator:
        """Transform decorators like @attr.s to @attrs.define."""
        decorator = updated_node.decorator

        # Handle @attr.s or @attr.attrs
        if isinstance(decorator, cst.Attribute):
            if isinstance(decorator.value, cst.Name) and decorator.value.value == "attr":
                attr_name = decorator.attr.value
                if attr_name in ("s", "attrs"):
                    self.record_change(
                        description=f"Transform @attr.{attr_name} to @attrs.define",
                        line_number=1,
                        original=f"@attr.{attr_name}",
                        replacement="@attrs.define",
                        transform_name="attr_s_to_attrs_define",
                    )
                    return updated_node.with_changes(
                        decorator=cst.Attribute(value=cst.Name("attrs"), attr=cst.Name("define"))
                    )

        # Handle @attr.s(...) with arguments
        if isinstance(decorator, cst.Call):
            func = decorator.func
            if isinstance(func, cst.Attribute):
                if isinstance(func.value, cst.Name) and func.value.value == "attr":
                    attr_name = func.attr.value
                    if attr_name in ("s", "attrs"):
                        return self._transform_attr_s_call(updated_node, decorator)

        return updated_node

    def _transform_attr_s_call(
        self, decorator_node: cst.Decorator, call: cst.Call
    ) -> cst.Decorator:
        """Transform @attr.s(...) to appropriate attrs decorator."""
        # Check for frozen=True -> @attrs.frozen
        # Check for auto_attribs=True, slots=True -> @attrs.define (these are defaults)
        # Handle cmp parameter -> eq, order

        has_frozen = False
        new_args = []
        removed_args = []

        for arg in call.args:
            if isinstance(arg.keyword, cst.Name):
                keyword_name = arg.keyword.value

                # frozen=True -> use @attrs.frozen instead
                if keyword_name == "frozen":
                    if isinstance(arg.value, cst.Name) and arg.value.value == "True":
                        has_frozen = True
                        removed_args.append("frozen=True")
                        continue
                    else:
                        new_args.append(arg)
                        continue

                # auto_attribs=True is default in @attrs.define, remove it
                if keyword_name == "auto_attribs":
                    if isinstance(arg.value, cst.Name) and arg.value.value == "True":
                        removed_args.append("auto_attribs=True")
                        continue

                # slots=True is default in @attrs.define, remove it
                if keyword_name == "slots":
                    if isinstance(arg.value, cst.Name) and arg.value.value == "True":
                        removed_args.append("slots=True")
                        continue

                # cmp parameter -> eq and order
                if keyword_name == "cmp":
                    eq_order_args = self._transform_cmp_arg(arg)
                    new_args.extend(eq_order_args)
                    self.record_change(
                        description="Transform cmp parameter to eq and order",
                        line_number=1,
                        original="cmp=...",
                        replacement="eq=..., order=...",
                        transform_name="cmp_to_eq_order",
                    )
                    continue

                new_args.append(arg)
            else:
                new_args.append(arg)

        # Determine target decorator
        if has_frozen:
            target_decorator = "frozen"
            self.record_change(
                description="Transform @attr.s(frozen=True) to @attrs.frozen",
                line_number=1,
                original="@attr.s(frozen=True, ...)",
                replacement="@attrs.frozen(...)",
                transform_name="attr_s_frozen_to_attrs_frozen",
            )
        else:
            target_decorator = "define"
            self.record_change(
                description="Transform @attr.s(...) to @attrs.define(...)",
                line_number=1,
                original="@attr.s(...)",
                replacement="@attrs.define(...)",
                transform_name="attr_s_to_attrs_define",
            )

        # Build new decorator
        new_func = cst.Attribute(value=cst.Name("attrs"), attr=cst.Name(target_decorator))

        if new_args:
            # Fix trailing comma
            if new_args:
                last_arg = new_args[-1]
                if last_arg.comma != cst.MaybeSentinel.DEFAULT:
                    new_args[-1] = last_arg.with_changes(comma=cst.MaybeSentinel.DEFAULT)
            new_call = call.with_changes(func=new_func, args=new_args)
        else:
            # No args left, use simple attribute
            return decorator_node.with_changes(decorator=new_func)

        return decorator_node.with_changes(decorator=new_call)

    def _transform_cmp_arg(self, arg: cst.Arg) -> list[cst.Arg]:
        """Transform cmp=X to eq=X, order=X."""
        value = arg.value
        return [
            cst.Arg(
                keyword=cst.Name("eq"),
                value=value,
                equal=cst.AssignEqual(
                    whitespace_before=cst.SimpleWhitespace(""),
                    whitespace_after=cst.SimpleWhitespace(""),
                ),
            ),
            cst.Arg(
                keyword=cst.Name("order"),
                value=value,
                equal=cst.AssignEqual(
                    whitespace_before=cst.SimpleWhitespace(""),
                    whitespace_after=cst.SimpleWhitespace(""),
                ),
            ),
        ]

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        """Transform function calls like attr.ib() to attrs.field()."""
        func = updated_node.func

        # Handle attr.ib() or attr.attrib()
        if isinstance(func, cst.Attribute):
            if isinstance(func.value, cst.Name) and func.value.value == "attr":
                attr_name = func.attr.value

                # attr.ib() / attr.attrib() -> attrs.field()
                if attr_name in ("ib", "attrib"):
                    self.record_change(
                        description=f"Transform attr.{attr_name}() to attrs.field()",
                        line_number=1,
                        original=f"attr.{attr_name}(...)",
                        replacement="attrs.field(...)",
                        transform_name="attr_ib_to_attrs_field",
                    )
                    # Transform cmp parameter in field calls too
                    new_args = self._transform_field_args(tuple(updated_node.args))
                    return updated_node.with_changes(
                        func=cst.Attribute(value=cst.Name("attrs"), attr=cst.Name("field")),
                        args=new_args,
                    )

                # attr.Factory -> attrs.Factory
                if attr_name == "Factory":
                    self.record_change(
                        description="Transform attr.Factory to attrs.Factory",
                        line_number=1,
                        original="attr.Factory(...)",
                        replacement="attrs.Factory(...)",
                        transform_name="attr_factory_to_attrs_factory",
                    )
                    return updated_node.with_changes(
                        func=cst.Attribute(value=cst.Name("attrs"), attr=cst.Name("Factory"))
                    )

                # attr.asdict -> attrs.asdict
                if attr_name == "asdict":
                    self.record_change(
                        description="Transform attr.asdict() to attrs.asdict()",
                        line_number=1,
                        original="attr.asdict(...)",
                        replacement="attrs.asdict(...)",
                        transform_name="attr_asdict_to_attrs_asdict",
                    )
                    return updated_node.with_changes(
                        func=cst.Attribute(value=cst.Name("attrs"), attr=cst.Name("asdict"))
                    )

                # attr.astuple -> attrs.astuple
                if attr_name == "astuple":
                    self.record_change(
                        description="Transform attr.astuple() to attrs.astuple()",
                        line_number=1,
                        original="attr.astuple(...)",
                        replacement="attrs.astuple(...)",
                        transform_name="attr_astuple_to_attrs_astuple",
                    )
                    return updated_node.with_changes(
                        func=cst.Attribute(value=cst.Name("attrs"), attr=cst.Name("astuple"))
                    )

                # attr.fields -> attrs.fields
                if attr_name == "fields":
                    self.record_change(
                        description="Transform attr.fields() to attrs.fields()",
                        line_number=1,
                        original="attr.fields(...)",
                        replacement="attrs.fields(...)",
                        transform_name="attr_fields_to_attrs_fields",
                    )
                    return updated_node.with_changes(
                        func=cst.Attribute(value=cst.Name("attrs"), attr=cst.Name("fields"))
                    )

                # attr.has -> attrs.has
                if attr_name == "has":
                    self.record_change(
                        description="Transform attr.has() to attrs.has()",
                        line_number=1,
                        original="attr.has(...)",
                        replacement="attrs.has(...)",
                        transform_name="attr_has_to_attrs_has",
                    )
                    return updated_node.with_changes(
                        func=cst.Attribute(value=cst.Name("attrs"), attr=cst.Name("has"))
                    )

                # attr.evolve -> attrs.evolve
                if attr_name == "evolve":
                    self.record_change(
                        description="Transform attr.evolve() to attrs.evolve()",
                        line_number=1,
                        original="attr.evolve(...)",
                        replacement="attrs.evolve(...)",
                        transform_name="attr_evolve_to_attrs_evolve",
                    )
                    return updated_node.with_changes(
                        func=cst.Attribute(value=cst.Name("attrs"), attr=cst.Name("evolve"))
                    )

                # attr.validate -> attrs.validate
                if attr_name == "validate":
                    self.record_change(
                        description="Transform attr.validate() to attrs.validate()",
                        line_number=1,
                        original="attr.validate(...)",
                        replacement="attrs.validate(...)",
                        transform_name="attr_validate_to_attrs_validate",
                    )
                    return updated_node.with_changes(
                        func=cst.Attribute(value=cst.Name("attrs"), attr=cst.Name("validate"))
                    )

        # Handle attr.validators.* calls
        if isinstance(func, cst.Attribute):
            if isinstance(func.value, cst.Attribute):
                if (
                    isinstance(func.value.value, cst.Name)
                    and func.value.value.value == "attr"
                    and func.value.attr.value == "validators"
                ):
                    validator_name = func.attr.value
                    self.record_change(
                        description=f"Transform attr.validators.{validator_name}() to attrs.validators.{validator_name}()",
                        line_number=1,
                        original=f"attr.validators.{validator_name}(...)",
                        replacement=f"attrs.validators.{validator_name}(...)",
                        transform_name="attr_validators_to_attrs_validators",
                    )
                    return updated_node.with_changes(
                        func=cst.Attribute(
                            value=cst.Attribute(
                                value=cst.Name("attrs"), attr=cst.Name("validators")
                            ),
                            attr=cst.Name(validator_name),
                        )
                    )

        # Handle attr.converters.* calls
        if isinstance(func, cst.Attribute):
            if isinstance(func.value, cst.Attribute):
                if (
                    isinstance(func.value.value, cst.Name)
                    and func.value.value.value == "attr"
                    and func.value.attr.value == "converters"
                ):
                    converter_name = func.attr.value
                    self.record_change(
                        description=f"Transform attr.converters.{converter_name}() to attrs.converters.{converter_name}()",
                        line_number=1,
                        original=f"attr.converters.{converter_name}(...)",
                        replacement=f"attrs.converters.{converter_name}(...)",
                        transform_name="attr_converters_to_attrs_converters",
                    )
                    return updated_node.with_changes(
                        func=cst.Attribute(
                            value=cst.Attribute(
                                value=cst.Name("attrs"), attr=cst.Name("converters")
                            ),
                            attr=cst.Name(converter_name),
                        )
                    )

        return updated_node

    def _transform_field_args(self, args: tuple[cst.Arg, ...]) -> list[cst.Arg]:
        """Transform field arguments, handling cmp -> eq, order."""
        new_args = []
        for arg in args:
            if isinstance(arg.keyword, cst.Name) and arg.keyword.value == "cmp":
                # cmp=X -> eq=X, order=X
                new_args.extend(self._transform_cmp_arg(arg))
                self.record_change(
                    description="Transform cmp parameter to eq and order in field",
                    line_number=1,
                    original="cmp=...",
                    replacement="eq=..., order=...",
                    transform_name="cmp_to_eq_order",
                )
            else:
                new_args.append(arg)
        return new_args

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.Attribute:
        """Transform attribute accesses like attr.validators to attrs.validators."""
        # Handle attr.validators, attr.converters as module access (not calls)
        if isinstance(updated_node.value, cst.Name) and updated_node.value.value == "attr":
            attr_name = updated_node.attr.value

            # attr.validators -> attrs.validators
            if attr_name == "validators":
                self.record_change(
                    description="Transform attr.validators to attrs.validators",
                    line_number=1,
                    original="attr.validators",
                    replacement="attrs.validators",
                    transform_name="attr_validators_to_attrs_validators",
                )
                return updated_node.with_changes(value=cst.Name("attrs"))

            # attr.converters -> attrs.converters
            if attr_name == "converters":
                self.record_change(
                    description="Transform attr.converters to attrs.converters",
                    line_number=1,
                    original="attr.converters",
                    replacement="attrs.converters",
                    transform_name="attr_converters_to_attrs_converters",
                )
                return updated_node.with_changes(value=cst.Name("attrs"))

        return updated_node

    def _get_module_name(self, module: cst.BaseExpression) -> str:
        """Get the full module name from a Name or Attribute node."""
        if isinstance(module, cst.Name):
            return str(module.value)
        elif isinstance(module, cst.Attribute):
            return f"{self._get_module_name(module.value)}.{module.attr.value}"
        return ""


def transform_attrs(source_code: str) -> tuple[str, list]:
    """Transform attrs code from 21.x to 23.x+.

    Args:
        source_code: The source code to transform

    Returns:
        Tuple of (transformed_code, list of changes)
    """
    try:
        tree = cst.parse_module(source_code)
    except cst.ParserSyntaxError:
        return source_code, []

    transformer = AttrsTransformer()
    transformer.set_source(source_code)

    try:
        transformed_tree = tree.visit(transformer)
        return transformed_tree.code, transformer.changes
    except Exception:
        return source_code, []
