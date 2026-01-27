"""aiohttp 3.7 to 3.9+ transformation using LibCST."""

import libcst as cst

from codeshift.migrator.ast_transforms import BaseTransformer


class AiohttpTransformer(BaseTransformer):
    """Transform aiohttp code for version upgrades (3.7 to 3.9+).

    Handles breaking changes including:
    - Removal of loop parameter from ClientSession, TCPConnector, web.Application, etc.
    - BasicAuth.encode() removal
    - Deprecated timeout parameters (read_timeout, conn_timeout)
    - app.loop property deprecation
    - WebSocket timeout parameter rename
    - Response URL attribute changes
    - WebSocket protocol attribute rename
    """

    def __init__(self) -> None:
        super().__init__()
        self._needs_asyncio_import = False
        self._has_asyncio_import = False
        self._needs_client_timeout_import = False
        self._has_client_timeout_import = False

    def visit_ImportFrom(self, node: cst.ImportFrom) -> bool:
        """Track existing imports."""
        if node.module is None:
            return True

        module_name = self._get_module_name(node.module)

        # Track if asyncio is imported
        if module_name == "asyncio":
            self._has_asyncio_import = True

        # Track if ClientTimeout is imported from aiohttp
        if module_name == "aiohttp":
            if not isinstance(node.names, cst.ImportStar):
                for name in node.names:
                    if isinstance(name, cst.ImportAlias):
                        if isinstance(name.name, cst.Name) and name.name.value == "ClientTimeout":
                            self._has_client_timeout_import = True

        return True

    def visit_Import(self, node: cst.Import) -> bool:
        """Track import asyncio statements."""
        if isinstance(node.names, cst.ImportStar):
            return True

        for name in node.names:
            if isinstance(name, cst.ImportAlias):
                if isinstance(name.name, cst.Name) and name.name.value == "asyncio":
                    self._has_asyncio_import = True
                elif isinstance(name.name, cst.Attribute):
                    # Handle import asyncio.something
                    if self._get_module_name(name.name).startswith("asyncio"):
                        self._has_asyncio_import = True

        return True

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.BaseExpression:
        """Transform aiohttp function calls."""
        # Handle ClientSession, TCPConnector, UnixConnector, web.Application, ClientTimeout
        # with loop parameter removal
        loop_transformed = self._remove_loop_parameter(updated_node)
        if loop_transformed is not None:
            return loop_transformed

        # Handle deprecated timeout parameters (read_timeout, conn_timeout)
        timeout_transformed = self._transform_deprecated_timeouts(updated_node)
        if timeout_transformed is not None:
            return timeout_transformed

        # Handle BasicAuth.encode() -> str(BasicAuth(...))
        auth_transformed = self._transform_basicauth_encode(updated_node)
        if auth_transformed is not None:
            return auth_transformed

        # Handle ws_connect timeout -> receive_timeout
        ws_transformed = self._transform_ws_connect_timeout(updated_node)
        if ws_transformed is not None:
            return ws_transformed

        return updated_node

    def _remove_loop_parameter(self, node: cst.Call) -> cst.Call | None:
        """Remove loop parameter from aiohttp constructors.

        Handles:
        - ClientSession(loop=...)
        - TCPConnector(loop=...)
        - UnixConnector(loop=...)
        - web.Application(loop=...)
        - aiohttp.web.Application(loop=...)
        - ClientTimeout(loop=...)
        """
        func_name = self._get_call_name(node)

        # Classes that had loop parameter removed
        classes_with_loop_removed = {
            "ClientSession": "remove_loop_param_client_session",
            "TCPConnector": "remove_loop_param_tcp_connector",
            "UnixConnector": "remove_loop_param_unix_connector",
            "Application": "remove_loop_param_web_application",
            "ClientTimeout": "remove_loop_param_client_timeout",
        }

        # Check if this is one of the target classes
        target_transform = None
        for class_name, transform_name in classes_with_loop_removed.items():
            if func_name == class_name or func_name.endswith(f".{class_name}"):
                target_transform = transform_name
                break

        if target_transform is None:
            return None

        # Look for loop parameter and remove it
        new_args = []
        found_loop = False

        for arg in node.args:
            if isinstance(arg.keyword, cst.Name) and arg.keyword.value == "loop":
                found_loop = True
                continue
            new_args.append(arg)

        if not found_loop:
            return None

        # Fix trailing comma: remove trailing comma from last argument if present
        if new_args:
            last_arg = new_args[-1]
            if last_arg.comma != cst.MaybeSentinel.DEFAULT:
                new_args[-1] = last_arg.with_changes(comma=cst.MaybeSentinel.DEFAULT)

        self.record_change(
            description=f"Remove deprecated loop parameter from {func_name}",
            line_number=1,
            original=f"{func_name}(loop=...)",
            replacement=f"{func_name}()",
            transform_name=target_transform,
        )

        return node.with_changes(args=new_args)

    def _transform_deprecated_timeouts(self, node: cst.Call) -> cst.Call | None:
        """Transform deprecated read_timeout/conn_timeout to ClientTimeout.

        Handles:
        - ClientSession(read_timeout=X) -> ClientSession(timeout=ClientTimeout(total=X))
        - ClientSession(conn_timeout=X) -> ClientSession(timeout=ClientTimeout(connect=X))
        """
        func_name = self._get_call_name(node)

        if func_name != "ClientSession" and not func_name.endswith(".ClientSession"):
            return None

        new_args = []
        timeout_values: dict[str, cst.BaseExpression] = {}
        existing_timeout = None
        changed = False

        for arg in node.args:
            if isinstance(arg.keyword, cst.Name):
                if arg.keyword.value == "read_timeout":
                    timeout_values["total"] = arg.value
                    changed = True
                    self.record_change(
                        description="Convert read_timeout to ClientTimeout(total=...)",
                        line_number=1,
                        original="ClientSession(read_timeout=...)",
                        replacement="ClientSession(timeout=ClientTimeout(total=...))",
                        transform_name="read_timeout_to_client_timeout",
                    )
                    continue
                elif arg.keyword.value == "conn_timeout":
                    timeout_values["connect"] = arg.value
                    changed = True
                    self.record_change(
                        description="Convert conn_timeout to ClientTimeout(connect=...)",
                        line_number=1,
                        original="ClientSession(conn_timeout=...)",
                        replacement="ClientSession(timeout=ClientTimeout(connect=...))",
                        transform_name="conn_timeout_to_client_timeout",
                    )
                    continue
                elif arg.keyword.value == "timeout":
                    existing_timeout = arg
                    continue
            new_args.append(arg)

        if not changed:
            return None

        self._needs_client_timeout_import = True

        # Build ClientTimeout call
        if timeout_values:
            timeout_args = []
            for key, value in timeout_values.items():
                timeout_args.append(
                    cst.Arg(
                        keyword=cst.Name(key),
                        value=value,
                        equal=cst.AssignEqual(
                            whitespace_before=cst.SimpleWhitespace(""),
                            whitespace_after=cst.SimpleWhitespace(""),
                        ),
                    )
                )

            client_timeout_call = cst.Call(
                func=cst.Name("ClientTimeout"),
                args=timeout_args,
            )

            # Add the timeout argument
            new_args.append(
                cst.Arg(
                    keyword=cst.Name("timeout"),
                    value=client_timeout_call,
                    equal=cst.AssignEqual(
                        whitespace_before=cst.SimpleWhitespace(""),
                        whitespace_after=cst.SimpleWhitespace(""),
                    ),
                )
            )
        elif existing_timeout:
            new_args.append(existing_timeout)

        # Fix trailing comma
        if new_args:
            last_arg = new_args[-1]
            if last_arg.comma != cst.MaybeSentinel.DEFAULT:
                new_args[-1] = last_arg.with_changes(comma=cst.MaybeSentinel.DEFAULT)

        return node.with_changes(args=new_args)

    def _transform_basicauth_encode(self, node: cst.Call) -> cst.BaseExpression | None:
        """Transform BasicAuth(...).encode() to str(BasicAuth(...)).

        Handles:
        - BasicAuth(user, pass).encode() -> str(BasicAuth(user, pass))
        """
        # Check if this is a .encode() call
        if not isinstance(node.func, cst.Attribute):
            return None

        if node.func.attr.value != "encode":
            return None

        # Check if the base is a BasicAuth call
        base = node.func.value
        if not isinstance(base, cst.Call):
            return None

        base_func_name = self._get_call_name(base)
        if base_func_name != "BasicAuth" and not base_func_name.endswith(".BasicAuth"):
            return None

        # Check that encode() has no arguments (the old API)
        if node.args:
            return None

        self.record_change(
            description="Convert BasicAuth(...).encode() to str(BasicAuth(...))",
            line_number=1,
            original="BasicAuth(...).encode()",
            replacement="str(BasicAuth(...))",
            transform_name="basicauth_encode_to_str",
        )

        # Transform to str(BasicAuth(...))
        return cst.Call(
            func=cst.Name("str"),
            args=[cst.Arg(value=base)],
        )

    def _transform_ws_connect_timeout(self, node: cst.Call) -> cst.Call | None:
        """Transform ws_connect timeout parameter to receive_timeout.

        Handles:
        - session.ws_connect(url, timeout=X) -> session.ws_connect(url, receive_timeout=X)
        """
        func_name = self._get_call_name(node)

        if not (func_name == "ws_connect" or func_name.endswith(".ws_connect")):
            return None

        new_args = []
        changed = False

        for arg in node.args:
            if isinstance(arg.keyword, cst.Name) and arg.keyword.value == "timeout":
                # Rename timeout to receive_timeout
                new_arg = arg.with_changes(keyword=cst.Name("receive_timeout"))
                new_args.append(new_arg)
                changed = True
                self.record_change(
                    description="Rename ws_connect timeout parameter to receive_timeout",
                    line_number=1,
                    original="ws_connect(..., timeout=...)",
                    replacement="ws_connect(..., receive_timeout=...)",
                    transform_name="ws_connect_timeout_rename",
                )
            else:
                new_args.append(arg)

        if not changed:
            return None

        return node.with_changes(args=new_args)

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.BaseExpression:
        """Transform aiohttp attribute accesses."""
        attr_name = updated_node.attr.value

        # Handle url_obj -> url
        if attr_name == "url_obj":
            self.record_change(
                description="Rename url_obj attribute to url",
                line_number=1,
                original=".url_obj",
                replacement=".url",
                transform_name="url_obj_to_url",
            )
            return updated_node.with_changes(attr=cst.Name("url"))

        # Handle WebSocketResponse.protocol -> ws_protocol
        # This is tricky because we can't know the type, so we look for patterns
        # like ws.protocol or websocket.protocol or ws_response.protocol
        if attr_name == "protocol":
            # Check if this looks like it might be a WebSocket response
            value_name = self._get_expression_name(updated_node.value)
            ws_patterns = {"ws", "websocket", "ws_response", "websock", "socket"}
            if value_name and any(pattern in value_name.lower() for pattern in ws_patterns):
                self.record_change(
                    description="Rename WebSocketResponse.protocol to ws_protocol",
                    line_number=1,
                    original=".protocol",
                    replacement=".ws_protocol",
                    transform_name="ws_protocol_rename",
                )
                return updated_node.with_changes(attr=cst.Name("ws_protocol"))

        # Handle app.loop -> asyncio.get_event_loop()
        if attr_name == "loop":
            value_name = self._get_expression_name(updated_node.value)
            if value_name and value_name in {"app", "application", "request.app"}:
                self._needs_asyncio_import = True
                self.record_change(
                    description=f"Replace {value_name}.loop with asyncio.get_event_loop()",
                    line_number=1,
                    original=f"{value_name}.loop",
                    replacement="asyncio.get_event_loop()",
                    transform_name="app_loop_to_get_event_loop",
                )
                return cst.Call(
                    func=cst.Attribute(
                        value=cst.Name("asyncio"),
                        attr=cst.Name("get_event_loop"),
                    ),
                    args=[],
                )

        return updated_node

    def _get_call_name(self, node: cst.Call) -> str:
        """Get the name of a function/class being called."""
        if isinstance(node.func, cst.Name):
            return str(node.func.value)
        elif isinstance(node.func, cst.Attribute):
            return self._get_attribute_chain(node.func)
        return ""

    def _get_attribute_chain(self, node: cst.Attribute) -> str:
        """Get the full attribute chain as a string."""
        if isinstance(node.value, cst.Name):
            return f"{node.value.value}.{node.attr.value}"
        elif isinstance(node.value, cst.Attribute):
            return f"{self._get_attribute_chain(node.value)}.{node.attr.value}"
        return str(node.attr.value)

    def _get_expression_name(self, node: cst.BaseExpression) -> str | None:
        """Get a simple name representation of an expression."""
        if isinstance(node, cst.Name):
            return str(node.value)
        elif isinstance(node, cst.Attribute):
            base = self._get_expression_name(node.value)
            if base:
                return f"{base}.{node.attr.value}"
            return str(node.attr.value)
        return None

    def _get_module_name(self, module: cst.BaseExpression) -> str:
        """Get the full module name from a Name or Attribute node."""
        if isinstance(module, cst.Name):
            return str(module.value)
        elif isinstance(module, cst.Attribute):
            return f"{self._get_module_name(module.value)}.{module.attr.value}"
        return ""


