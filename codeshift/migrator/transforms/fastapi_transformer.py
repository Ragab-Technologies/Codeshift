"""FastAPI transformation using LibCST."""

import libcst as cst

from codeshift.migrator.ast_transforms import BaseTransformer


class FastAPITransformer(BaseTransformer):
    """Transform FastAPI code for version upgrades (0.99 to 0.100+)."""

    def __init__(self) -> None:
        super().__init__()
        self._in_fastapi_context = False

    def leave_ImportFrom(
        self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
    ) -> cst.ImportFrom:
        """Transform starlette imports to fastapi imports."""
        if original_node.module is None:
            return updated_node

        module_name = self._get_module_name(original_node.module)

        # Transform starlette.responses imports
        if module_name == "starlette.responses":
            self.record_change(
                description="Import from fastapi.responses instead of starlette.responses",
                line_number=1,
                original=f"from {module_name}",
                replacement="from fastapi.responses",
                transform_name="starlette_to_fastapi_responses",
            )
            return updated_node.with_changes(
                module=cst.Attribute(
                    value=cst.Name("fastapi"),
                    attr=cst.Name("responses"),
                )
            )

        # Transform starlette.requests imports
        if module_name == "starlette.requests":
            self.record_change(
                description="Import Request from fastapi instead of starlette.requests",
                line_number=1,
                original=f"from {module_name}",
                replacement="from fastapi",
                transform_name="starlette_to_fastapi_request",
            )
            return updated_node.with_changes(module=cst.Name("fastapi"))

        # Transform starlette.websockets imports
        if module_name == "starlette.websockets":
            self.record_change(
                description="Import WebSocket from fastapi instead of starlette.websockets",
                line_number=1,
                original=f"from {module_name}",
                replacement="from fastapi",
                transform_name="starlette_to_fastapi_websocket",
            )
            return updated_node.with_changes(module=cst.Name("fastapi"))

        # Transform starlette.status imports
        if module_name == "starlette.status":
            self.record_change(
                description="Import status from fastapi instead of starlette",
                line_number=1,
                original=f"from {module_name}",
                replacement="from fastapi import status",
                transform_name="starlette_to_fastapi_status",
            )
            return updated_node.with_changes(module=cst.Name("fastapi"))

        return updated_node

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        """Transform FastAPI function calls."""
        # Handle Field, Query, Path, Body regex -> pattern
        if isinstance(updated_node.func, cst.Name):
            func_name = updated_node.func.value
            if func_name in ("Field", "Query", "Path", "Body"):
                new_args = []
                changed = False
                for arg in updated_node.args:
                    if isinstance(arg.keyword, cst.Name) and arg.keyword.value == "regex":
                        new_args.append(arg.with_changes(keyword=cst.Name("pattern")))
                        changed = True
                        self.record_change(
                            description=f"Rename {func_name}(regex=...) to {func_name}(pattern=...)",
                            line_number=1,
                            original=f"{func_name}(regex=...)",
                            replacement=f"{func_name}(pattern=...)",
                            transform_name=f"{func_name.lower()}_regex_to_pattern",
                        )
                    else:
                        new_args.append(arg)

                if changed:
                    return updated_node.with_changes(args=new_args)

        # Handle Depends(use_cache=...) -> Depends(use_cached=...)
        if isinstance(updated_node.func, cst.Name) and updated_node.func.value == "Depends":
            new_args = []
            changed = False
            for arg in updated_node.args:
                if isinstance(arg.keyword, cst.Name) and arg.keyword.value == "use_cache":
                    new_args.append(arg.with_changes(keyword=cst.Name("use_cached")))
                    changed = True
                    self.record_change(
                        description="Rename Depends(use_cache=...) to Depends(use_cached=...)",
                        line_number=1,
                        original="Depends(use_cache=...)",
                        replacement="Depends(use_cached=...)",
                        transform_name="depends_use_cache_rename",
                    )
                else:
                    new_args.append(arg)

            if changed:
                return updated_node.with_changes(args=new_args)

        # Handle FastAPI(openapi_prefix=...) -> FastAPI(root_path=...)
        if isinstance(updated_node.func, cst.Name) and updated_node.func.value == "FastAPI":
            new_args = []
            changed = False
            for arg in updated_node.args:
                if isinstance(arg.keyword, cst.Name) and arg.keyword.value == "openapi_prefix":
                    new_args.append(arg.with_changes(keyword=cst.Name("root_path")))
                    changed = True
                    self.record_change(
                        description="Rename openapi_prefix to root_path",
                        line_number=1,
                        original="FastAPI(openapi_prefix=...)",
                        replacement="FastAPI(root_path=...)",
                        transform_name="openapi_prefix_to_root_path",
                    )
                else:
                    new_args.append(arg)

            if changed:
                return updated_node.with_changes(args=new_args)

        return updated_node

    def _get_module_name(self, module: cst.BaseExpression) -> str:
        """Get the full module name from a Name or Attribute node."""
        if isinstance(module, cst.Name):
            return str(module.value)
        elif isinstance(module, cst.Attribute):
            return f"{self._get_module_name(module.value)}.{module.attr.value}"
        return ""


def transform_fastapi(source_code: str) -> tuple[str, list]:
    """Transform FastAPI code.

    Args:
        source_code: The source code to transform

    Returns:
        Tuple of (transformed_code, list of changes)
    """
    try:
        tree = cst.parse_module(source_code)
    except cst.ParserSyntaxError:
        return source_code, []

    transformer = FastAPITransformer()
    transformer.set_source(source_code)

    try:
        transformed_tree = tree.visit(transformer)
        return transformed_tree.code, transformer.changes
    except Exception:
        return source_code, []
