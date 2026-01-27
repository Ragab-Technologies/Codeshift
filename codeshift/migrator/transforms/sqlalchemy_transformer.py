"""SQLAlchemy 1.x to 2.0 transformation using LibCST."""

from collections.abc import Sequence

import libcst as cst

from codeshift.migrator.ast_transforms import BaseTransformer


class _FilterByArg:
    """Marker class to represent a filter_by argument that needs model reference."""

    def __init__(self, key: str, value: cst.BaseExpression) -> None:
        self.key = key
        self.value = value


class SQLAlchemyTransformer(BaseTransformer):
    """Transform SQLAlchemy 1.x code to 2.0."""

    def __init__(self) -> None:
        super().__init__()
        self._needs_select_import = False
        self._needs_func_import = False
        self._needs_text_import = False
        self._has_declarative_base_import = False
        self._has_text_import = False
        # Track declarative_base variable name for transformation
        self._declarative_base_var_name: str | None = None
        # Track engine variable names from create_engine() calls
        self._engine_var_names: set[str] = set()

    def visit_ImportFrom(self, node: cst.ImportFrom) -> bool:
        """Track existing imports."""
        if node.module is None:
            return True

        module_name = self._get_module_name(node.module)

        # Track if text is already imported from sqlalchemy
        if module_name == "sqlalchemy":
            if not isinstance(node.names, cst.ImportStar):
                for name in node.names:
                    if isinstance(name, cst.ImportAlias):
                        if isinstance(name.name, cst.Name) and name.name.value == "text":
                            self._has_text_import = True

        return True

    def leave_ImportFrom(
        self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
    ) -> cst.ImportFrom | cst.RemovalSentinel:
        """Transform SQLAlchemy imports."""
        if original_node.module is None:
            return updated_node

        module_name = self._get_module_name(original_node.module)

        # Transform declarative_base import from sqlalchemy.ext.declarative
        if module_name == "sqlalchemy.ext.declarative":
            if isinstance(updated_node.names, cst.ImportStar):
                return updated_node

            new_names = []
            found_declarative_base = False

            for name in updated_node.names:
                if isinstance(name, cst.ImportAlias):
                    if isinstance(name.name, cst.Name) and name.name.value == "declarative_base":
                        found_declarative_base = True
                        self.record_change(
                            description="Import DeclarativeBase from sqlalchemy.orm instead of declarative_base",
                            line_number=1,
                            original="from sqlalchemy.ext.declarative import declarative_base",
                            replacement="from sqlalchemy.orm import DeclarativeBase",
                            transform_name="import_declarative_base",
                        )
                        self._has_declarative_base_import = True
                    else:
                        new_names.append(name)
                else:
                    new_names.append(name)

            if found_declarative_base:
                # Add DeclarativeBase to the list
                new_names.insert(0, cst.ImportAlias(name=cst.Name("DeclarativeBase")))
                # Change module to sqlalchemy.orm
                return updated_node.with_changes(
                    module=cst.Attribute(
                        value=cst.Name("sqlalchemy"),
                        attr=cst.Name("orm"),
                    ),
                    names=new_names,
                )

        # Handle declarative_base import from sqlalchemy.orm and backref removal
        if module_name == "sqlalchemy.orm":
            if isinstance(updated_node.names, cst.ImportStar):
                return updated_node

            new_names = []
            found_declarative_base = False
            found_backref = False

            for name in updated_node.names:
                if isinstance(name, cst.ImportAlias):
                    name_value = name.name.value if isinstance(name.name, cst.Name) else None

                    if name_value == "declarative_base":
                        found_declarative_base = True
                        self.record_change(
                            description="Replace declarative_base import with DeclarativeBase",
                            line_number=1,
                            original="from sqlalchemy.orm import declarative_base",
                            replacement="from sqlalchemy.orm import DeclarativeBase",
                            transform_name="import_declarative_base",
                        )
                        self._has_declarative_base_import = True
                    elif name_value == "backref":
                        found_backref = True
                        self.record_change(
                            description="Remove backref import (use back_populates instead)",
                            line_number=1,
                            original="backref",
                            replacement="# backref removed, use back_populates",
                            transform_name="remove_backref_import",
                        )
                    else:
                        new_names.append(name)
                else:
                    new_names.append(name)

            if found_declarative_base or found_backref:
                # Add DeclarativeBase if we found declarative_base
                if found_declarative_base:
                    new_names.insert(0, cst.ImportAlias(name=cst.Name("DeclarativeBase")))

                if new_names:
                    # Fix trailing comma: ensure last item has no trailing comma
                    if new_names:
                        last_item = new_names[-1]
                        if (
                            hasattr(last_item, "comma")
                            and last_item.comma != cst.MaybeSentinel.DEFAULT
                        ):
                            new_names[-1] = last_item.with_changes(comma=cst.MaybeSentinel.DEFAULT)
                    return updated_node.with_changes(names=new_names)
                else:
                    # No imports left, remove the line
                    return cst.RemovalSentinel.REMOVE

        return updated_node

    def visit_Assign(self, node: cst.Assign) -> bool:
        """Track engine variable names from create_engine() calls."""
        if len(node.targets) == 1:
            target = node.targets[0].target
            if isinstance(target, cst.Name) and isinstance(node.value, cst.Call):
                call = node.value
                # Check if this is a create_engine() call
                if isinstance(call.func, cst.Name) and call.func.value == "create_engine":
                    self._engine_var_names.add(target.value)
        return True

    def leave_SimpleStatementLine(
        self,
        original_node: cst.SimpleStatementLine,
        updated_node: cst.SimpleStatementLine,
    ) -> cst.SimpleStatementLine | cst.ClassDef | cst.RemovalSentinel:
        """Transform assignment statements like Base = declarative_base()."""
        # Check if this is an assignment with declarative_base() call
        if len(updated_node.body) == 1:
            stmt = updated_node.body[0]
            if isinstance(stmt, cst.Assign) and len(stmt.targets) == 1:
                target = stmt.targets[0].target
                if isinstance(target, cst.Name) and isinstance(stmt.value, cst.Call):
                    call = stmt.value
                    if isinstance(call.func, cst.Name) and call.func.value == "declarative_base":
                        var_name = target.value
                        self._declarative_base_var_name = var_name

                        self.record_change(
                            description=f"Replace {var_name} = declarative_base() with class {var_name}(DeclarativeBase): pass",
                            line_number=1,
                            original=f"{var_name} = declarative_base()",
                            replacement=f"class {var_name}(DeclarativeBase):\n    pass",
                            transform_name="declarative_base_to_class",
                            confidence=1.0,
                        )

                        # Create a class definition: class Base(DeclarativeBase): pass
                        class_def = cst.ClassDef(
                            name=cst.Name(var_name),
                            bases=[cst.Arg(value=cst.Name("DeclarativeBase"))],
                            body=cst.IndentedBlock(
                                body=[cst.SimpleStatementLine(body=[cst.Pass()])]
                            ),
                        )
                        return class_def

        return updated_node

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.BaseExpression:
        """Transform SQLAlchemy function calls."""
        # Handle session.query() transformations
        transformed = self._transform_query_call(updated_node)
        if transformed is not None:
            return transformed

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
                # Fix trailing comma: remove trailing comma from last argument if present
                if new_args:
                    last_arg = new_args[-1]
                    # Remove trailing comma from the last argument
                    if last_arg.comma != cst.MaybeSentinel.DEFAULT:
                        new_args[-1] = last_arg.with_changes(comma=cst.MaybeSentinel.DEFAULT)
                return updated_node.with_changes(args=new_args)

        # Handle execute() with raw SQL string - wrap with text()
        if (
            isinstance(updated_node.func, cst.Attribute)
            and updated_node.func.attr.value == "execute"
        ):
            # Check if this is engine.execute() - which requires manual migration
            # to use with engine.connect() as conn: conn.execute()
            if self._is_engine_execute_call(updated_node):
                self.record_change(
                    description="engine.execute() is removed in SQLAlchemy 2.0. "
                    "Use 'with engine.connect() as conn: conn.execute(...)' instead",
                    line_number=1,
                    original="engine.execute(...)",
                    replacement="with engine.connect() as conn:\n    conn.execute(...)",
                    transform_name="engine_execute_to_connect",
                    confidence=0.5,
                    notes="MANUAL MIGRATION REQUIRED: This transformation requires "
                    "restructuring the code to use a context manager. The execute() call "
                    "must be moved inside a 'with engine.connect() as conn:' block, and "
                    "raw SQL strings should be wrapped with text(). If the result is used, "
                    "ensure proper handling within the context manager scope.",
                )
                # Don't transform the code - just record the warning
                # The code still needs to have text() wrapping applied if applicable
                # Fall through to the text wrapping logic below

            if updated_node.args:
                first_arg = updated_node.args[0]
                # Check if the first argument is a string literal (raw SQL)
                if isinstance(first_arg.value, cst.SimpleString) or isinstance(
                    first_arg.value, cst.ConcatenatedString
                ):
                    # Wrap the string with text()
                    self._needs_text_import = True
                    text_call = cst.Call(
                        func=cst.Name("text"),
                        args=[cst.Arg(value=first_arg.value)],
                    )
                    new_first_arg = first_arg.with_changes(value=text_call)
                    new_args = [new_first_arg] + list(updated_node.args[1:])

                    self.record_change(
                        description="Wrap raw SQL string with text()",
                        line_number=1,
                        original='execute("...")',
                        replacement='execute(text("..."))',
                        transform_name="wrap_execute_with_text",
                    )

                    return updated_node.with_changes(args=new_args)

        return updated_node

    def _is_engine_execute_call(self, node: cst.Call) -> bool:
        """Check if a call is engine.execute() where engine is likely a SQLAlchemy engine.

        Uses heuristics:
        1. The variable is known to be assigned from create_engine()
        2. The variable name contains 'engine' (case insensitive)

        Args:
            node: The Call node to check (already verified to be *.execute())

        Returns:
            True if this appears to be an engine.execute() call
        """
        if not isinstance(node.func, cst.Attribute):
            return False

        caller = node.func.value
        if not isinstance(caller, cst.Name):
            return False

        var_name = caller.value

        # Check if this variable was assigned from create_engine()
        if var_name in self._engine_var_names:
            return True

        # Heuristic: check if variable name contains 'engine'
        if "engine" in var_name.lower():
            return True

        return False

    def _transform_query_call(self, node: cst.Call) -> cst.BaseExpression | None:
        """Transform session.query(...) patterns to session.execute(select(...)).

        Handles patterns like:
        - session.query(Model).all() -> session.execute(select(Model)).scalars().all()
        - session.query(Model).first() -> session.execute(select(Model)).scalars().first()
        - session.query(Model).one() -> session.execute(select(Model)).scalars().one()
        - session.query(Model).filter(...).all() -> session.execute(select(Model).where(...)).scalars().all()
        - session.query(Model).get(id) -> session.get(Model, id)
        - session.query(Model).count() -> session.execute(select(func.count()).select_from(Model)).scalar()

        Returns:
            Transformed node if this is a query pattern, None otherwise.
        """
        # Check if this is a method call (has Attribute as func)
        if not isinstance(node.func, cst.Attribute):
            return None

        # Find the terminal method being called (.all(), .first(), .get(), etc.)
        terminal_method = node.func.attr.value

        # Methods that end a query chain
        terminal_methods = {"all", "first", "one", "one_or_none", "get", "count", "scalar"}
        if terminal_method not in terminal_methods:
            return None

        # Walk up the chain to find .query() and collect intermediate methods
        chain_info = self._parse_query_chain(node)
        if chain_info is None:
            return None

        session_node, model_node, filters, terminal_method, terminal_args = chain_info

        # Handle .get(id) - transforms to session.get(Model, id)
        if terminal_method == "get":
            return self._transform_query_get(session_node, model_node, terminal_args)

        # Handle .count() - transforms to session.execute(select(func.count()).select_from(Model)).scalar()
        if terminal_method == "count":
            return self._transform_query_count(session_node, model_node, filters)

        # Handle .all(), .first(), .one(), .one_or_none(), .scalar()
        return self._transform_query_execute(session_node, model_node, filters, terminal_method)

    def _parse_query_chain(self, node: cst.Call) -> (
        tuple[
            cst.BaseExpression,
            cst.BaseExpression,
            list[cst.BaseExpression | _FilterByArg],
            str,
            Sequence[cst.Arg],
        ]
        | None
    ):
        """Parse a query chain to extract session, model, filters, and terminal method.

        Returns:
            Tuple of (session_node, model_node, filters, terminal_method, terminal_args) or None
        """
        if not isinstance(node.func, cst.Attribute):
            return None

        terminal_method = node.func.attr.value
        terminal_args = node.args
        current = node.func.value  # Move past the terminal method call
        filters: list[cst.BaseExpression | _FilterByArg] = []

        # Walk up the chain collecting .filter() and .filter_by() calls
        while True:
            if isinstance(current, cst.Call):
                func = current.func
                if isinstance(func, cst.Attribute):
                    method_name = func.attr.value

                    if method_name == "query":
                        # Found the root .query() call
                        session_node = func.value
                        if current.args:
                            model_node = current.args[0].value
                            return (
                                session_node,
                                model_node,
                                list(reversed(filters)),  # Reverse to get correct order
                                terminal_method,
                                terminal_args,
                            )
                        return None

                    elif method_name == "filter":
                        # Collect filter arguments
                        for arg in current.args:
                            filters.append(arg.value)
                        current = func.value

                    elif method_name == "filter_by":
                        # Convert filter_by(key=val) to Model.key == val
                        # Store the kwargs for handling during transform
                        for arg in current.args:
                            if arg.keyword is not None:
                                filters.append(_FilterByArg(arg.keyword.value, arg.value))
                        current = func.value

                    elif method_name in {
                        "order_by",
                        "limit",
                        "offset",
                        "distinct",
                        "group_by",
                        "having",
                        "join",
                        "outerjoin",
                    }:
                        # Skip these for now - they can be added to the select() later
                        current = func.value

                    else:
                        # Unknown method, not a query chain we can handle
                        return None
                else:
                    return None
            elif isinstance(current, cst.Attribute):
                # This might be something like query.Model or session.query
                return None
            else:
                return None

    def _transform_query_get(
        self,
        session_node: cst.BaseExpression,
        model_node: cst.BaseExpression,
        args: Sequence[cst.Arg],
    ) -> cst.Call:
        """Transform session.query(Model).get(id) to session.get(Model, id)."""
        self._needs_select_import = True

        self.record_change(
            description="Convert session.query(Model).get(id) to session.get(Model, id)",
            line_number=1,
            original="session.query(Model).get(id)",
            replacement="session.get(Model, id)",
            transform_name="query_get_to_session_get",
        )

        # Build session.get(Model, id)
        new_args = [cst.Arg(value=model_node)]
        new_args.extend(args)

        return cst.Call(
            func=cst.Attribute(value=session_node, attr=cst.Name("get")),
            args=new_args,
        )

    def _transform_query_count(
        self,
        session_node: cst.BaseExpression,
        model_node: cst.BaseExpression,
        filters: list[cst.BaseExpression | _FilterByArg],
    ) -> cst.Call:
        """Transform session.query(Model).count() to session.execute(select(func.count()).select_from(Model)).scalar()."""
        self._needs_select_import = True
        self._needs_func_import = True

        self.record_change(
            description="Convert session.query(Model).count() to session.execute(select(func.count()).select_from(Model)).scalar()",
            line_number=1,
            original="session.query(Model).count()",
            replacement="session.execute(select(func.count()).select_from(Model)).scalar()",
            transform_name="query_count_to_select_count",
        )

        # Build func.count()
        func_count = cst.Call(
            func=cst.Attribute(value=cst.Name("func"), attr=cst.Name("count")),
            args=[],
        )

        # Build select(func.count())
        select_call = cst.Call(
            func=cst.Name("select"),
            args=[cst.Arg(value=func_count)],
        )

        # Add .select_from(Model)
        select_from = cst.Call(
            func=cst.Attribute(value=select_call, attr=cst.Name("select_from")),
            args=[cst.Arg(value=model_node)],
        )

        # Add .where() if there are filters
        current: cst.BaseExpression = select_from
        for filter_expr in filters:
            if isinstance(filter_expr, _FilterByArg):
                # Convert filter_by to where with Model.attr == val
                where_condition = cst.Comparison(
                    left=cst.Attribute(value=model_node, attr=cst.Name(filter_expr.key)),
                    comparisons=[
                        cst.ComparisonTarget(
                            operator=cst.Equal(),
                            comparator=filter_expr.value,
                        )
                    ],
                )
                current = cst.Call(
                    func=cst.Attribute(value=current, attr=cst.Name("where")),
                    args=[cst.Arg(value=where_condition)],
                )
            else:
                current = cst.Call(
                    func=cst.Attribute(value=current, attr=cst.Name("where")),
                    args=[cst.Arg(value=filter_expr)],
                )

        # Build session.execute(...)
        execute_call = cst.Call(
            func=cst.Attribute(value=session_node, attr=cst.Name("execute")),
            args=[cst.Arg(value=current)],
        )

        # Add .scalar()
        return cst.Call(
            func=cst.Attribute(value=execute_call, attr=cst.Name("scalar")),
            args=[],
        )

    def _transform_query_execute(
        self,
        session_node: cst.BaseExpression,
        model_node: cst.BaseExpression,
        filters: list[cst.BaseExpression | _FilterByArg],
        terminal_method: str,
    ) -> cst.Call:
        """Transform session.query(Model).all/first/one() to session.execute(select(Model)).scalars().all/first/one()."""
        self._needs_select_import = True

        original = f"session.query(Model).{terminal_method}()"
        replacement = f"session.execute(select(Model)).scalars().{terminal_method}()"

        self.record_change(
            description=f"Convert {original} to {replacement}",
            line_number=1,
            original=original,
            replacement=replacement,
            transform_name=f"query_{terminal_method}_to_select",
        )

        # Build select(Model)
        select_call = cst.Call(
            func=cst.Name("select"),
            args=[cst.Arg(value=model_node)],
        )

        # Add .where() for each filter
        current: cst.BaseExpression = select_call
        for filter_expr in filters:
            if isinstance(filter_expr, _FilterByArg):
                # Convert filter_by to where with Model.attr == val
                where_condition = cst.Comparison(
                    left=cst.Attribute(value=model_node, attr=cst.Name(filter_expr.key)),
                    comparisons=[
                        cst.ComparisonTarget(
                            operator=cst.Equal(),
                            comparator=filter_expr.value,
                        )
                    ],
                )
                current = cst.Call(
                    func=cst.Attribute(value=current, attr=cst.Name("where")),
                    args=[cst.Arg(value=where_condition)],
                )
            else:
                current = cst.Call(
                    func=cst.Attribute(value=current, attr=cst.Name("where")),
                    args=[cst.Arg(value=filter_expr)],
                )

        # Build session.execute(...)
        execute_call = cst.Call(
            func=cst.Attribute(value=session_node, attr=cst.Name("execute")),
            args=[cst.Arg(value=current)],
        )

        # Add .scalars()
        scalars_call = cst.Call(
            func=cst.Attribute(value=execute_call, attr=cst.Name("scalars")),
            args=[],
        )

        # Add terminal method (.all(), .first(), .one(), etc.)
        return cst.Call(
            func=cst.Attribute(value=scalars_call, attr=cst.Name(terminal_method)),
            args=[],
        )

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


