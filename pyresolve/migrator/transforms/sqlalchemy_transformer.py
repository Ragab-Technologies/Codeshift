"""SQLAlchemy 1.x to 2.0 transformation using LibCST."""

from typing import Union

import libcst as cst

from pyresolve.migrator.ast_transforms import BaseTransformer


class SQLAlchemyTransformer(BaseTransformer):
    """Transform SQLAlchemy 1.x code to 2.0."""

    def __init__(self) -> None:
        super().__init__()
        self._needs_select_import = False
        self._needs_text_import = False
        self._has_declarative_base_import = False

    def leave_ImportFrom(
        self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
    ) -> Union[cst.ImportFrom, cst.RemovalSentinel]:
        """Transform SQLAlchemy imports."""
        if original_node.module is None:
            return updated_node

        module_name = self._get_module_name(original_node.module)

        # Transform declarative_base import
        if module_name == "sqlalchemy.ext.declarative":
            if isinstance(updated_node.names, cst.ImportStar):
                return updated_node

            new_names = []
            changed = False

            for name in updated_node.names:
                if isinstance(name, cst.ImportAlias):
                    if isinstance(name.name, cst.Name) and name.name.value == "declarative_base":
                        # Change to DeclarativeBase from sqlalchemy.orm
                        self.record_change(
                            description="Import DeclarativeBase from sqlalchemy.orm instead of declarative_base",
                            line_number=1,
                            original="from sqlalchemy.ext.declarative import declarative_base",
                            replacement="from sqlalchemy.orm import DeclarativeBase",
                            transform_name="import_declarative_base",
                        )
                        self._has_declarative_base_import = True
                        # Return updated import from sqlalchemy.orm
                        return updated_node.with_changes(
                            module=cst.Attribute(
                                value=cst.Name("sqlalchemy"),
                                attr=cst.Name("orm"),
                            ),
                            names=[cst.ImportAlias(name=cst.Name("DeclarativeBase"))],
                        )
                    else:
                        new_names.append(name)
                else:
                    new_names.append(name)

            if changed and new_names:
                return updated_node.with_changes(names=new_names)

        # Handle backref import removal
        if module_name == "sqlalchemy.orm":
            if isinstance(updated_node.names, cst.ImportStar):
                return updated_node

            new_names = []
            changed = False

            for name in updated_node.names:
                if isinstance(name, cst.ImportAlias):
                    if isinstance(name.name, cst.Name) and name.name.value == "backref":
                        self.record_change(
                            description="Remove backref import (use back_populates instead)",
                            line_number=1,
                            original="backref",
                            replacement="# backref removed, use back_populates",
                            transform_name="remove_backref_import",
                        )
                        changed = True
                        continue
                    new_names.append(name)
                else:
                    new_names.append(name)

            if changed:
                if new_names:
                    return updated_node.with_changes(names=new_names)
                # If no names left, remove the import
                return cst.RemovalSentinel.REMOVE

        return updated_node

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        """Transform SQLAlchemy function calls."""
        # Handle declarative_base() -> class Base(DeclarativeBase): pass
        # This is complex - we just record the need for change
        if isinstance(updated_node.func, cst.Name):
            func_name = updated_node.func.value

            if func_name == "declarative_base":
                self.record_change(
                    description="Replace declarative_base() with class Base(DeclarativeBase): pass",
                    line_number=1,
                    original="Base = declarative_base()",
                    replacement="class Base(DeclarativeBase): pass",
                    transform_name="declarative_base_to_class",
                    confidence=0.8,
                    notes="Manual review recommended - create class inheriting from DeclarativeBase",
                )

        # Handle create_engine future flag
        if isinstance(updated_node.func, cst.Name) and updated_node.func.value == "create_engine":
            new_args = []
            changed = False
            for arg in updated_node.args:
                if isinstance(arg.keyword, cst.Name) and arg.keyword.value == "future":
                    # Remove future=True as it's now default
                    changed = True
                    self.record_change(
                        description="Remove future=True from create_engine (now default)",
                        line_number=1,
                        original="create_engine(..., future=True)",
                        replacement="create_engine(...)",
                        transform_name="remove_future_flag",
                    )
                    continue
                new_args.append(arg)

            if changed:
                return updated_node.with_changes(args=new_args)

        return updated_node

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.Attribute:
        """Transform SQLAlchemy attribute accesses."""
        # Handle method renames: .all() when preceded by query-like calls
        # This is simplified - would need more context for accurate detection
        # Note: attr_name = updated_node.attr.value would be used for future transforms

        return updated_node

    def _get_module_name(self, module: cst.BaseExpression) -> str:
        """Get the full module name from a Name or Attribute node."""
        if isinstance(module, cst.Name):
            return str(module.value)
        elif isinstance(module, cst.Attribute):
            return f"{self._get_module_name(module.value)}.{module.attr.value}"
        return ""


def transform_sqlalchemy(source_code: str) -> tuple[str, list]:
    """Transform SQLAlchemy code from 1.x to 2.0.

    Args:
        source_code: The source code to transform

    Returns:
        Tuple of (transformed_code, list of changes)
    """
    try:
        tree = cst.parse_module(source_code)
    except cst.ParserSyntaxError:
        return source_code, []

    transformer = SQLAlchemyTransformer()
    transformer.set_source(source_code)

    try:
        transformed_tree = tree.visit(transformer)
        return transformed_tree.code, transformer.changes
    except Exception:
        return source_code, []
