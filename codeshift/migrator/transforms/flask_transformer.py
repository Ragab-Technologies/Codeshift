"""Flask transformation using LibCST for Flask 1.x to 2.x/3.x migrations."""

import libcst as cst

from codeshift.migrator.ast_transforms import BaseTransformer


class FlaskTransformer(BaseTransformer):
    """Transform Flask code for version upgrades (1.x to 2.x/3.x)."""

    def __init__(self) -> None:
        super().__init__()
        # Track imports that need to be added
        self._needs_markupsafe_escape = False
        self._needs_markupsafe_markup = False
        self._needs_werkzeug_safe_join = False
        self._needs_json_import = False
        # Track what flask imports exist
        self._has_flask_escape_import = False
        self._has_flask_markup_import = False
        self._has_flask_safe_join_import = False
        # Track if markupsafe import already exists
        self._has_markupsafe_import = False
        self._markupsafe_import_names: set[str] = set()

    def leave_ImportFrom(
        self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
    ) -> cst.BaseSmallStatement | cst.RemovalSentinel:
        """Transform Flask imports to their new locations."""
        if updated_node.module is None:
            return updated_node

        module_name = self._get_module_name(updated_node.module)

        # Handle flask imports
        if module_name == "flask":
            return self._handle_flask_import(updated_node)

        # Handle flask.globals imports (deprecated context stacks)
        if module_name == "flask.globals":
            return self._handle_flask_globals_import(updated_node)

        # Track existing markupsafe imports
        if module_name == "markupsafe":
            self._has_markupsafe_import = True
            if not isinstance(updated_node.names, cst.ImportStar):
                for name in updated_node.names:
                    if isinstance(name, cst.ImportAlias):
                        imported = self._get_name_value(name.name)
                        if imported:
                            self._markupsafe_import_names.add(imported)

        return updated_node

    def _handle_flask_import(self, node: cst.ImportFrom) -> cst.ImportFrom | cst.RemovalSentinel:
        """Handle imports from flask module."""
        if isinstance(node.names, cst.ImportStar):
            return node

        new_names = []
        changed = False

        for name in node.names:
            if isinstance(name, cst.ImportAlias):
                imported_name = self._get_name_value(name.name)

                if imported_name == "escape":
                    # Mark for adding markupsafe import
                    self._needs_markupsafe_escape = True
                    self._has_flask_escape_import = True
                    changed = True
                    self.record_change(
                        description="Move 'escape' import from flask to markupsafe",
                        line_number=1,
                        original="from flask import escape",
                        replacement="from markupsafe import escape",
                        transform_name="flask_escape_to_markupsafe",
                    )
                    # Don't add to new_names - we'll add markupsafe import later
                    continue

                elif imported_name == "Markup":
                    # Mark for adding markupsafe import
                    self._needs_markupsafe_markup = True
                    self._has_flask_markup_import = True
                    changed = True
                    self.record_change(
                        description="Move 'Markup' import from flask to markupsafe",
                        line_number=1,
                        original="from flask import Markup",
                        replacement="from markupsafe import Markup",
                        transform_name="flask_markup_to_markupsafe",
                    )
                    # Don't add to new_names - we'll add markupsafe import later
                    continue

                elif imported_name == "safe_join":
                    # Mark for adding werkzeug import
                    self._needs_werkzeug_safe_join = True
                    self._has_flask_safe_join_import = True
                    changed = True
                    self.record_change(
                        description="Move 'safe_join' import from flask to werkzeug.utils",
                        line_number=1,
                        original="from flask import safe_join",
                        replacement="from werkzeug.utils import safe_join",
                        transform_name="flask_safe_join_to_werkzeug",
                    )
                    # Don't add to new_names
                    continue

            new_names.append(name)

        if changed:
            if not new_names:
                # All imports were moved, remove the flask import line
                return cst.RemovalSentinel.REMOVE
            return node.with_changes(names=new_names)

        return node

    def _handle_flask_globals_import(
        self, node: cst.ImportFrom
    ) -> cst.BaseSmallStatement | cst.RemovalSentinel:
        """Handle imports from flask.globals (deprecated context stacks)."""
        if isinstance(node.names, cst.ImportStar):
            return node

        new_names = []
        changed = False

        for name in node.names:
            if isinstance(name, cst.ImportAlias):
                imported_name = self._get_name_value(name.name)

                if imported_name in ("_app_ctx_stack", "_request_ctx_stack"):
                    changed = True
                    self.record_change(
                        description=f"Remove deprecated '{imported_name}' import, use flask.g instead",
                        line_number=1,
                        original=f"from flask.globals import {imported_name}",
                        replacement="from flask import g",
                        transform_name=f"{imported_name.lstrip('_')}_to_g",
                    )
                    continue

            new_names.append(name)

        if changed:
            if not new_names:
                return cst.RemovalSentinel.REMOVE
            return node.with_changes(names=new_names)

        return node

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        """Transform Flask function calls."""
        # Handle send_file parameter renames
        if self._is_call_to(updated_node, "send_file"):
            return self._transform_send_file(updated_node)

        # Handle send_from_directory parameter renames
        if self._is_call_to(updated_node, "send_from_directory"):
            return self._transform_send_from_directory(updated_node)

        # Handle app.config.from_json -> app.config.from_file
        if self._is_method_call(updated_node, "from_json"):
            return self._transform_from_json(updated_node)

        return updated_node

    def _transform_send_file(self, node: cst.Call) -> cst.Call:
        """Transform send_file() parameter names."""
        new_args = []
        changed = False

        param_renames = {
            "attachment_filename": (
                "download_name",
                "send_file_attachment_filename_to_download_name",
            ),
            "cache_timeout": ("max_age", "send_file_cache_timeout_to_max_age"),
            "add_etags": ("etag", "send_file_add_etags_to_etag"),
        }

        for arg in node.args:
            if isinstance(arg.keyword, cst.Name):
                keyword_name = arg.keyword.value
                if keyword_name in param_renames:
                    new_name, transform_name = param_renames[keyword_name]
                    new_args.append(arg.with_changes(keyword=cst.Name(new_name)))
                    changed = True
                    self.record_change(
                        description=f"Rename send_file({keyword_name}=...) to send_file({new_name}=...)",
                        line_number=1,
                        original=f"send_file({keyword_name}=...)",
                        replacement=f"send_file({new_name}=...)",
                        transform_name=transform_name,
                    )
                else:
                    new_args.append(arg)
            else:
                new_args.append(arg)

        if changed:
            return node.with_changes(args=new_args)
        return node

    def _transform_send_from_directory(self, node: cst.Call) -> cst.Call:
        """Transform send_from_directory() parameter names."""
        new_args = []
        changed = False

        for arg in node.args:
            if isinstance(arg.keyword, cst.Name) and arg.keyword.value == "filename":
                new_args.append(arg.with_changes(keyword=cst.Name("path")))
                changed = True
                self.record_change(
                    description="Rename send_from_directory(filename=...) to send_from_directory(path=...)",
                    line_number=1,
                    original="send_from_directory(filename=...)",
                    replacement="send_from_directory(path=...)",
                    transform_name="send_from_directory_filename_to_path",
                )
            else:
                new_args.append(arg)

        if changed:
            return node.with_changes(args=new_args)
        return node

    def _transform_from_json(self, node: cst.Call) -> cst.Call:
        """Transform config.from_json() to config.from_file() with json.load."""
        # Check if this is actually a from_json call on config
        if not isinstance(node.func, cst.Attribute):
            return node

        if node.func.attr.value != "from_json":
            return node

        # Check the call chain to see if it's on config
        value = node.func.value
        is_config_call = False
        if isinstance(value, cst.Attribute) and value.attr.value == "config":
            is_config_call = True
        elif isinstance(value, cst.Name) and value.value == "config":
            is_config_call = True

        if not is_config_call:
            return node

        # Get the first positional argument (the filename)
        if not node.args:
            return node

        file_arg = node.args[0]

        # Transform from_json to from_file with json.load
        self._needs_json_import = True

        # Build new arguments: (filename, load=json.load)
        new_args = [
            file_arg,
            cst.Arg(
                keyword=cst.Name("load"),
                value=cst.Attribute(
                    value=cst.Name("json"),
                    attr=cst.Name("load"),
                ),
                equal=cst.AssignEqual(
                    whitespace_before=cst.SimpleWhitespace(""),
                    whitespace_after=cst.SimpleWhitespace(""),
                ),
            ),
        ]

        # Change the method name from from_json to from_file
        new_func = node.func.with_changes(attr=cst.Name("from_file"))

        self.record_change(
            description="Convert config.from_json() to config.from_file() with json.load",
            line_number=1,
            original="config.from_json('file.json')",
            replacement="config.from_file('file.json', load=json.load)",
            transform_name="config_from_json_to_from_file",
        )

        return node.with_changes(func=new_func, args=new_args)

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.BaseExpression:
        """Transform attribute access for deprecated properties."""
        attr_name = updated_node.attr.value

        # Handle app.env -> app.debug
        if attr_name == "env":
            # Check if it's likely an app.env access
            if isinstance(updated_node.value, cst.Name):
                if updated_node.value.value in ("app", "application", "current_app"):
                    self.record_change(
                        description="Convert app.env to app.debug (env property deprecated)",
                        line_number=1,
                        original="app.env",
                        replacement="app.debug",
                        transform_name="app_env_to_debug",
                    )
                    return updated_node.with_changes(attr=cst.Name("debug"))

        return updated_node

    def _is_call_to(self, node: cst.Call, func_name: str) -> bool:
        """Check if a Call node is calling a specific function."""
        if isinstance(node.func, cst.Name):
            return bool(node.func.value == func_name)
        return False

    def _is_method_call(self, node: cst.Call, method_name: str) -> bool:
        """Check if a Call node is calling a specific method."""
        if isinstance(node.func, cst.Attribute):
            return bool(node.func.attr.value == method_name)
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


