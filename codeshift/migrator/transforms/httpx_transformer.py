"""HTTPX library transformation using LibCST.

Handles migrations from httpx 0.x to 0.28+ including:
- Timeout parameter renames (connect_timeout -> connect, etc.)
- proxies parameter removal (use proxy or mounts)
- app parameter removal (use WSGITransport/ASGITransport)
"""

import libcst as cst

from codeshift.migrator.ast_transforms import BaseTransformer


class HTTPXTransformer(BaseTransformer):
    """Transform HTTPX library code for version upgrades."""

    # Timeout parameter mappings (old -> new)
    TIMEOUT_PARAM_MAPPINGS = {
        "connect_timeout": "connect",
        "read_timeout": "read",
        "write_timeout": "write",
        "pool_timeout": "pool",
    }

    def __init__(self) -> None:
        super().__init__()
        self._needs_wsgi_transport_import = False
        self._needs_asgi_transport_import = False
        self._needs_http_transport_import = False
        self._has_httpx_import = False

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.BaseExpression:
        """Transform HTTPX function calls."""
        # Handle httpx.Timeout() calls
        if self._is_timeout_call(updated_node):
            return self._transform_timeout_call(updated_node)

        # Handle httpx.Client() and httpx.AsyncClient() calls
        if self._is_client_call(updated_node):
            return self._transform_client_call(updated_node)

        return updated_node

    def _is_timeout_call(self, node: cst.Call) -> bool:
        """Check if this is a Timeout() call."""
        # Match httpx.Timeout(...) or Timeout(...)
        if isinstance(node.func, cst.Attribute):
            if (
                isinstance(node.func.value, cst.Name)
                and node.func.value.value == "httpx"
                and node.func.attr.value == "Timeout"
            ):
                return True
        elif isinstance(node.func, cst.Name):
            if node.func.value == "Timeout":
                return True
        return False

    def _is_client_call(self, node: cst.Call) -> bool:
        """Check if this is a Client() or AsyncClient() call."""
        client_names = {"Client", "AsyncClient"}

        if isinstance(node.func, cst.Attribute):
            if (
                isinstance(node.func.value, cst.Name)
                and node.func.value.value == "httpx"
                and node.func.attr.value in client_names
            ):
                return True
        elif isinstance(node.func, cst.Name):
            if node.func.value in client_names:
                return True
        return False

    def _get_client_type(self, node: cst.Call) -> str | None:
        """Get the client type (Client or AsyncClient)."""
        if isinstance(node.func, cst.Attribute):
            return str(node.func.attr.value)
        elif isinstance(node.func, cst.Name):
            return str(node.func.value)
        return None

    def _transform_timeout_call(self, node: cst.Call) -> cst.Call:
        """Transform Timeout() call to use new parameter names."""
        new_args: list[cst.Arg] = []
        changed = False

        for arg in node.args:
            if isinstance(arg.keyword, cst.Name):
                keyword_name = arg.keyword.value

                # Handle 'timeout' keyword -> positional argument
                if keyword_name == "timeout":
                    # Convert timeout=X to just X as first positional argument
                    new_arg = cst.Arg(value=arg.value)
                    new_args.insert(0, new_arg)
                    changed = True
                    self.record_change(
                        description="Convert Timeout(timeout=...) to Timeout(...)",
                        line_number=1,
                        original="Timeout(timeout=...)",
                        replacement="Timeout(...)",
                        transform_name="timeout_keyword_to_positional",
                    )
                    continue

                # Handle *_timeout -> shorter names
                if keyword_name in self.TIMEOUT_PARAM_MAPPINGS:
                    new_keyword = self.TIMEOUT_PARAM_MAPPINGS[keyword_name]
                    new_arg = arg.with_changes(keyword=cst.Name(new_keyword))
                    new_args.append(new_arg)
                    changed = True
                    self.record_change(
                        description=f"Rename Timeout({keyword_name}=...) to Timeout({new_keyword}=...)",
                        line_number=1,
                        original=f"Timeout({keyword_name}=...)",
                        replacement=f"Timeout({new_keyword}=...)",
                        transform_name=f"timeout_{keyword_name}_to_{new_keyword}",
                    )
                    continue

            new_args.append(arg)

        if changed:
            return node.with_changes(args=new_args)
        return node

    def _transform_client_call(self, node: cst.Call) -> cst.Call:
        """Transform Client() or AsyncClient() calls."""
        client_type = self._get_client_type(node)
        new_args = []
        changed = False

        for arg in node.args:
            if isinstance(arg.keyword, cst.Name):
                keyword_name = arg.keyword.value

                # Handle proxies parameter -> proxy (for simple single-value cases)
                if keyword_name == "proxies":
                    transformed_arg = self._transform_proxies_arg(arg, client_type)
                    if transformed_arg is not None:
                        new_args.append(transformed_arg)
                        changed = True
                        continue
                    # If transform returned None, we'll skip this arg (it was recorded as needing manual fix)

                # Handle app parameter -> transport
                if keyword_name == "app":
                    transformed_arg = self._transform_app_arg(arg, client_type)
                    new_args.append(transformed_arg)
                    changed = True
                    continue

            new_args.append(arg)

        if changed:
            return node.with_changes(args=new_args)
        return node

    def _transform_proxies_arg(self, arg: cst.Arg, client_type: str | None) -> cst.Arg | None:
        """Transform proxies=... argument.

        For simple string values, convert to proxy=...
        For dict values, this is more complex and may need mounts.
        """
        # Check if it's a simple string value
        if isinstance(arg.value, cst.SimpleString):
            # Simple case: proxies="http://..." -> proxy="http://..."
            new_arg = arg.with_changes(keyword=cst.Name("proxy"))
            self.record_change(
                description=f"Convert {client_type or 'Client'}(proxies=...) to {client_type or 'Client'}(proxy=...)",
                line_number=1,
                original=f"{client_type or 'Client'}(proxies=...)",
                replacement=f"{client_type or 'Client'}(proxy=...)",
                transform_name="client_proxies_to_proxy",
            )
            return new_arg

        # Check if it's a variable reference (Name)
        if isinstance(arg.value, cst.Name):
            # Variable reference - convert to proxy but note it may need review
            new_arg = arg.with_changes(keyword=cst.Name("proxy"))
            self.record_change(
                description=f"Convert {client_type or 'Client'}(proxies=...) to {client_type or 'Client'}(proxy=...)",
                line_number=1,
                original=f"{client_type or 'Client'}(proxies=...)",
                replacement=f"{client_type or 'Client'}(proxy=...)",
                transform_name="client_proxies_to_proxy",
                confidence=0.8,
                notes="If proxies was a dict, may need to use mounts with HTTPTransport instead",
            )
            return new_arg

        # For dict values, record that manual migration is needed
        if isinstance(arg.value, cst.Dict):
            self.record_change(
                description=f"Manual migration needed: {client_type or 'Client'}(proxies={{...}}) requires mounts with HTTPTransport",
                line_number=1,
                original=f"{client_type or 'Client'}(proxies={{...}})",
                replacement=f"{client_type or 'Client'}(mounts={{...}})",
                transform_name="client_proxies_dict_to_mounts",
                confidence=0.5,
                notes="Dict-based proxies must be converted to mounts with HTTPTransport. Example: mounts={'http://': httpx.HTTPTransport(proxy='...')}",
            )
            # Return the original arg - we can't auto-transform dicts safely
            return arg

        # For other cases, convert to proxy and note uncertainty
        new_arg = arg.with_changes(keyword=cst.Name("proxy"))
        self.record_change(
            description=f"Convert {client_type or 'Client'}(proxies=...) to {client_type or 'Client'}(proxy=...)",
            line_number=1,
            original=f"{client_type or 'Client'}(proxies=...)",
            replacement=f"{client_type or 'Client'}(proxy=...)",
            transform_name="client_proxies_to_proxy",
            confidence=0.7,
            notes="Review this change - if original value was a dict, use mounts instead",
        )
        return new_arg

    def _transform_app_arg(self, arg: cst.Arg, client_type: str | None) -> cst.Arg:
        """Transform app=... argument to transport=WSGITransport/ASGITransport(app=...)."""
        is_async = client_type == "AsyncClient"
        transport_name = "ASGITransport" if is_async else "WSGITransport"

        if is_async:
            self._needs_asgi_transport_import = True
        else:
            self._needs_wsgi_transport_import = True

        # Create the transport call: httpx.WSGITransport(app=...) or httpx.ASGITransport(app=...)
        transport_call = cst.Call(
            func=cst.Attribute(
                value=cst.Name("httpx"),
                attr=cst.Name(transport_name),
            ),
            args=[
                cst.Arg(
                    keyword=cst.Name("app"),
                    value=arg.value,
                    equal=cst.AssignEqual(
                        whitespace_before=cst.SimpleWhitespace(""),
                        whitespace_after=cst.SimpleWhitespace(""),
                    ),
                )
            ],
        )

        # Create transport=... argument
        new_arg = cst.Arg(
            keyword=cst.Name("transport"),
            value=transport_call,
            equal=cst.AssignEqual(
                whitespace_before=cst.SimpleWhitespace(""),
                whitespace_after=cst.SimpleWhitespace(""),
            ),
        )

        self.record_change(
            description=f"Convert {client_type or 'Client'}(app=...) to {client_type or 'Client'}(transport=httpx.{transport_name}(app=...))",
            line_number=1,
            original=f"{client_type or 'Client'}(app=...)",
            replacement=f"{client_type or 'Client'}(transport=httpx.{transport_name}(app=...))",
            transform_name=f"{'async_' if is_async else ''}client_app_to_{'asgi' if is_async else 'wsgi'}_transport",
        )

        return new_arg

    def visit_ImportFrom(self, node: cst.ImportFrom) -> bool:
        """Track httpx imports."""
        if node.module is not None:
            module_name = self._get_module_name(node.module)
            if module_name == "httpx":
                self._has_httpx_import = True
        return True

    def visit_Import(self, node: cst.Import) -> bool:
        """Track httpx imports."""
        if isinstance(node.names, cst.ImportStar):
            return True
        for name in node.names:
            if isinstance(name, cst.ImportAlias):
                if isinstance(name.name, cst.Name) and name.name.value == "httpx":
                    self._has_httpx_import = True
        return True

    def _get_module_name(self, module: cst.BaseExpression) -> str:
        """Get the full module name from a Name or Attribute node."""
        if isinstance(module, cst.Name):
            return str(module.value)
        elif isinstance(module, cst.Attribute):
            return f"{self._get_module_name(module.value)}.{module.attr.value}"
        return ""


