"""Pandas 1.x to 2.0 transformation using LibCST."""

from typing import Optional, Sequence, Union

import libcst as cst
from libcst import matchers as m

from pyresolve.migrator.ast_transforms import BaseTransformer


class PandasTransformer(BaseTransformer):
    """Transform Pandas 1.x code to 2.0."""

    def __init__(self) -> None:
        super().__init__()

    def leave_Call(
        self, original_node: cst.Call, updated_node: cst.Call
    ) -> cst.Call:
        """Transform Pandas function calls."""
        # Handle to_csv line_terminator -> lineterminator
        if isinstance(updated_node.func, cst.Attribute):
            attr_name = updated_node.func.attr.value

            if attr_name == "to_csv":
                new_args = []
                changed = False
                for arg in updated_node.args:
                    if isinstance(arg.keyword, cst.Name) and arg.keyword.value == "line_terminator":
                        new_args.append(arg.with_changes(keyword=cst.Name("lineterminator")))
                        changed = True
                        self.record_change(
                            description="Rename to_csv line_terminator to lineterminator",
                            line_number=1,
                            original="to_csv(line_terminator=...)",
                            replacement="to_csv(lineterminator=...)",
                            transform_name="line_terminator_rename",
                        )
                    else:
                        new_args.append(arg)

                if changed:
                    return updated_node.with_changes(args=new_args)

            # Handle swaplevel axis removal
            if attr_name == "swaplevel":
                new_args = []
                changed = False
                for arg in updated_node.args:
                    if isinstance(arg.keyword, cst.Name) and arg.keyword.value == "axis":
                        changed = True
                        self.record_change(
                            description="Remove axis parameter from swaplevel",
                            line_number=1,
                            original="swaplevel(..., axis=...)",
                            replacement="swaplevel(...)",
                            transform_name="swaplevel_remove_axis",
                        )
                        continue
                    new_args.append(arg)

                if changed:
                    return updated_node.with_changes(args=new_args)

            # Handle reorder_levels axis removal
            if attr_name == "reorder_levels":
                new_args = []
                changed = False
                for arg in updated_node.args:
                    if isinstance(arg.keyword, cst.Name) and arg.keyword.value == "axis":
                        changed = True
                        self.record_change(
                            description="Remove axis parameter from reorder_levels",
                            line_number=1,
                            original="reorder_levels(..., axis=...)",
                            replacement="reorder_levels(...)",
                            transform_name="reorder_levels_remove_axis",
                        )
                        continue
                    new_args.append(arg)

                if changed:
                    return updated_node.with_changes(args=new_args)

            # Handle groupby numeric_only default changes
            if attr_name in ("mean", "sum", "prod", "std", "var", "min", "max"):
                # Check if called on groupby result and no numeric_only specified
                has_numeric_only = any(
                    isinstance(arg.keyword, cst.Name) and arg.keyword.value == "numeric_only"
                    for arg in updated_node.args
                )
                if not has_numeric_only:
                    # Record as potential issue but don't auto-change
                    self.record_change(
                        description=f"GroupBy.{attr_name}() numeric_only now defaults to False",
                        line_number=1,
                        original=f".{attr_name}()",
                        replacement=f".{attr_name}(numeric_only=True)",
                        transform_name=f"groupby_{attr_name}_numeric_only",
                        confidence=0.6,
                        notes="Add numeric_only=True if you want to exclude non-numeric columns",
                    )

        return updated_node

    def leave_Attribute(
        self, original_node: cst.Attribute, updated_node: cst.Attribute
    ) -> cst.Attribute:
        """Transform Pandas attribute accesses."""
        attr_name = updated_node.attr.value

        # Handle iteritems -> items
        if attr_name == "iteritems":
            self.record_change(
                description="Rename iteritems() to items()",
                line_number=1,
                original=".iteritems()",
                replacement=".items()",
                transform_name="iteritems_to_items",
            )
            return updated_node.with_changes(attr=cst.Name("items"))

        # Handle is_monotonic -> is_monotonic_increasing
        if attr_name == "is_monotonic":
            self.record_change(
                description="Rename is_monotonic to is_monotonic_increasing",
                line_number=1,
                original=".is_monotonic",
                replacement=".is_monotonic_increasing",
                transform_name="is_monotonic_to_increasing",
            )
            return updated_node.with_changes(attr=cst.Name("is_monotonic_increasing"))

        return updated_node


class PandasAppendTransformer(BaseTransformer):
    """Transform DataFrame.append() to pd.concat()."""

    def __init__(self) -> None:
        super().__init__()

    def leave_Call(
        self, original_node: cst.Call, updated_node: cst.Call
    ) -> cst.BaseExpression:
        """Transform append calls to concat."""
        if not isinstance(updated_node.func, cst.Attribute):
            return updated_node

        if updated_node.func.attr.value != "append":
            return updated_node

        # Get the object being called on
        obj = updated_node.func.value

        # Get the first positional argument (what's being appended)
        if not updated_node.args:
            return updated_node

        append_arg = updated_node.args[0].value

        # Check for ignore_index parameter
        ignore_index = False
        other_args = []
        for arg in updated_node.args[1:]:
            if isinstance(arg.keyword, cst.Name) and arg.keyword.value == "ignore_index":
                if isinstance(arg.value, cst.Name) and arg.value.value == "True":
                    ignore_index = True
            else:
                other_args.append(arg)

        # Build pd.concat call
        concat_args = [
            cst.Arg(
                value=cst.List(elements=[
                    cst.Element(value=obj),
                    cst.Element(value=append_arg),
                ])
            )
        ]

        if ignore_index:
            concat_args.append(
                cst.Arg(
                    keyword=cst.Name("ignore_index"),
                    value=cst.Name("True"),
                    equal=cst.AssignEqual(
                        whitespace_before=cst.SimpleWhitespace(""),
                        whitespace_after=cst.SimpleWhitespace(""),
                    ),
                )
            )

        self.record_change(
            description="Replace DataFrame.append() with pd.concat()",
            line_number=1,
            original=".append(...)",
            replacement="pd.concat([df1, df2], ...)",
            transform_name="append_to_concat",
        )

        return cst.Call(
            func=cst.Attribute(
                value=cst.Name("pd"),
                attr=cst.Name("concat"),
            ),
            args=concat_args,
        )


def transform_pandas(source_code: str) -> tuple[str, list]:
    """Transform Pandas code from 1.x to 2.0.

    Args:
        source_code: The source code to transform

    Returns:
        Tuple of (transformed_code, list of changes)
    """
    try:
        tree = cst.parse_module(source_code)
    except cst.ParserSyntaxError:
        return source_code, []

    # Apply main transformer
    transformer = PandasTransformer()
    transformer.set_source(source_code)

    try:
        transformed_tree = tree.visit(transformer)
        all_changes = list(transformer.changes)

        # Apply append transformer
        append_transformer = PandasAppendTransformer()
        append_transformer.set_source(transformed_tree.code)
        transformed_tree = transformed_tree.visit(append_transformer)
        all_changes.extend(append_transformer.changes)

        return transformed_tree.code, all_changes
    except Exception:
        return source_code, []
