"""Click 7.x to 8.x transformation using LibCST."""

import libcst as cst

from codeshift.migrator.ast_transforms import BaseTransformer


class ClickTransformer(BaseTransformer):
    """Transform Click 7.x code to 8.x."""

    def __init__(self) -> None:
        super().__init__()
        # Track imports needed
        self._needs_shutil_import = False
        self._needs_sys_import = False
        self._needs_importlib_metadata = False
        self._has_shutil_import = False
        self._has_sys_import = False
        self._has_importlib_metadata_import = False
        # Track click imports for transforming
        self._has_click_import = False

    def leave_ImportFrom(
        self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
    ) -> cst.ImportFrom:
        """Transform Click imports and track existing imports."""
        if updated_node.module is None:
            return updated_node

        module_name = self._get_module_name(updated_node.module)

        # Track existing imports
        if module_name == "shutil":
            self._has_shutil_import = True
        elif module_name == "sys":
            self._has_sys_import = True
        elif module_name == "importlib.metadata" or module_name == "importlib":
            self._has_importlib_metadata_import = True
        elif module_name == "click":
            self._has_click_import = True

            # Transform deprecated class imports
            if isinstance(updated_node.names, cst.ImportStar):
                return updated_node

            new_names = []
            changed = False

            for name in updated_node.names:
                if isinstance(name, cst.ImportAlias):
                    imported_name = self._get_name_value(name.name)

                    if imported_name == "MultiCommand":
                        new_names.append(name.with_changes(name=cst.Name("Group")))
                        changed = True
                        self.record_change(
                            description="Replace MultiCommand import with Group",
                            line_number=1,
                            original="from click import MultiCommand",
                            replacement="from click import Group",
                            transform_name="multicommand_to_group",
                        )
                    elif imported_name == "BaseCommand":
                        new_names.append(name.with_changes(name=cst.Name("Command")))
                        changed = True
                        self.record_change(
                            description="Replace BaseCommand import with Command",
                            line_number=1,
                            original="from click import BaseCommand",
                            replacement="from click import Command",
                            transform_name="basecommand_to_command",
                        )
                    else:
                        new_names.append(name)

            if changed:
                return updated_node.with_changes(names=new_names)

        return updated_node

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.BaseExpression:
        """Transform attribute access like result.output_bytes and click.__version__."""
        attr_name = updated_node.attr.value

        # Handle result.output_bytes -> result.output.encode()
        if attr_name == "output_bytes":
            self.record_change(
                description="Replace .output_bytes with .output.encode()",
                line_number=1,
                original=".output_bytes",
                replacement=".output.encode()",
                transform_name="output_bytes_to_encode",
            )
            # Transform to .output.encode()
            output_attr = cst.Attribute(
                value=updated_node.value,
                attr=cst.Name("output"),
            )
            return cst.Call(
                func=cst.Attribute(
                    value=output_attr,
                    attr=cst.Name("encode"),
                ),
                args=[],
            )

        # Handle click.__version__ -> importlib.metadata.version("click")
        if attr_name == "__version__":
            if isinstance(updated_node.value, cst.Name) and updated_node.value.value == "click":
                self._needs_importlib_metadata = True
                self.record_change(
                    description="Replace click.__version__ with importlib.metadata.version('click')",
                    line_number=1,
                    original="click.__version__",
                    replacement="importlib.metadata.version('click')",
                    transform_name="version_attr_to_importlib",
                )
                return cst.Call(
                    func=cst.Attribute(
                        value=cst.Attribute(
                            value=cst.Name("importlib"),
                            attr=cst.Name("metadata"),
                        ),
                        attr=cst.Name("version"),
                    ),
                    args=[cst.Arg(value=cst.SimpleString('"click"'))],
                )

        return updated_node

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.BaseExpression:
        """Transform function calls."""
        # Handle click.get_terminal_size() -> shutil.get_terminal_size()
        if self._is_click_call(updated_node, "get_terminal_size"):
            self._needs_shutil_import = True
            self.record_change(
                description="Replace click.get_terminal_size() with shutil.get_terminal_size()",
                line_number=1,
                original="click.get_terminal_size()",
                replacement="shutil.get_terminal_size()",
                transform_name="get_terminal_size_to_shutil",
            )
            return cst.Call(
                func=cst.Attribute(
                    value=cst.Name("shutil"),
                    attr=cst.Name("get_terminal_size"),
                ),
                args=updated_node.args,
            )

        # Handle click.get_os_args() -> sys.argv[1:]
        if self._is_click_call(updated_node, "get_os_args"):
            self._needs_sys_import = True
            self.record_change(
                description="Replace click.get_os_args() with sys.argv[1:]",
                line_number=1,
                original="click.get_os_args()",
                replacement="sys.argv[1:]",
                transform_name="get_os_args_to_sys_argv",
            )
            return cst.Subscript(
                value=cst.Attribute(
                    value=cst.Name("sys"),
                    attr=cst.Name("argv"),
                ),
                slice=[
                    cst.SubscriptElement(
                        slice=cst.Slice(
                            lower=cst.Integer("1"),
                            upper=None,
                        )
                    )
                ],
            )

        # Handle CliRunner(..., mix_stderr=...) -> CliRunner(...)
        if isinstance(updated_node.func, cst.Name) and updated_node.func.value == "CliRunner":
            new_args = []
            changed = False

            for arg in updated_node.args:
                if isinstance(arg.keyword, cst.Name) and arg.keyword.value == "mix_stderr":
                    changed = True
                    self.record_change(
                        description="Remove deprecated mix_stderr parameter from CliRunner",
                        line_number=1,
                        original="CliRunner(mix_stderr=...)",
                        replacement="CliRunner()",
                        transform_name="clirunner_remove_mix_stderr",
                    )
                else:
                    new_args.append(arg)

            if changed:
                return updated_node.with_changes(args=new_args)

        # Handle @click.option/argument(..., autocompletion=...) -> shell_complete=...
        if isinstance(updated_node.func, cst.Attribute):
            if isinstance(updated_node.func.value, cst.Name):
                if updated_node.func.value.value == "click":
                    attr_name = updated_node.func.attr.value
                    if attr_name in ("option", "argument"):
                        return self._transform_autocompletion_param(updated_node, attr_name)

        # Also handle decorators without click. prefix (e.g., from click import option)
        if isinstance(updated_node.func, cst.Name):
            func_name = updated_node.func.value
            if func_name in ("option", "argument"):
                return self._transform_autocompletion_param(updated_node, func_name)

        return updated_node

    def _transform_autocompletion_param(self, node: cst.Call, decorator_name: str) -> cst.Call:
        """Transform autocompletion parameter to shell_complete."""
        new_args = []
        changed = False

        for arg in node.args:
            if isinstance(arg.keyword, cst.Name) and arg.keyword.value == "autocompletion":
                new_arg = arg.with_changes(keyword=cst.Name("shell_complete"))
                new_args.append(new_arg)
                changed = True

                self.record_change(
                    description=f"Rename {decorator_name}(autocompletion=...) to {decorator_name}(shell_complete=...)",
                    line_number=1,
                    original=f"@click.{decorator_name}(autocompletion=...)",
                    replacement=f"@click.{decorator_name}(shell_complete=...)",
                    transform_name="autocompletion_to_shell_complete",
                    notes="Callback signature changed from (ctx, args, incomplete) to (ctx, param, incomplete)",
                )
            else:
                new_args.append(arg)

        if changed:
            return node.with_changes(args=new_args)

        return node

    def leave_Decorator(
        self, original_node: cst.Decorator, updated_node: cst.Decorator
    ) -> cst.Decorator:
        """Transform decorator calls like @group.resultcallback to @group.result_callback."""
        # Handle @group.resultcallback -> @group.result_callback
        if isinstance(updated_node.decorator, cst.Call):
            if isinstance(updated_node.decorator.func, cst.Attribute):
                if updated_node.decorator.func.attr.value == "resultcallback":
                    new_func = updated_node.decorator.func.with_changes(
                        attr=cst.Name("result_callback")
                    )
                    new_call_decorator = updated_node.decorator.with_changes(func=new_func)

                    self.record_change(
                        description="Rename @group.resultcallback() to @group.result_callback()",
                        line_number=1,
                        original="@group.resultcallback()",
                        replacement="@group.result_callback()",
                        transform_name="resultcallback_to_result_callback",
                    )

                    return updated_node.with_changes(decorator=new_call_decorator)

        elif isinstance(updated_node.decorator, cst.Attribute):
            if updated_node.decorator.attr.value == "resultcallback":
                new_attr_decorator = updated_node.decorator.with_changes(
                    attr=cst.Name("result_callback")
                )

                self.record_change(
                    description="Rename @group.resultcallback to @group.result_callback",
                    line_number=1,
                    original="@group.resultcallback",
                    replacement="@group.result_callback",
                    transform_name="resultcallback_to_result_callback",
                )

                return updated_node.with_changes(decorator=new_attr_decorator)

        return updated_node

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        """Transform class definitions that inherit from deprecated base classes."""
        if not updated_node.bases:
            return updated_node

        new_bases = []
        changed = False

        for base in updated_node.bases:
            if isinstance(base.value, cst.Attribute):
                # Handle click.MultiCommand, click.BaseCommand
                if isinstance(base.value.value, cst.Name) and base.value.value.value == "click":
                    if base.value.attr.value == "MultiCommand":
                        new_base = base.with_changes(
                            value=cst.Attribute(
                                value=cst.Name("click"),
                                attr=cst.Name("Group"),
                            )
                        )
                        new_bases.append(new_base)
                        changed = True
                        self.record_change(
                            description="Replace click.MultiCommand with click.Group as base class",
                            line_number=1,
                            original="class MyClass(click.MultiCommand)",
                            replacement="class MyClass(click.Group)",
                            transform_name="multicommand_to_group",
                        )
                        continue
                    elif base.value.attr.value == "BaseCommand":
                        new_base = base.with_changes(
                            value=cst.Attribute(
                                value=cst.Name("click"),
                                attr=cst.Name("Command"),
                            )
                        )
                        new_bases.append(new_base)
                        changed = True
                        self.record_change(
                            description="Replace click.BaseCommand with click.Command as base class",
                            line_number=1,
                            original="class MyClass(click.BaseCommand)",
                            replacement="class MyClass(click.Command)",
                            transform_name="basecommand_to_command",
                        )
                        continue

            elif isinstance(base.value, cst.Name):
                # Handle MultiCommand, BaseCommand (imported directly)
                if base.value.value == "MultiCommand":
                    new_base = base.with_changes(value=cst.Name("Group"))
                    new_bases.append(new_base)
                    changed = True
                    self.record_change(
                        description="Replace MultiCommand with Group as base class",
                        line_number=1,
                        original="class MyClass(MultiCommand)",
                        replacement="class MyClass(Group)",
                        transform_name="multicommand_to_group",
                    )
                    continue
                elif base.value.value == "BaseCommand":
                    new_base = base.with_changes(value=cst.Name("Command"))
                    new_bases.append(new_base)
                    changed = True
                    self.record_change(
                        description="Replace BaseCommand with Command as base class",
                        line_number=1,
                        original="class MyClass(BaseCommand)",
                        replacement="class MyClass(Command)",
                        transform_name="basecommand_to_command",
                    )
                    continue

            new_bases.append(base)

        if changed:
            return updated_node.with_changes(bases=new_bases)

        return updated_node

    def _is_click_call(self, node: cst.Call, func_name: str) -> bool:
        """Check if a call is click.<func_name>()."""
        if isinstance(node.func, cst.Attribute):
            if isinstance(node.func.value, cst.Name):
                return bool(node.func.value.value == "click" and node.func.attr.value == func_name)
        return False

    def _get_module_name(self, module: cst.BaseExpression) -> str:
        """Get the full module name from a Name or Attribute node."""
        if isinstance(module, cst.Name):
            return str(module.value)
        elif isinstance(module, cst.Attribute):
            return f"{self._get_module_name(module.value)}.{module.attr.value}"
        return ""

    def _get_name_value(self, node: cst.BaseExpression) -> str | None:
        """Extract the string value from a Name node."""
        if isinstance(node, cst.Name):
            return str(node.value)
        return None


