"""NumPy 1.x to 2.0 transformation using LibCST."""

import libcst as cst

from codeshift.migrator.ast_transforms import BaseTransformer


class NumPyTransformer(BaseTransformer):
    """Transform NumPy 1.x code to 2.0.

    Handles the following breaking changes:
    - Type alias removals (np.bool, np.int, np.float, np.complex, np.object, np.str)
    - Function renames (alltrue, sometrue, product, cumproduct, trapz, in1d, row_stack, msort)
    - Constant renames (Inf, Infinity, infty, NaN, PINF, NINF, PZERO, NZERO)
    - Other deprecated/removed functions
    """

    # Type alias mappings: old_name -> new_name
    TYPE_ALIAS_MAPPINGS = {
        # Python builtin shadows (high priority)
        "bool": "bool_",
        "int": "int_",
        "float": "float64",
        "complex": "complex128",
        "object": "object_",
        "str": "str_",
        # Other type aliases
        "unicode_": "str_",
        "string_": "bytes_",
        "float_": "float64",
        "complex_": "complex128",
        "cfloat": "complex128",
        "singlecomplex": "complex64",
        "longfloat": "longdouble",
        "longcomplex": "clongdouble",
        "clongfloat": "clongdouble",
    }

    # Function renames: old_name -> new_name
    FUNCTION_RENAMES = {
        "alltrue": "all",
        "sometrue": "any",
        "product": "prod",
        "cumproduct": "cumprod",
        "trapz": "trapezoid",
        "in1d": "isin",
        "row_stack": "vstack",
        "issubsctype": "issubdtype",
    }

    # Constant renames: old_name -> new_name
    CONSTANT_RENAMES = {
        "Inf": "inf",
        "Infinity": "inf",
        "infty": "inf",
        "NaN": "nan",
        "PINF": "inf",
    }

    # Constants that need special handling (replacement with expressions)
    CONSTANT_SPECIAL = {
        "NINF": "-np.inf",  # Requires special handling
        "PZERO": "0.0",
        "NZERO": "-0.0",
    }

    def __init__(self) -> None:
        super().__init__()
        self._numpy_aliases: set[str] = {"np", "numpy"}
        self._has_numpy_import = False

    def visit_ImportFrom(self, node: cst.ImportFrom) -> bool:
        """Track numpy imports to detect aliases."""
        if node.module is None:
            return True

        module_name = self._get_module_name(node.module)
        if module_name == "numpy" or module_name.startswith("numpy."):
            self._has_numpy_import = True
        return True

    def visit_Import(self, node: cst.Import) -> bool:
        """Track numpy import aliases (e.g., import numpy as np)."""
        if isinstance(node.names, cst.ImportStar):
            return True

        for alias in node.names:
            if isinstance(alias, cst.ImportAlias):
                name = self._get_name_value(alias.name)
                if name == "numpy":
                    self._has_numpy_import = True
                    if alias.asname:
                        if isinstance(alias.asname, cst.AsName):
                            if isinstance(alias.asname.name, cst.Name):
                                self._numpy_aliases.add(alias.asname.name.value)
        return True

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.BaseExpression:
        """Transform numpy attribute accesses."""
        attr_name = updated_node.attr.value

        # Check if this is a numpy attribute access
        if not self._is_numpy_attribute(updated_node):
            return updated_node

        # Handle type alias removals
        if attr_name in self.TYPE_ALIAS_MAPPINGS:
            new_attr = self.TYPE_ALIAS_MAPPINGS[attr_name]
            self.record_change(
                description=f"Replace numpy.{attr_name} with numpy.{new_attr}",
                line_number=1,
                original=f"numpy.{attr_name}",
                replacement=f"numpy.{new_attr}",
                transform_name=f"{attr_name}_to_{new_attr}",
            )
            return updated_node.with_changes(attr=cst.Name(new_attr))

        # Handle constant renames
        if attr_name in self.CONSTANT_RENAMES:
            new_attr = self.CONSTANT_RENAMES[attr_name]
            self.record_change(
                description=f"Replace numpy.{attr_name} with numpy.{new_attr}",
                line_number=1,
                original=f"numpy.{attr_name}",
                replacement=f"numpy.{new_attr}",
                transform_name=f"{attr_name}_to_{new_attr}",
            )
            return updated_node.with_changes(attr=cst.Name(new_attr))

        # Handle NINF -> -np.inf
        if attr_name == "NINF":
            self.record_change(
                description="Replace numpy.NINF with -numpy.inf",
                line_number=1,
                original="numpy.NINF",
                replacement="-numpy.inf",
                transform_name="NINF_to_neg_inf",
            )
            return cst.UnaryOperation(
                operator=cst.Minus(),
                expression=updated_node.with_changes(attr=cst.Name("inf")),
            )

        # Handle PZERO -> 0.0
        if attr_name == "PZERO":
            self.record_change(
                description="Replace numpy.PZERO with 0.0",
                line_number=1,
                original="numpy.PZERO",
                replacement="0.0",
                transform_name="PZERO_to_zero",
            )
            return cst.Float("0.0")

        # Handle NZERO -> -0.0
        if attr_name == "NZERO":
            self.record_change(
                description="Replace numpy.NZERO with -0.0",
                line_number=1,
                original="numpy.NZERO",
                replacement="-0.0",
                transform_name="NZERO_to_neg_zero",
            )
            return cst.UnaryOperation(
                operator=cst.Minus(),
                expression=cst.Float("0.0"),
            )

        return updated_node

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.BaseExpression:
        """Transform numpy function calls."""
        # Handle direct numpy function calls like np.alltrue(), np.product(), etc.
        if isinstance(updated_node.func, cst.Attribute):
            attr = updated_node.func
            func_name = attr.attr.value

            if not self._is_numpy_attribute(attr):
                return updated_node

            # Handle function renames
            if func_name in self.FUNCTION_RENAMES:
                new_func = self.FUNCTION_RENAMES[func_name]
                self.record_change(
                    description=f"Replace numpy.{func_name}() with numpy.{new_func}()",
                    line_number=1,
                    original=f"numpy.{func_name}()",
                    replacement=f"numpy.{new_func}()",
                    transform_name=f"{func_name}_to_{new_func}",
                )
                new_attr = attr.with_changes(attr=cst.Name(new_func))
                return updated_node.with_changes(func=new_attr)

            # Handle msort(a) -> sort(a, axis=0)
            if func_name == "msort":
                self.record_change(
                    description="Replace numpy.msort(a) with numpy.sort(a, axis=0)",
                    line_number=1,
                    original="numpy.msort(a)",
                    replacement="numpy.sort(a, axis=0)",
                    transform_name="msort_to_sort_axis0",
                )
                new_attr = attr.with_changes(attr=cst.Name("sort"))
                # Add axis=0 argument
                new_args = list(updated_node.args)
                new_args.append(
                    cst.Arg(
                        keyword=cst.Name("axis"),
                        value=cst.Integer("0"),
                        equal=cst.AssignEqual(
                            whitespace_before=cst.SimpleWhitespace(""),
                            whitespace_after=cst.SimpleWhitespace(""),
                        ),
                    )
                )
                return updated_node.with_changes(func=new_attr, args=new_args)

            # Handle asfarray(a) -> asarray(a, dtype=float)
            if func_name == "asfarray":
                self.record_change(
                    description="Replace numpy.asfarray(a) with numpy.asarray(a, dtype=float)",
                    line_number=1,
                    original="numpy.asfarray(a)",
                    replacement="numpy.asarray(a, dtype=float)",
                    transform_name="asfarray_to_asarray",
                )
                new_attr = attr.with_changes(attr=cst.Name("asarray"))
                # Check if dtype is already specified
                has_dtype = any(
                    isinstance(arg.keyword, cst.Name) and arg.keyword.value == "dtype"
                    for arg in updated_node.args
                )
                new_args = list(updated_node.args)
                if not has_dtype:
                    new_args.append(
                        cst.Arg(
                            keyword=cst.Name("dtype"),
                            value=cst.Name("float"),
                            equal=cst.AssignEqual(
                                whitespace_before=cst.SimpleWhitespace(""),
                                whitespace_after=cst.SimpleWhitespace(""),
                            ),
                        )
                    )
                return updated_node.with_changes(func=new_attr, args=new_args)

            # Handle issubclass_(arg1, arg2) -> issubclass(arg1, arg2)
            if func_name == "issubclass_":
                self.record_change(
                    description="Replace numpy.issubclass_() with builtin issubclass()",
                    line_number=1,
                    original="numpy.issubclass_()",
                    replacement="issubclass()",
                    transform_name="issubclass__to_builtin",
                )
                return updated_node.with_changes(func=cst.Name("issubclass"))

        return updated_node

    def _is_numpy_attribute(self, node: cst.Attribute) -> bool:
        """Check if an Attribute node is accessing numpy.

        Handles both 'numpy.X' and 'np.X' patterns.
        """
        if isinstance(node.value, cst.Name):
            return node.value.value in self._numpy_aliases
        return False

    def _get_module_name(self, node: cst.BaseExpression) -> str:
        """Get the full module name from an Attribute or Name node."""
        if isinstance(node, cst.Name):
            return str(node.value)
        if isinstance(node, cst.Attribute):
            base = self._get_module_name(node.value)
            return f"{base}.{node.attr.value}"
        return ""

    def _get_name_value(self, node: cst.BaseExpression) -> str | None:
        """Extract the string value from a Name node."""
        if isinstance(node, cst.Name):
            return str(node.value)
        if isinstance(node, cst.Attribute):
            return self._get_module_name(node)
        return None