class HTTPXImportTransformer(BaseTransformer):
    """Handle import updates for HTTPX transformations."""

    def __init__(
        self,
        needs_wsgi_transport: bool = False,
        needs_asgi_transport: bool = False,
        needs_http_transport: bool = False,
    ) -> None:
        super().__init__()
        self.needs_wsgi_transport = needs_wsgi_transport
        self.needs_asgi_transport = needs_asgi_transport
        self.needs_http_transport = needs_http_transport
        self._has_wsgi_transport = False
        self._has_asgi_transport = False
        self._has_http_transport = False

    def visit_ImportFrom(self, node: cst.ImportFrom) -> bool:
        """Check existing httpx imports."""
        if node.module is None:
            return True

        module_name = self._get_module_name(node.module)
        if module_name == "httpx":
            if not isinstance(node.names, cst.ImportStar):
                for name in node.names:
                    if isinstance(name, cst.ImportAlias):
                        imported = self._get_name_value(name.name)
                        if imported == "WSGITransport":
                            self._has_wsgi_transport = True
                        elif imported == "ASGITransport":
                            self._has_asgi_transport = True
                        elif imported == "HTTPTransport":
                            self._has_http_transport = True
        return True

    def leave_ImportFrom(
        self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
    ) -> cst.ImportFrom:
        """Add missing transport imports to httpx import statement."""
        if updated_node.module is None:
            return updated_node

        module_name = self._get_module_name(updated_node.module)
        if module_name != "httpx":
            return updated_node

        if isinstance(updated_node.names, cst.ImportStar):
            return updated_node

        new_names = list(updated_node.names)
        changed = False

        if self.needs_wsgi_transport and not self._has_wsgi_transport:
            new_names.append(cst.ImportAlias(name=cst.Name("WSGITransport")))
            self._has_wsgi_transport = True
            changed = True

        if self.needs_asgi_transport and not self._has_asgi_transport:
            new_names.append(cst.ImportAlias(name=cst.Name("ASGITransport")))
            self._has_asgi_transport = True
            changed = True

        if self.needs_http_transport and not self._has_http_transport:
            new_names.append(cst.ImportAlias(name=cst.Name("HTTPTransport")))
            self._has_http_transport = True
            changed = True

        if changed:
            return updated_node.with_changes(names=new_names)
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


def transform_httpx(source_code: str) -> tuple[str, list]:
    """Transform HTTPX library code.

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
    transformer = HTTPXTransformer()
    transformer.set_source(source_code)

    try:
        transformed_tree = tree.visit(transformer)

        # Second pass: add missing imports if needed
        if (
            transformer._needs_wsgi_transport_import
            or transformer._needs_asgi_transport_import
            or transformer._needs_http_transport_import
        ):
            import_transformer = HTTPXImportTransformer(
                needs_wsgi_transport=transformer._needs_wsgi_transport_import,
                needs_asgi_transport=transformer._needs_asgi_transport_import,
                needs_http_transport=transformer._needs_http_transport_import,
            )
            transformed_tree = transformed_tree.visit(import_transformer)

        return transformed_tree.code, transformer.changes
    except Exception:
        return source_code, []