class FlaskImportAdder(cst.CSTTransformer):
    """Adds new imports needed after Flask transformation."""

    def __init__(
        self,
        needs_markupsafe_escape: bool = False,
        needs_markupsafe_markup: bool = False,
        needs_werkzeug_safe_join: bool = False,
        needs_json_import: bool = False,
        has_markupsafe_import: bool = False,
        existing_markupsafe_names: set[str] | None = None,
    ) -> None:
        super().__init__()
        self.needs_markupsafe_escape = needs_markupsafe_escape
        self.needs_markupsafe_markup = needs_markupsafe_markup
        self.needs_werkzeug_safe_join = needs_werkzeug_safe_join
        self.needs_json_import = needs_json_import
        self.has_markupsafe_import = has_markupsafe_import
        self.existing_markupsafe_names = existing_markupsafe_names or set()
        self._added_imports = False
        self._has_json_import = False
        self._has_werkzeug_import = False

    def visit_ImportFrom(self, node: cst.ImportFrom) -> bool:
        """Track existing imports."""
        if node.module:
            module_name = self._get_module_name(node.module)
            if module_name == "json":
                self._has_json_import = True
            elif module_name == "werkzeug.utils":
                self._has_werkzeug_import = True
        return True

    def visit_Import(self, node: cst.Import) -> bool:
        """Track existing json import."""
        for name in node.names:
            if isinstance(name, cst.ImportAlias):
                if isinstance(name.name, cst.Name) and name.name.value == "json":
                    self._has_json_import = True
        return True

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        """Add necessary imports at the top of the module."""
        if self._added_imports:
            return updated_node

        new_imports = []

        # Add markupsafe import if needed
        if self.needs_markupsafe_escape or self.needs_markupsafe_markup:
            names_to_import = []
            if self.needs_markupsafe_escape and "escape" not in self.existing_markupsafe_names:
                names_to_import.append(cst.ImportAlias(name=cst.Name("escape")))
            if self.needs_markupsafe_markup and "Markup" not in self.existing_markupsafe_names:
                names_to_import.append(cst.ImportAlias(name=cst.Name("Markup")))

            if names_to_import:
                new_imports.append(
                    cst.SimpleStatementLine(
                        body=[
                            cst.ImportFrom(
                                module=cst.Name("markupsafe"),
                                names=names_to_import,
                            )
                        ]
                    )
                )

        # Add werkzeug.utils import if needed
        if self.needs_werkzeug_safe_join and not self._has_werkzeug_import:
            new_imports.append(
                cst.SimpleStatementLine(
                    body=[
                        cst.ImportFrom(
                            module=cst.Attribute(
                                value=cst.Name("werkzeug"),
                                attr=cst.Name("utils"),
                            ),
                            names=[cst.ImportAlias(name=cst.Name("safe_join"))],
                        )
                    ]
                )
            )

        # Add json import if needed
        if self.needs_json_import and not self._has_json_import:
            new_imports.append(
                cst.SimpleStatementLine(
                    body=[cst.Import(names=[cst.ImportAlias(name=cst.Name("json"))])]
                )
            )

        if new_imports:
            # Find the first import statement and insert before it
            new_body = list(updated_node.body)

            # Find insertion point (after module docstring, before first import)
            insert_idx = 0
            for i, stmt in enumerate(new_body):
                if isinstance(stmt, cst.SimpleStatementLine):
                    if stmt.body and isinstance(stmt.body[0], cst.Import | cst.ImportFrom):
                        insert_idx = i
                        break
                    elif stmt.body and isinstance(stmt.body[0], cst.Expr):
                        # Could be docstring, continue
                        if isinstance(stmt.body[0].value, cst.SimpleString):
                            insert_idx = i + 1
                            continue
                        insert_idx = i
                        break

            # Insert new imports
            for imp in reversed(new_imports):
                new_body.insert(insert_idx, imp)

            self._added_imports = True
            return updated_node.with_changes(body=new_body)

        return updated_node

    def _get_module_name(self, module: cst.BaseExpression) -> str:
        """Get the full module name from a Name or Attribute node."""
        if isinstance(module, cst.Name):
            return str(module.value)
        elif isinstance(module, cst.Attribute):
            return f"{self._get_module_name(module.value)}.{module.attr.value}"
        return ""


def transform_flask(source_code: str) -> tuple[str, list]:
    """Transform Flask code for version upgrades.

    Args:
        source_code: The source code to transform

    Returns:
        Tuple of (transformed_code, list of changes)
    """
    try:
        tree = cst.parse_module(source_code)
    except cst.ParserSyntaxError:
        return source_code, []

    # First pass: main transformations
    transformer = FlaskTransformer()
    transformer.set_source(source_code)

    try:
        transformed_tree = tree.visit(transformer)
    except Exception:
        return source_code, []

    # Second pass: add missing imports
    import_adder = FlaskImportAdder(
        needs_markupsafe_escape=transformer._needs_markupsafe_escape,
        needs_markupsafe_markup=transformer._needs_markupsafe_markup,
        needs_werkzeug_safe_join=transformer._needs_werkzeug_safe_join,
        needs_json_import=transformer._needs_json_import,
        has_markupsafe_import=transformer._has_markupsafe_import,
        existing_markupsafe_names=transformer._markupsafe_import_names,
    )

    try:
        final_tree = transformed_tree.visit(import_adder)
        return final_tree.code, transformer.changes
    except Exception:
        return transformed_tree.code, transformer.changes