class AiohttpImportTransformer(BaseTransformer):
    """Separate transformer for handling import additions.

    This runs after the main transformer to add any missing imports.
    """

    def __init__(
        self,
        needs_asyncio_import: bool = False,
        has_asyncio_import: bool = False,
        needs_client_timeout_import: bool = False,
        has_client_timeout_import: bool = False,
    ) -> None:
        super().__init__()
        self._needs_asyncio_import = needs_asyncio_import
        self._has_asyncio_import = has_asyncio_import
        self._needs_client_timeout_import = needs_client_timeout_import
        self._has_client_timeout_import = has_client_timeout_import
        self._found_aiohttp_import = False

    def visit_Import(self, node: cst.Import) -> bool:
        """Check for existing asyncio import."""
        if isinstance(node.names, cst.ImportStar):
            return True

        for name in node.names:
            if isinstance(name, cst.ImportAlias):
                if isinstance(name.name, cst.Name) and name.name.value == "asyncio":
                    self._has_asyncio_import = True

        return True

    def visit_ImportFrom(self, node: cst.ImportFrom) -> bool:
        """Check existing aiohttp imports."""
        if node.module is None:
            return True

        module_name = self._get_module_name(node.module)

        if module_name == "asyncio":
            self._has_asyncio_import = True

        if module_name == "aiohttp":
            self._found_aiohttp_import = True
            if not isinstance(node.names, cst.ImportStar):
                for name in node.names:
                    if isinstance(name, cst.ImportAlias):
                        if isinstance(name.name, cst.Name):
                            if name.name.value == "ClientTimeout":
                                self._has_client_timeout_import = True

        return True

    def leave_ImportFrom(
        self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
    ) -> cst.ImportFrom:
        """Add missing imports to aiohttp import statement."""
        if updated_node.module is None:
            return updated_node

        module_name = self._get_module_name(updated_node.module)

        if module_name != "aiohttp":
            return updated_node

        if isinstance(updated_node.names, cst.ImportStar):
            return updated_node

        new_names = list(updated_node.names)
        changed = False

        # Add ClientTimeout import if needed
        if self._needs_client_timeout_import and not self._has_client_timeout_import:
            new_names.append(cst.ImportAlias(name=cst.Name("ClientTimeout")))
            self._has_client_timeout_import = True
            changed = True

            self.record_change(
                description="Add 'ClientTimeout' import for timeout transformation",
                line_number=1,
                original="from aiohttp import ...",
                replacement="from aiohttp import ..., ClientTimeout",
                transform_name="add_client_timeout_import",
            )

        if changed:
            return updated_node.with_changes(names=new_names)

        return updated_node

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        """Add missing imports at module level."""
        new_body = list(updated_node.body)
        changed = False

        # Add asyncio import if needed
        if self._needs_asyncio_import and not self._has_asyncio_import:
            asyncio_import = cst.SimpleStatementLine(
                body=[cst.Import(names=[cst.ImportAlias(name=cst.Name("asyncio"))])]
            )
            # Insert after any __future__ imports
            insert_pos = 0
            for i, stmt in enumerate(new_body):
                if isinstance(stmt, cst.SimpleStatementLine):
                    for s in stmt.body:
                        if isinstance(s, cst.ImportFrom):
                            if s.module and self._get_module_name(s.module) == "__future__":
                                insert_pos = i + 1
                                break
                else:
                    break

            new_body.insert(insert_pos, asyncio_import)
            self._has_asyncio_import = True
            changed = True

            self.record_change(
                description="Add 'asyncio' import for get_event_loop()",
                line_number=1,
                original="",
                replacement="import asyncio",
                transform_name="add_asyncio_import",
            )

        # Add ClientTimeout import if needed and no aiohttp import exists
        if (
            self._needs_client_timeout_import
            and not self._has_client_timeout_import
            and not self._found_aiohttp_import
        ):
            client_timeout_import = cst.SimpleStatementLine(
                body=[
                    cst.ImportFrom(
                        module=cst.Name("aiohttp"),
                        names=[cst.ImportAlias(name=cst.Name("ClientTimeout"))],
                    )
                ]
            )
            # Insert after asyncio import if we just added it
            insert_pos = 1 if self._needs_asyncio_import else 0
            new_body.insert(insert_pos, client_timeout_import)
            changed = True

            self.record_change(
                description="Add 'ClientTimeout' import from aiohttp",
                line_number=1,
                original="",
                replacement="from aiohttp import ClientTimeout",
                transform_name="add_client_timeout_import",
            )

        if changed:
            return updated_node.with_changes(body=new_body)

        return updated_node

    def _get_module_name(self, module: cst.BaseExpression) -> str:
        """Get the full module name from an Attribute or Name node."""
        if isinstance(module, cst.Name):
            return str(module.value)
        elif isinstance(module, cst.Attribute):
            return f"{self._get_module_name(module.value)}.{module.attr.value}"
        return ""


def transform_aiohttp(source_code: str) -> tuple[str, list]:
    """Transform aiohttp code from 3.7 to 3.9+.

    Args:
        source_code: The source code to transform

    Returns:
        Tuple of (transformed_code, list of changes)
    """
    try:
        tree = cst.parse_module(source_code)
    except cst.ParserSyntaxError:
        return source_code, []

    transformer = AiohttpTransformer()
    transformer.set_source(source_code)

    try:
        transformed_tree = tree.visit(transformer)

        # Second pass: add missing imports
        import_transformer = AiohttpImportTransformer(
            needs_asyncio_import=transformer._needs_asyncio_import,
            has_asyncio_import=transformer._has_asyncio_import,
            needs_client_timeout_import=transformer._needs_client_timeout_import,
            has_client_timeout_import=transformer._has_client_timeout_import,
        )
        final_tree = transformed_tree.visit(import_transformer)

        all_changes = transformer.changes + import_transformer.changes
        return final_tree.code, all_changes
    except Exception:
        return source_code, []
