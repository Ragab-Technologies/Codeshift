"""Tests for NumPy 1.x to 2.0 transforms."""

from codeshift.migrator.transforms.numpy_transformer import (
    transform_numpy,
)


class TestTypeAliasTransforms:
    """Tests for NumPy type alias removal transforms."""

    def test_bool_to_bool_(self):
        """Test numpy.bool -> numpy.bool_ transformation."""
        code = """import numpy as np
x = np.bool"""
        result, changes = transform_numpy(code)
        assert "np.bool_" in result
        assert "np.bool" not in result or "np.bool_" in result
        assert any(c.transform_name == "bool_to_bool_" for c in changes)

    def test_int_to_int_(self):
        """Test numpy.int -> numpy.int_ transformation."""
        code = """import numpy as np
x = np.int"""
        result, changes = transform_numpy(code)
        assert "np.int_" in result
        assert any(c.transform_name == "int_to_int_" for c in changes)

    def test_float_to_float64(self):
        """Test numpy.float -> numpy.float64 transformation."""
        code = """import numpy as np
x = np.float"""
        result, changes = transform_numpy(code)
        assert "np.float64" in result
        assert any(c.transform_name == "float_to_float64" for c in changes)

    def test_complex_to_complex128(self):
        """Test numpy.complex -> numpy.complex128 transformation."""
        code = """import numpy as np
x = np.complex"""
        result, changes = transform_numpy(code)
        assert "np.complex128" in result
        assert any(c.transform_name == "complex_to_complex128" for c in changes)

    def test_object_to_object_(self):
        """Test numpy.object -> numpy.object_ transformation."""
        code = """import numpy as np
x = np.object"""
        result, changes = transform_numpy(code)
        assert "np.object_" in result
        assert any(c.transform_name == "object_to_object_" for c in changes)

    def test_str_to_str_(self):
        """Test numpy.str -> numpy.str_ transformation."""
        code = """import numpy as np
x = np.str"""
        result, changes = transform_numpy(code)
        assert "np.str_" in result
        assert any(c.transform_name == "str_to_str_" for c in changes)

    def test_unicode_to_str_(self):
        """Test numpy.unicode_ -> numpy.str_ transformation."""
        code = """import numpy as np
x = np.unicode_"""
        result, changes = transform_numpy(code)
        assert "np.str_" in result
        assert any(c.transform_name == "unicode__to_str_" for c in changes)

    def test_string_to_bytes_(self):
        """Test numpy.string_ -> numpy.bytes_ transformation."""
        code = """import numpy as np
x = np.string_"""
        result, changes = transform_numpy(code)
        assert "np.bytes_" in result
        assert any(c.transform_name == "string__to_bytes_" for c in changes)

    def test_float__to_float64(self):
        """Test numpy.float_ -> numpy.float64 transformation."""
        code = """import numpy as np
x = np.float_"""
        result, changes = transform_numpy(code)
        assert "np.float64" in result
        assert any(c.transform_name == "float__to_float64" for c in changes)

    def test_cfloat_to_complex128(self):
        """Test numpy.cfloat -> numpy.complex128 transformation."""
        code = """import numpy as np
x = np.cfloat"""
        result, changes = transform_numpy(code)
        assert "np.complex128" in result
        assert any(c.transform_name == "cfloat_to_complex128" for c in changes)


