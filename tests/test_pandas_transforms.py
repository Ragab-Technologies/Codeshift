"""Tests for Pandas transformation."""

from pyresolve.migrator.transforms.pandas_transformer import (
    transform_pandas,
)


class TestMethodRenames:
    """Tests for Pandas method renames."""

    def test_iteritems_to_items(self):
        """Test iteritems() to items() transformation."""
        code = """for k, v in df.iteritems():
    print(k, v)"""
        result, changes = transform_pandas(code)
        assert ".items()" in result
        assert ".iteritems()" not in result
        assert any(c.transform_name == "iteritems_to_items" for c in changes)

    def test_is_monotonic_to_is_monotonic_increasing(self):
        """Test is_monotonic to is_monotonic_increasing transformation."""
        code = """if index.is_monotonic:
    pass"""
        result, changes = transform_pandas(code)
        assert ".is_monotonic_increasing" in result
        assert any(c.transform_name == "is_monotonic_to_increasing" for c in changes)


class TestToCsvTransforms:
    """Tests for to_csv parameter renames."""

    def test_line_terminator_to_lineterminator(self):
        """Test line_terminator -> lineterminator in to_csv."""
        code = """df.to_csv("file.csv", line_terminator="\\n")"""
        result, changes = transform_pandas(code)
        assert "lineterminator=" in result
        assert "line_terminator=" not in result
        assert any(c.transform_name == "line_terminator_rename" for c in changes)

    def test_to_csv_without_line_terminator_unchanged(self):
        """Test to_csv without line_terminator is unchanged."""
        code = """df.to_csv("file.csv", index=False)"""
        result, changes = transform_pandas(code)
        assert result == code


class TestAxisParameterRemoval:
    """Tests for axis parameter removal."""

    def test_swaplevel_axis_removed(self):
        """Test axis parameter removal from swaplevel."""
        code = """df.swaplevel(0, 1, axis=1)"""
        result, changes = transform_pandas(code)
        assert "axis=" not in result
        assert any(c.transform_name == "swaplevel_remove_axis" for c in changes)

    def test_reorder_levels_axis_removed(self):
        """Test axis parameter removal from reorder_levels."""
        code = """df.reorder_levels([1, 0], axis=0)"""
        result, changes = transform_pandas(code)
        assert "axis=" not in result
        assert any(c.transform_name == "reorder_levels_remove_axis" for c in changes)


class TestGroupByNumericOnly:
    """Tests for GroupBy numeric_only warnings."""

    def test_groupby_mean_numeric_only_warning(self):
        """Test GroupBy.mean() numeric_only warning."""
        code = """result = df.groupby("col").mean()"""
        result, changes = transform_pandas(code)
        assert any(c.transform_name == "groupby_mean_numeric_only" for c in changes)

    def test_groupby_sum_numeric_only_warning(self):
        """Test GroupBy.sum() numeric_only warning."""
        code = """result = df.groupby("col").sum()"""
        result, changes = transform_pandas(code)
        assert any(c.transform_name == "groupby_sum_numeric_only" for c in changes)

    def test_groupby_with_numeric_only_no_warning(self):
        """Test GroupBy with numeric_only specified has no warning."""
        code = """result = df.groupby("col").mean(numeric_only=True)"""
        result, changes = transform_pandas(code)
        assert not any("numeric_only" in c.transform_name for c in changes)


class TestAppendToConcat:
    """Tests for DataFrame.append() to pd.concat() transformation."""

    def test_simple_append_to_concat(self):
        """Test simple append to concat transformation."""
        code = """result = df1.append(df2)"""
        result, changes = transform_pandas(code)
        assert "pd.concat" in result
        assert ".append(" not in result
        assert any(c.transform_name == "append_to_concat" for c in changes)

    def test_append_with_ignore_index(self):
        """Test append with ignore_index to concat transformation."""
        code = """result = df1.append(df2, ignore_index=True)"""
        result, changes = transform_pandas(code)
        assert "pd.concat" in result
        assert "ignore_index=True" in result
        assert any(c.transform_name == "append_to_concat" for c in changes)


class TestSyntaxErrorHandling:
    """Tests for syntax error handling."""

    def test_syntax_error_returns_original(self):
        """Test that syntax errors return original code."""
        code = """df.to_csv("""
        result, changes = transform_pandas(code)
        assert result == code
        assert len(changes) == 0


class TestComplexTransforms:
    """Tests for complex multi-transform scenarios."""

    def test_multiple_transforms_in_one_file(self):
        """Test multiple transforms applied to one file."""
        code = """import pandas as pd

for k, v in df.iteritems():
    print(k)

if index.is_monotonic:
    df.to_csv("out.csv", line_terminator="\\r\\n")
"""
        result, changes = transform_pandas(code)
        assert ".items()" in result
        assert ".is_monotonic_increasing" in result
        assert "lineterminator=" in result
        assert len(changes) >= 3