class ClickImportTransformer(BaseTransformer):
    """Separate transformer for handling import additions.

    This runs after the main transformer to add any missing imports.
    """

    def __init__(
        self,
        needs_shutil: bool = False,
        needs_sys: bool = False,
        needs_importlib_metadata: bool = False,
    ) -> None:
        super().__init__()
        self.needs_shutil = needs_shutil
        self.needs_sys = needs_sys
        self.needs_importlib_metadata = needs_importlib_metadata
        self._added_shutil = False
        self._added_sys = False
        self._added_importlib = False

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        """Add missing imports at the beginning of the module."""
        new_imports: list[cst.SimpleStatementLine] = []

        # Check if imports already exist
        for stmt in updated_node.body:
            if isinstance(stmt, cst.SimpleStatementLine):
                for item in stmt.body:
                    if isinstance(item, cst.Import):
                        for name in (
                            item.names if not isinstance(item.names, cst.ImportStar) else []
                        ):
                            if isinstance(name, cst.ImportAlias):
                                name_val = self._get_name_value(name.name)
                                if name_val == "shutil":
                                    self._added_shutil = True
                                elif name_val == "sys":
                                    self._added_sys = True
                                elif name_val == "importlib":
                                    self._added_importlib = True
                    elif isinstance(item, cst.ImportFrom):
                        if item.module:
                            mod_name = self._get_module_name(item.module)
                            if mod_name == "shutil":
                                self._added_shutil = True
                            elif mod_name == "sys":
                                self._added_sys = True
                            elif mod_name.startswith("importlib"):
                                self._added_importlib = True

        # Add needed imports
        if self.needs_shutil and not self._added_shutil:
            new_imports.append(
                cst.SimpleStatementLine(
                    body=[cst.Import(names=[cst.ImportAlias(name=cst.Name("shutil"))])]
                )
            )

        if self.needs_sys and not self._added_sys:
            new_imports.append(
                cst.SimpleStatementLine(
                    body=[cst.Import(names=[cst.ImportAlias(name=cst.Name("sys"))])]
                )
            )

        if self.needs_importlib_metadata and not self._added_importlib:
            new_imports.append(
                cst.SimpleStatementLine(
                    body=[cst.Import(names=[cst.ImportAlias(name=cst.Name("importlib"))])]
                )
            )

        if new_imports:
            # Insert imports at the beginning, after any existing imports/docstrings
            insert_pos = 0
            for i, stmt in enumerate(updated_node.body):
                if isinstance(stmt, cst.SimpleStatementLine):
                    if any(
                        isinstance(s, cst.Import | cst.ImportFrom | cst.Expr) for s in stmt.body
                    ):
                        insert_pos = i + 1
                elif isinstance(stmt, cst.IndentedBlock | cst.Expr):
                    # Skip docstrings
                    insert_pos = i + 1
                else:
                    break

            new_body = (
                list(updated_node.body[:insert_pos])
                + new_imports
                + list(updated_node.body[insert_pos:])
            )
            return updated_node.with_changes(body=new_body)

        return updated_node

    def _get_module_name(self, module: cst.BaseExpression) -> str:
        """Get the full module name from a Name or Attribute node."""
        if isinstance(module, cst.Name):
            return str(module.value)
        elif isinstance(module, cst.Attribute):
            return f"{self._get_module_name(module.value)}.{module.attr.value}"
        return ""

    def _get_name_value(self, node: cst.BaseExpression) -> str | None:
        """Extract the string value from a Name node."""
        if isinstance(node, cst.Name):
            return str(node.value)
        return None


def transform_click(source_code: str) -> tuple[str, list]:
    """Transform Click 7.x code to 8.x.

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
    transformer = ClickTransformer()
    transformer.set_source(source_code)
    transformed_tree = tree.visit(transformer)

    # Second pass: add missing imports
    import_transformer = ClickImportTransformer(
        needs_shutil=transformer._needs_shutil_import,
        needs_sys=transformer._needs_sys_import,
        needs_importlib_metadata=transformer._needs_importlib_metadata,
    )
    final_tree = transformed_tree.visit(import_transformer)

    return final_tree.code, transformer.changes