class TestFunctionRenameTransforms:
    """Tests for NumPy function rename transforms."""

    def test_alltrue_to_all(self):
        """Test numpy.alltrue() -> numpy.all() transformation."""
        code = """import numpy as np
result = np.alltrue(arr)"""
        result, changes = transform_numpy(code)
        assert "np.all(" in result
        assert "np.alltrue(" not in result
        assert any(c.transform_name == "alltrue_to_all" for c in changes)

    def test_sometrue_to_any(self):
        """Test numpy.sometrue() -> numpy.any() transformation."""
        code = """import numpy as np
result = np.sometrue(arr)"""
        result, changes = transform_numpy(code)
        assert "np.any(" in result
        assert "np.sometrue(" not in result
        assert any(c.transform_name == "sometrue_to_any" for c in changes)

    def test_product_to_prod(self):
        """Test numpy.product() -> numpy.prod() transformation."""
        code = """import numpy as np
result = np.product(arr)"""
        result, changes = transform_numpy(code)
        assert "np.prod(" in result
        assert "np.product(" not in result
        assert any(c.transform_name == "product_to_prod" for c in changes)

    def test_cumproduct_to_cumprod(self):
        """Test numpy.cumproduct() -> numpy.cumprod() transformation."""
        code = """import numpy as np
result = np.cumproduct(arr)"""
        result, changes = transform_numpy(code)
        assert "np.cumprod(" in result
        assert "np.cumproduct(" not in result
        assert any(c.transform_name == "cumproduct_to_cumprod" for c in changes)

    def test_trapz_to_trapezoid(self):
        """Test numpy.trapz() -> numpy.trapezoid() transformation."""
        code = """import numpy as np
result = np.trapz(y, x)"""
        result, changes = transform_numpy(code)
        assert "np.trapezoid(" in result
        assert "np.trapz(" not in result
        assert any(c.transform_name == "trapz_to_trapezoid" for c in changes)

    def test_in1d_to_isin(self):
        """Test numpy.in1d() -> numpy.isin() transformation."""
        code = """import numpy as np
result = np.in1d(ar1, ar2)"""
        result, changes = transform_numpy(code)
        assert "np.isin(" in result
        assert "np.in1d(" not in result
        assert any(c.transform_name == "in1d_to_isin" for c in changes)

    def test_row_stack_to_vstack(self):
        """Test numpy.row_stack() -> numpy.vstack() transformation."""
        code = """import numpy as np
result = np.row_stack((a, b))"""
        result, changes = transform_numpy(code)
        assert "np.vstack(" in result
        assert "np.row_stack(" not in result
        assert any(c.transform_name == "row_stack_to_vstack" for c in changes)

    def test_msort_to_sort_axis0(self):
        """Test numpy.msort(a) -> numpy.sort(a, axis=0) transformation."""
        code = """import numpy as np
result = np.msort(arr)"""
        result, changes = transform_numpy(code)
        assert "np.sort(" in result
        assert "axis=0" in result
        assert "np.msort(" not in result
        assert any(c.transform_name == "msort_to_sort_axis0" for c in changes)

    def test_asfarray_to_asarray(self):
        """Test numpy.asfarray(a) -> numpy.asarray(a, dtype=float) transformation."""
        code = """import numpy as np
result = np.asfarray(data)"""
        result, changes = transform_numpy(code)
        assert "np.asarray(" in result
        assert "dtype=float" in result
        assert "np.asfarray(" not in result
        assert any(c.transform_name == "asfarray_to_asarray" for c in changes)

    def test_issubclass_to_builtin(self):
        """Test numpy.issubclass_() -> issubclass() transformation."""
        code = """import numpy as np
result = np.issubclass_(cls, np.ndarray)"""
        result, changes = transform_numpy(code)
        assert "issubclass(" in result
        assert "np.issubclass_(" not in result
        assert any(c.transform_name == "issubclass__to_builtin" for c in changes)


class TestConstantTransforms:
    """Tests for NumPy constant transforms."""

    def test_Inf_to_inf(self):
        """Test numpy.Inf -> numpy.inf transformation."""
        code = """import numpy as np
x = np.Inf"""
        result, changes = transform_numpy(code)
        assert "np.inf" in result
        # Check that it's lowercase inf, not Inf
        assert "np.Inf" not in result or "np.inf" in result
        assert any(c.transform_name == "Inf_to_inf" for c in changes)

    def test_Infinity_to_inf(self):
        """Test numpy.Infinity -> numpy.inf transformation."""
        code = """import numpy as np
x = np.Infinity"""
        result, changes = transform_numpy(code)
        assert "np.inf" in result
        assert any(c.transform_name == "Infinity_to_inf" for c in changes)

    def test_infty_to_inf(self):
        """Test numpy.infty -> numpy.inf transformation."""
        code = """import numpy as np
x = np.infty"""
        result, changes = transform_numpy(code)
        assert "np.inf" in result
        assert any(c.transform_name == "infty_to_inf" for c in changes)

    def test_NaN_to_nan(self):
        """Test numpy.NaN -> numpy.nan transformation."""
        code = """import numpy as np
x = np.NaN"""
        result, changes = transform_numpy(code)
        assert "np.nan" in result
        assert any(c.transform_name == "NaN_to_nan" for c in changes)

    def test_PINF_to_inf(self):
        """Test numpy.PINF -> numpy.inf transformation."""
        code = """import numpy as np
x = np.PINF"""
        result, changes = transform_numpy(code)
        assert "np.inf" in result
        assert any(c.transform_name == "PINF_to_inf" for c in changes)

    def test_NINF_to_neg_inf(self):
        """Test numpy.NINF -> -numpy.inf transformation."""
        code = """import numpy as np
x = np.NINF"""
        result, changes = transform_numpy(code)
        assert "-np.inf" in result
        assert "np.NINF" not in result
        assert any(c.transform_name == "NINF_to_neg_inf" for c in changes)

    def test_PZERO_to_zero(self):
        """Test numpy.PZERO -> 0.0 transformation."""
        code = """import numpy as np
x = np.PZERO"""
        result, changes = transform_numpy(code)
        assert "0.0" in result
        assert "np.PZERO" not in result
        assert any(c.transform_name == "PZERO_to_zero" for c in changes)

    def test_NZERO_to_neg_zero(self):
        """Test numpy.NZERO -> -0.0 transformation."""
        code = """import numpy as np
x = np.NZERO"""
        result, changes = transform_numpy(code)
        assert "-0.0" in result
        assert "np.NZERO" not in result
        assert any(c.transform_name == "NZERO_to_neg_zero" for c in changes)