class SQLAlchemyImportTransformer(BaseTransformer):
    """Separate transformer for handling import additions.

    This runs after the main transformer to add any missing imports.
    """

    def __init__(
        self,
        needs_select_import: bool = False,
        needs_func_import: bool = False,
        needs_text_import: bool = False,
        has_text_import: bool = False,
    ) -> None:
        super().__init__()
        self._needs_select_import = needs_select_import
        self._needs_func_import = needs_func_import
        self._needs_text_import = needs_text_import
        self._has_text_import = has_text_import
        self._has_select_import = False
        self._has_func_import = False
        self._found_sqlalchemy_import = False

    def visit_ImportFrom(self, node: cst.ImportFrom) -> bool:
        """Check existing sqlalchemy imports."""
        if node.module is None:
            return True

        module_name = self._get_module_name(node.module)
        if module_name == "sqlalchemy":
            self._found_sqlalchemy_import = True
            if not isinstance(node.names, cst.ImportStar):
                for name in node.names:
                    if isinstance(name, cst.ImportAlias):
                        if isinstance(name.name, cst.Name):
                            if name.name.value == "text":
                                self._has_text_import = True
                            elif name.name.value == "select":
                                self._has_select_import = True
                            elif name.name.value == "func":
                                self._has_func_import = True

        return True

    def leave_ImportFrom(
        self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
    ) -> cst.ImportFrom:
        """Add missing imports to sqlalchemy import statement."""
        if updated_node.module is None:
            return updated_node

        module_name = self._get_module_name(updated_node.module)
        if module_name != "sqlalchemy":
            return updated_node

        if isinstance(updated_node.names, cst.ImportStar):
            return updated_node

        new_names = list(updated_node.names)
        changed = False

        # Add text import if needed and not already present
        if self._needs_text_import and not self._has_text_import:
            new_names.append(cst.ImportAlias(name=cst.Name("text")))
            self._has_text_import = True
            changed = True

        # Add select import if needed and not already present
        if self._needs_select_import and not self._has_select_import:
            new_names.append(cst.ImportAlias(name=cst.Name("select")))
            self._has_select_import = True
            changed = True

            self.record_change(
                description="Add 'select' import for query transformation",
                line_number=1,
                original="from sqlalchemy import ...",
                replacement="from sqlalchemy import ..., select",
                transform_name="add_select_import",
            )

        # Add func import if needed and not already present
        if self._needs_func_import and not self._has_func_import:
            new_names.append(cst.ImportAlias(name=cst.Name("func")))
            self._has_func_import = True
            changed = True

            self.record_change(
                description="Add 'func' import for count transformation",
                line_number=1,
                original="from sqlalchemy import ...",
                replacement="from sqlalchemy import ..., func",
                transform_name="add_func_import",
            )

        if changed:
            return updated_node.with_changes(names=new_names)

        return updated_node

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        """Add sqlalchemy import if not found but needed."""
        if self._found_sqlalchemy_import:
            return updated_node

        needs_import = (
            (self._needs_select_import and not self._has_select_import)
            or (self._needs_func_import and not self._has_func_import)
            or (self._needs_text_import and not self._has_text_import)
        )

        if not needs_import:
            return updated_node

        # Build the import names
        import_names = []
        if self._needs_select_import and not self._has_select_import:
            import_names.append(cst.ImportAlias(name=cst.Name("select")))
            self.record_change(
                description="Add 'select' import for query transformation",
                line_number=1,
                original="",
                replacement="from sqlalchemy import select",
                transform_name="add_select_import",
            )
        if self._needs_func_import and not self._has_func_import:
            import_names.append(cst.ImportAlias(name=cst.Name("func")))
            self.record_change(
                description="Add 'func' import for count transformation",
                line_number=1,
                original="",
                replacement="from sqlalchemy import func",
                transform_name="add_func_import",
            )
        if self._needs_text_import and not self._has_text_import:
            import_names.append(cst.ImportAlias(name=cst.Name("text")))

        if not import_names:
            return updated_node

        # Create the import statement
        new_import = cst.SimpleStatementLine(
            body=[
                cst.ImportFrom(
                    module=cst.Name("sqlalchemy"),
                    names=import_names,
                )
            ]
        )

        # Add at the beginning of the module (after any existing imports)
        new_body = [new_import] + list(updated_node.body)
        return updated_node.with_changes(body=new_body)

    def _get_module_name(self, module: cst.BaseExpression) -> str:
        """Get the full module name from an Attribute or Name node."""
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

        # Second pass: add missing imports
        import_transformer = SQLAlchemyImportTransformer(
            needs_select_import=transformer._needs_select_import,
            needs_func_import=transformer._needs_func_import,
            needs_text_import=transformer._needs_text_import,
            has_text_import=transformer._has_text_import,
        )
        final_tree = transformed_tree.visit(import_transformer)

        all_changes = transformer.changes + import_transformer.changes
        return final_tree.code, all_changes
    except Exception:
        return source_code, []