class NumPyImportTransformer(BaseTransformer):
    """Transform numpy imports (e.g., from numpy import bool -> from numpy import bool_)."""

    # Import name mappings
    IMPORT_MAPPINGS = {
        "bool": "bool_",
        "int": "int_",
        "float": "float64",
        "complex": "complex128",
        "object": "object_",
        "str": "str_",
        "unicode_": "str_",
        "string_": "bytes_",
        "float_": "float64",
        "complex_": "complex128",
        "cfloat": "complex128",
        "singlecomplex": "complex64",
        "longfloat": "longdouble",
        "longcomplex": "clongdouble",
        "clongfloat": "clongdouble",
        "alltrue": "all",
        "sometrue": "any",
        "product": "prod",
        "cumproduct": "cumprod",
        "trapz": "trapezoid",
        "in1d": "isin",
        "row_stack": "vstack",
        "issubsctype": "issubdtype",
        "Inf": "inf",
        "Infinity": "inf",
        "infty": "inf",
        "NaN": "nan",
        "PINF": "inf",
    }

    def leave_ImportFrom(
        self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
    ) -> cst.ImportFrom:
        """Transform imports from numpy."""
        if updated_node.module is None:
            return updated_node

        module_name = self._get_module_name(updated_node.module)
        if module_name != "numpy":
            return updated_node

        if isinstance(updated_node.names, cst.ImportStar):
            return updated_node

        new_names = []
        changed = False

        for name in updated_node.names:
            if isinstance(name, cst.ImportAlias):
                imported_name = self._get_name_value(name.name)

                if imported_name in self.IMPORT_MAPPINGS:
                    new_import_name = self.IMPORT_MAPPINGS[imported_name]
                    new_name = name.with_changes(name=cst.Name(new_import_name))
                    new_names.append(new_name)
                    changed = True

                    self.record_change(
                        description=f"Replace 'from numpy import {imported_name}' with '{new_import_name}'",
                        line_number=1,
                        original=f"from numpy import {imported_name}",
                        replacement=f"from numpy import {new_import_name}",
                        transform_name=f"import_{imported_name}_to_{new_import_name}",
                    )
                else:
                    new_names.append(name)

        if changed:
            return updated_node.with_changes(names=new_names)

        return updated_node

    def _get_module_name(self, node: cst.BaseExpression) -> str:
        """Get the full module name from an Attribute or Name node."""
        if isinstance(node, cst.Name):
            return str(node.value)
        if isinstance(node, cst.Attribute):
            base = self._get_module_name(node.value)
            return f"{base}.{node.attr.value}"
        return ""

    def _get_name_value(self, node: cst.BaseExpression) -> str | None:
        """Extract the string value from a Name node."""
        if isinstance(node, cst.Name):
            return str(node.value)
        return None


def transform_numpy(source_code: str) -> tuple[str, list]:
    """Transform NumPy code from 1.x to 2.0.

    Args:
        source_code: The source code to transform

    Returns:
        Tuple of (transformed_code, list of changes)
    """
    try:
        tree = cst.parse_module(source_code)
    except cst.ParserSyntaxError:
        return source_code, []

    all_changes = []

    try:
        # First pass: transform imports
        import_transformer = NumPyImportTransformer()
        import_transformer.set_source(source_code)
        tree = tree.visit(import_transformer)
        all_changes.extend(import_transformer.changes)

        # Second pass: main transformations
        transformer = NumPyTransformer()
        transformer.set_source(tree.code)
        tree = tree.visit(transformer)
        all_changes.extend(transformer.changes)

        return tree.code, all_changes
    except Exception:
        return source_code, []