class TestImportTransforms:
    """Tests for NumPy import transforms."""

    def test_import_bool_to_bool_(self):
        """Test from numpy import bool -> from numpy import bool_."""
        code = """from numpy import bool
x = bool"""
        result, changes = transform_numpy(code)
        assert "from numpy import bool_" in result
        assert any("import_bool_to_bool_" in c.transform_name for c in changes)

    def test_import_alltrue_to_all(self):
        """Test from numpy import alltrue -> from numpy import all."""
        code = """from numpy import alltrue
x = alltrue(arr)"""
        result, changes = transform_numpy(code)
        assert "from numpy import all" in result
        assert any("import_alltrue_to_all" in c.transform_name for c in changes)

    def test_import_multiple(self):
        """Test multiple deprecated imports in one line."""
        code = """from numpy import bool, int, float, alltrue"""
        result, changes = transform_numpy(code)
        assert "bool_" in result
        assert "int_" in result
        assert "float64" in result
        assert "all" in result


class TestNumpyAlias:
    """Tests for handling different numpy import aliases."""

    def test_numpy_full_name(self):
        """Test transformations with 'numpy' (not 'np')."""
        code = """import numpy
x = numpy.bool
y = numpy.alltrue(arr)"""
        result, changes = transform_numpy(code)
        assert "numpy.bool_" in result
        assert "numpy.all(" in result

    def test_custom_alias(self):
        """Test transformations with custom alias (import numpy as npy)."""
        code = """import numpy as npy
x = npy.bool
y = npy.alltrue(arr)"""
        result, changes = transform_numpy(code)
        assert "npy.bool_" in result
        assert "npy.all(" in result


class TestSyntaxErrorHandling:
    """Tests for syntax error handling."""

    def test_syntax_error_returns_original(self):
        """Test that syntax errors return original code."""
        code = """import numpy as np
np.alltrue("""
        result, changes = transform_numpy(code)
        assert result == code
        assert len(changes) == 0


class TestComplexTransforms:
    """Tests for complex multi-transform scenarios."""

    def test_multiple_transforms_in_one_file(self):
        """Test multiple transforms applied to one file."""
        code = """import numpy as np

# Type aliases
dtype = np.float
arr_type = np.bool

# Function calls
result1 = np.alltrue(arr)
result2 = np.product(arr)
result3 = np.trapz(y, x)

# Constants
pos_inf = np.Inf
neg_inf = np.NINF
nan_val = np.NaN
"""
        result, changes = transform_numpy(code)

        # Type aliases transformed
        assert "np.float64" in result
        assert "np.bool_" in result

        # Functions transformed
        assert "np.all(" in result
        assert "np.prod(" in result
        assert "np.trapezoid(" in result

        # Constants transformed
        assert "np.inf" in result
        assert "-np.inf" in result
        assert "np.nan" in result

        # Multiple changes recorded
        assert len(changes) >= 7

    def test_preserves_valid_code(self):
        """Test that valid NumPy 2.0 code is preserved."""
        code = """import numpy as np

# Already valid NumPy 2.0 code
dtype = np.float64
arr_type = np.bool_
result = np.all(arr)
infinity = np.inf
"""
        result, changes = transform_numpy(code)
        assert result == code
        assert len(changes) == 0

    def test_valid_python_output(self):
        """Test that transformed code is valid Python."""
        code = """import numpy as np

x = np.bool
y = np.int
z = np.float
c = np.complex
o = np.object
s = np.str

result = np.alltrue(arr)
sorted_arr = np.msort(arr)
inf_val = np.NINF
zero_val = np.PZERO
"""
        result, changes = transform_numpy(code)

        # Verify the code compiles without syntax errors
        compile(result, "<string>", "exec")

    def test_mixed_numpy_and_other_code(self):
        """Test that non-numpy code is not affected."""
        code = """import numpy as np

class MyClass:
    bool = True  # This should not be transformed
    float = 1.5  # This should not be transformed

x = np.bool  # This should be transformed
my_list = [1, 2, 3]
"""
        result, changes = transform_numpy(code)

        # numpy.bool should be transformed
        assert "np.bool_" in result

        # Class attributes should not be affected
        assert "bool = True" in result
        assert "float = 1.5" in result

        # Only numpy attributes should generate changes
        assert len(changes) == 1
