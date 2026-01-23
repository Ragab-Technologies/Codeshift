"""Requests library transformation using LibCST."""

from typing import Union

import libcst as cst

from pyresolve.migrator.ast_transforms import BaseTransformer


class RequestsTransformer(BaseTransformer):
    """Transform Requests library code for version upgrades."""

    def __init__(self) -> None:
        super().__init__()

    def leave_ImportFrom(
        self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
    ) -> cst.ImportFrom:
        """Transform requests imports."""
        if original_node.module is None:
            return updated_node

        module_name = self._get_module_name(original_node.module)

        # Transform requests.packages.urllib3 imports
        if module_name == "requests.packages.urllib3" or module_name.startswith(
            "requests.packages.urllib3."
        ):
            new_module_name = module_name.replace("requests.packages.urllib3", "urllib3")
            self.record_change(
                description="Import urllib3 directly instead of through requests.packages",
                line_number=1,
                original=f"from {module_name}",
                replacement=f"from {new_module_name}",
                transform_name="urllib3_import_fix",
            )
            return updated_node.with_changes(module=self._build_module_node(new_module_name))

        # Transform requests.compat imports
        if module_name == "requests.compat":
            if isinstance(updated_node.names, cst.ImportStar):
                return updated_node

            for name in updated_node.names:
                if isinstance(name, cst.ImportAlias) and isinstance(name.name, cst.Name):
                    import_name = name.name.value
                    if import_name in (
                        "urljoin",
                        "urlparse",
                        "urlsplit",
                        "urlunparse",
                        "urlencode",
                        "quote",
                        "unquote",
                    ):
                        self.record_change(
                            description=f"Import {import_name} from urllib.parse instead of requests.compat",
                            line_number=1,
                            original=f"from requests.compat import {import_name}",
                            replacement=f"from urllib.parse import {import_name}",
                            transform_name=f"compat_{import_name}_fix",
                        )
                        return updated_node.with_changes(
                            module=cst.Attribute(
                                value=cst.Name("urllib"),
                                attr=cst.Name("parse"),
                            )
                        )

        return updated_node

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> Union[cst.Attribute, cst.Name]:
        """Transform requests.packages.urllib3 attribute access."""
        # Check for requests.packages.urllib3 pattern
        attr_str = self._get_full_attribute(updated_node)

        if attr_str.startswith("requests.packages.urllib3"):
            new_attr_str = attr_str.replace("requests.packages.urllib3", "urllib3")
            self.record_change(
                description="Access urllib3 directly instead of through requests.packages",
                line_number=1,
                original=attr_str,
                replacement=new_attr_str,
                transform_name="urllib3_attribute_fix",
            )
            return self._build_name_or_attribute_node(new_attr_str)

        return updated_node

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        """Transform requests function calls."""
        # Check for requests.get/post/put/delete without timeout
        if isinstance(updated_node.func, cst.Attribute):
            if (
                isinstance(updated_node.func.value, cst.Name)
                and updated_node.func.value.value == "requests"
            ):
                method_name = updated_node.func.attr.value
                if method_name in ("get", "post", "put", "delete", "patch", "head", "options"):
                    # Check if timeout is specified
                    has_timeout = any(
                        isinstance(arg.keyword, cst.Name) and arg.keyword.value == "timeout"
                        for arg in updated_node.args
                    )
                    if not has_timeout:
                        self.record_change(
                            description=f"requests.{method_name}() called without explicit timeout",
                            line_number=1,
                            original=f"requests.{method_name}(...)",
                            replacement=f"requests.{method_name}(..., timeout=30)",
                            transform_name=f"{method_name}_add_explicit_timeout",
                            confidence=0.7,
                            notes="Consider adding explicit timeout parameter",
                        )

        # Check for session method calls without timeout
        if isinstance(updated_node.func, cst.Attribute):
            method_name = updated_node.func.attr.value
            if method_name in (
                "get",
                "post",
                "put",
                "delete",
                "patch",
                "head",
                "options",
                "request",
            ):
                # Check if this might be a session call (heuristic)
                has_timeout = any(
                    isinstance(arg.keyword, cst.Name) and arg.keyword.value == "timeout"
                    for arg in updated_node.args
                )
                if not has_timeout and isinstance(updated_node.func.value, cst.Name):
                    value_name = updated_node.func.value.value.lower()
                    if "session" in value_name or value_name in ("s", "sess", "client"):
                        self.record_change(
                            description=f"Session.{method_name}() called without explicit timeout",
                            line_number=1,
                            original=f"session.{method_name}(...)",
                            replacement=f"session.{method_name}(..., timeout=30)",
                            transform_name=f"session_{method_name}_add_timeout",
                            confidence=0.6,
                            notes="Consider adding explicit timeout parameter",
                        )

        return updated_node

    def _get_module_name(self, module: cst.BaseExpression) -> str:
        """Get the full module name from a Name or Attribute node."""
        if isinstance(module, cst.Name):
            return str(module.value)
        elif isinstance(module, cst.Attribute):
            return f"{self._get_module_name(module.value)}.{module.attr.value}"
        return ""

    def _build_module_node(self, module_name: str) -> Union[cst.Name, cst.Attribute]:
        """Build a module node from a dotted name string."""
        parts = module_name.split(".")
        if len(parts) == 1:
            return cst.Name(parts[0])

        result: Union[cst.Name, cst.Attribute] = cst.Name(parts[0])
        for part in parts[1:]:
            result = cst.Attribute(value=result, attr=cst.Name(part))
        return result

    def _get_full_attribute(self, node: cst.Attribute) -> str:
        """Get the full attribute path as a string."""
        if isinstance(node.value, cst.Name):
            return f"{node.value.value}.{node.attr.value}"
        elif isinstance(node.value, cst.Attribute):
            return f"{self._get_full_attribute(node.value)}.{node.attr.value}"
        return str(node.attr.value)

    def _build_attribute_node(self, attr_str: str) -> cst.Attribute:
        """Build an attribute node from a dotted string."""
        parts = attr_str.split(".")
        result: Union[cst.Name, cst.Attribute] = cst.Name(parts[0])
        for part in parts[1:]:
            result = cst.Attribute(value=result, attr=cst.Name(part))
        # Safe to cast since we always have at least 2 parts for an Attribute
        assert isinstance(result, cst.Attribute)
        return result

    def _build_name_or_attribute_node(self, name_str: str) -> Union[cst.Name, cst.Attribute]:
        """Build a Name or Attribute node from a dotted string."""
        parts = name_str.split(".")
        if len(parts) == 1:
            return cst.Name(parts[0])
        result: Union[cst.Name, cst.Attribute] = cst.Name(parts[0])
        for part in parts[1:]:
            result = cst.Attribute(value=result, attr=cst.Name(part))
        return result


def transform_requests(source_code: str) -> tuple[str, list]:
    """Transform Requests library code.

    Args:
        source_code: The source code to transform

    Returns:
        Tuple of (transformed_code, list of changes)
    """
    try:
        tree = cst.parse_module(source_code)
    except cst.ParserSyntaxError:
        return source_code, []

    transformer = RequestsTransformer()
    transformer.set_source(source_code)

    try:
        transformed_tree = tree.visit(transformer)
        return transformed_tree.code, transformer.changes
    except Exception:
        return source_code, []
