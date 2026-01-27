"""Pytest 6.x to 7.x/8.x transformation using LibCST."""

import libcst as cst
from libcst import matchers as m

from codeshift.migrator.ast_transforms import BaseTransformer


class PytestTransformer(BaseTransformer):
    """Transform pytest 6.x code to 7.x/8.x compatible code."""

    def __init__(self) -> None:
        super().__init__()
        # Track current class context for setup/teardown transforms
        self._in_test_class = False
        self._current_class_name: str | None = None

    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
        """Track when we enter a test class."""
        class_name = node.name.value
        # Check if this looks like a test class
        if class_name.startswith("Test") or any(
            isinstance(base.value, cst.Name) and base.value.value == "TestCase"
            for base in node.bases
            if isinstance(base, cst.Arg)
        ):
            self._in_test_class = True
            self._current_class_name = class_name
        return True

    def leave_ClassDef(
        self, original_node: cst.ClassDef, updated_node: cst.ClassDef
    ) -> cst.ClassDef:
        """Reset class tracking when leaving a class."""
        self._in_test_class = False
        self._current_class_name = None
        return updated_node

    def leave_Decorator(
        self, original_node: cst.Decorator, updated_node: cst.Decorator
    ) -> cst.Decorator:
        """Transform @pytest.yield_fixture to @pytest.fixture."""
        # Handle @pytest.yield_fixture
        if m.matches(
            updated_node.decorator,
            m.Attribute(
                value=m.Name("pytest"),
                attr=m.Name("yield_fixture"),
            ),
        ):
            self.record_change(
                description="Convert @pytest.yield_fixture to @pytest.fixture",
                line_number=1,
                original="@pytest.yield_fixture",
                replacement="@pytest.fixture",
                transform_name="yield_fixture_to_fixture",
            )
            new_attr = cst.Attribute(
                value=cst.Name("pytest"),
                attr=cst.Name("fixture"),
            )
            return updated_node.with_changes(decorator=new_attr)

        # Handle @pytest.yield_fixture(...)
        if m.matches(
            updated_node.decorator,
            m.Call(
                func=m.Attribute(
                    value=m.Name("pytest"),
                    attr=m.Name("yield_fixture"),
                ),
            ),
        ):
            assert isinstance(updated_node.decorator, cst.Call)
            self.record_change(
                description="Convert @pytest.yield_fixture(...) to @pytest.fixture(...)",
                line_number=1,
                original="@pytest.yield_fixture(...)",
                replacement="@pytest.fixture(...)",
                transform_name="yield_fixture_to_fixture",
            )
            new_func = cst.Attribute(
                value=cst.Name("pytest"),
                attr=cst.Name("fixture"),
            )
            new_call = updated_node.decorator.with_changes(func=new_func)
            return updated_node.with_changes(decorator=new_call)

        return updated_node

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.FunctionDef:
        """Transform setup/teardown methods in test classes and fixture parameters."""
        # Handle tmpdir/tmpdir_factory fixture parameter renames
        updated_node = self._transform_fixture_params(updated_node)

        # Handle conftest hook parameter renames
        updated_node = self._transform_hook_params(updated_node)

        # Handle setup/teardown method renames only in test classes
        if self._in_test_class:
            func_name = updated_node.name.value

            if func_name == "setup":
                self.record_change(
                    description="Rename setup() to setup_method() for pytest 8.x compatibility",
                    line_number=1,
                    original="def setup(self):",
                    replacement="def setup_method(self):",
                    transform_name="setup_to_setup_method",
                )
                return updated_node.with_changes(name=cst.Name("setup_method"))

            if func_name == "teardown":
                self.record_change(
                    description="Rename teardown() to teardown_method() for pytest 8.x compatibility",
                    line_number=1,
                    original="def teardown(self):",
                    replacement="def teardown_method(self):",
                    transform_name="teardown_to_teardown_method",
                )
                return updated_node.with_changes(name=cst.Name("teardown_method"))

        return updated_node

    def _transform_fixture_params(self, node: cst.FunctionDef) -> cst.FunctionDef:
        """Transform tmpdir/tmpdir_factory fixture parameters to tmp_path/tmp_path_factory."""
        if node.params.params is None:
            return node

        new_params = []
        changed = False

        for param in node.params.params:
            param_name = param.name.value if isinstance(param.name, cst.Name) else None

            if param_name == "tmpdir":
                self.record_change(
                    description="Convert tmpdir fixture to tmp_path (pathlib.Path)",
                    line_number=1,
                    original="def func(tmpdir):",
                    replacement="def func(tmp_path):",
                    transform_name="tmpdir_to_tmp_path",
                )
                new_param = param.with_changes(name=cst.Name("tmp_path"))
                new_params.append(new_param)
                changed = True
            elif param_name == "tmpdir_factory":
                self.record_change(
                    description="Convert tmpdir_factory fixture to tmp_path_factory",
                    line_number=1,
                    original="def func(tmpdir_factory):",
                    replacement="def func(tmp_path_factory):",
                    transform_name="tmpdir_factory_to_tmp_path_factory",
                )
                new_param = param.with_changes(name=cst.Name("tmp_path_factory"))
                new_params.append(new_param)
                changed = True
            else:
                new_params.append(param)

        if changed:
            new_parameters = node.params.with_changes(params=new_params)
            return node.with_changes(params=new_parameters)

        return node

    def _transform_hook_params(self, node: cst.FunctionDef) -> cst.FunctionDef:
        """Transform pytest hook parameters for 7.x/8.x compatibility."""
        func_name = node.name.value

        # Map of hook names to parameter renames
        hook_param_renames: dict[str, dict[str, str]] = {
            "pytest_collect_file": {"path": "file_path"},
            "pytest_ignore_collect": {"path": "collection_path"},
            "pytest_pycollect_makemodule": {"path": "module_path"},
            "pytest_report_header": {"startdir": "start_path"},
            "pytest_report_collectionfinish": {"startdir": "start_path"},
        }

        if func_name not in hook_param_renames:
            return node

        param_renames = hook_param_renames[func_name]
        new_params = []
        changed = False

        for param in node.params.params:
            param_name = param.name.value if isinstance(param.name, cst.Name) else None

            if param_name in param_renames:
                new_name = param_renames[param_name]
                self.record_change(
                    description=f"Rename {func_name} parameter '{param_name}' to '{new_name}'",
                    line_number=1,
                    original=f"def {func_name}({param_name}):",
                    replacement=f"def {func_name}({new_name}):",
                    transform_name=f"hook_{param_name}_to_{new_name}",
                )
                new_param = param.with_changes(name=cst.Name(new_name))
                new_params.append(new_param)
                changed = True
            else:
                new_params.append(param)

        if changed:
            new_parameters = node.params.with_changes(params=new_params)
            return node.with_changes(params=new_parameters)

        return node

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.BaseExpression:
        """Transform pytest function calls."""
        # Handle pytest.skip(msg=...), pytest.fail(msg=...), pytest.exit(msg=...)
        updated_node = self._transform_msg_to_reason(updated_node)

        # Handle pytest.warns(None)
        updated_node = self._transform_warns_none(updated_node)

        return updated_node

    def _transform_msg_to_reason(self, node: cst.Call) -> cst.Call:
        """Transform msg parameter to reason in pytest.skip/fail/exit."""
        # Check if this is a pytest.skip, pytest.fail, or pytest.exit call
        if not isinstance(node.func, cst.Attribute):
            return node

        if not isinstance(node.func.value, cst.Name) or node.func.value.value != "pytest":
            return node

        func_name = node.func.attr.value
        if func_name not in ("skip", "fail", "exit"):
            return node

        # Look for msg= parameter and rename to reason=
        new_args = []
        changed = False

        for arg in node.args:
            if isinstance(arg.keyword, cst.Name) and arg.keyword.value == "msg":
                self.record_change(
                    description=f"Rename 'msg' parameter to 'reason' in pytest.{func_name}()",
                    line_number=1,
                    original=f"pytest.{func_name}(msg=...)",
                    replacement=f"pytest.{func_name}(reason=...)",
                    transform_name=f"{func_name}_msg_to_reason",
                )
                new_arg = arg.with_changes(keyword=cst.Name("reason"))
                new_args.append(new_arg)
                changed = True
            else:
                new_args.append(arg)

        if changed:
            return node.with_changes(args=new_args)

        return node

    def _transform_warns_none(self, node: cst.Call) -> cst.Call:
        """Transform pytest.warns(None) to pytest.warns()."""
        # Check if this is pytest.warns(None)
        if not isinstance(node.func, cst.Attribute):
            return node

        if not isinstance(node.func.value, cst.Name) or node.func.value.value != "pytest":
            return node

        if node.func.attr.value != "warns":
            return node

        # Check if the first argument is None
        if (
            len(node.args) >= 1
            and isinstance(node.args[0].value, cst.Name)
            and node.args[0].value.value == "None"
            and node.args[0].keyword is None
        ):
            self.record_change(
                description="Convert pytest.warns(None) to pytest.warns()",
                line_number=1,
                original="pytest.warns(None)",
                replacement="pytest.warns()",
                transform_name="warns_none_to_warns",
            )
            # Remove the None argument
            new_args = list(node.args[1:])
            return node.with_changes(args=new_args)

        return node

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.BaseExpression:
        """Transform attribute accesses like .fspath to .path and funcargnames to fixturenames."""
        attr_name = updated_node.attr.value

        # Transform .fspath to .path
        if attr_name == "fspath":
            self.record_change(
                description="Convert .fspath (py.path.local) to .path (pathlib.Path)",
                line_number=1,
                original=".fspath",
                replacement=".path",
                transform_name="fspath_to_path",
            )
            return updated_node.with_changes(attr=cst.Name("path"))

        # Transform .funcargnames to .fixturenames
        if attr_name == "funcargnames":
            self.record_change(
                description="Convert .funcargnames to .fixturenames",
                line_number=1,
                original=".funcargnames",
                replacement=".fixturenames",
                transform_name="funcargnames_to_fixturenames",
            )
            return updated_node.with_changes(attr=cst.Name("fixturenames"))

        return updated_node

    def leave_Name(self, original_node: cst.Name, updated_node: cst.Name) -> cst.BaseExpression:
        """Transform bare name references like tmpdir inside function bodies."""
        # Note: This is a simplified transform. In a real scenario, we'd need more
        # context to determine if 'tmpdir' is a variable reference to the fixture.
        # For safety, we only transform fixture parameters, not variable uses.
        return updated_node


def transform_pytest(source_code: str) -> tuple[str, list]:
    """Transform pytest code from 6.x to 7.x/8.x.

    Args:
        source_code: The source code to transform

    Returns:
        Tuple of (transformed_code, list of changes)
    """
    try:
        tree = cst.parse_module(source_code)
    except cst.ParserSyntaxError as e:
        raise SyntaxError(f"Invalid Python syntax: {e}") from e

    transformer = PytestTransformer()
    transformer.set_source(source_code)

    try:
        transformed_tree = tree.visit(transformer)
        return transformed_tree.code, transformer.changes
    except Exception as e:
        raise RuntimeError(f"Transform failed: {e}") from e
