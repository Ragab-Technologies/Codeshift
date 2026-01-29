"""
Stress Test: NumPy 1.x to 2.x Scientific Computing Migration
=============================================================

This file contains INTENTIONALLY DEPRECATED NumPy 1.x code patterns
to stress test the Codeshift migration tool. It covers:

- Type aliases (np.int, np.float, np.complex, np.object, np.bool, np.str)
- Matrix multiplication patterns
- ufunc operations
- Broadcasting edge cases
- np.matrix usage (deprecated)
- np.MachAr usage (removed in NumPy 2.0)
- np.rank() -> np.ndim()
- np.PINF, np.NINF, np.PZERO, np.NZERO constants
- Linear algebra operations
- FFT operations
- Random number generation (old vs new API)
- Masked arrays

This is NOT production code - it is designed to exercise migration paths.
"""

import numpy as np
from numpy.fft import fft, ifft
from numpy.linalg import det, eig, inv, svd
from numpy.ma import masked_array

# =============================================================================
# SECTION 1: TYPE ALIASES (All deprecated in NumPy 2.0)
# =============================================================================

def type_alias_stress_test():
    """Test all deprecated type alias patterns."""

    # Basic type aliases
    int_type = np.int_
    float_type = np.float64
    complex_type = np.complex128
    bool_type = np.bool_
    object_type = np.object_
    str_type = np.str_

    # Type aliases in array creation
    arr_int = np.array([1, 2, 3], dtype=np.int_)
    arr_float = np.array([1.0, 2.0, 3.0], dtype=np.float64)
    arr_complex = np.array([1+2j, 3+4j], dtype=np.complex128)
    arr_bool = np.array([True, False], dtype=np.bool_)
    arr_object = np.array([object(), object()], dtype=np.object_)
    arr_str = np.array(['hello', 'world'], dtype=np.str_)

    # Using type aliases in isinstance checks
    x = np.array([1, 2, 3])
    is_int = x.dtype == np.int_
    is_float = x.dtype == np.float64

    # Unicode and string type aliases
    unicode_type = np.str_
    string_type = np.bytes_

    # Additional deprecated type aliases
    float__type = np.float64
    cfloat_type = np.complex128
    singlecomplex_type = np.complex64
    longcomplex_type = np.clongdouble

    return {
        'int_type': int_type,
        'float_type': float_type,
        'complex_type': complex_type,
        'bool_type': bool_type,
        'object_type': object_type,
        'str_type': str_type,
    }


# =============================================================================
# SECTION 2: DEPRECATED CONSTANTS
# =============================================================================

def constant_stress_test():
    """Test all deprecated constant patterns."""

    # Infinity variants
    pos_inf_1 = np.inf
    pos_inf_2 = np.inf
    pos_inf_3 = np.inf
    pos_inf_4 = np.inf
    neg_inf = -np.inf

    # Zero variants
    pos_zero = 0.0
    neg_zero = -0.0

    # NaN variants
    nan_1 = np.nan
    nan_2 = np.NAN

    # Using constants in comparisons
    arr = np.array([1.0, np.inf, -np.inf, np.nan])
    has_inf = np.any(arr == np.inf)
    has_nan = np.any(np.isnan(arr))

    # Using PINF/NINF in calculations
    clipped = np.clip(arr, -np.inf, np.inf)

    return {
        'pos_inf': pos_inf_1,
        'neg_inf': neg_inf,
        'pos_zero': pos_zero,
        'neg_zero': neg_zero,
        'nan': nan_1,
    }


# =============================================================================
# SECTION 3: DEPRECATED FUNCTIONS
# =============================================================================

def function_rename_stress_test():
    """Test all deprecated function renames."""

    arr = np.array([1, 2, 3, 4, 5])
    arr2d = np.array([[1, 2], [3, 4]])

    # alltrue -> all
    all_positive = np.all(arr > 0)

    # sometrue -> any
    any_even = np.any(arr % 2 == 0)

    # product -> prod
    total_product = np.prod(arr)

    # cumproduct -> cumprod
    running_product = np.cumprod(arr)

    # rank -> ndim (CRITICAL: rank() is completely removed!)
    array_rank = np.rank(arr2d)

    # msort -> sort with axis=0
    sorted_arr = np.sort(arr, axis=0)

    # trapz -> trapezoid
    x = np.linspace(0, 10, 100)
    y = np.sin(x)
    area = np.trapezoid(y, x)

    # in1d -> isin
    test_vals = np.array([2, 4, 6])
    mask = np.isin(arr, test_vals)

    # row_stack -> vstack
    stacked = np.vstack((arr, arr * 2))

    # asfarray -> asarray with dtype=float
    float_arr = np.asarray([1, 2, 3], dtype=float)

    # issubclass_ -> builtin issubclass
    is_subclass = issubclass(np.ndarray, object)

    return {
        'all_positive': all_positive,
        'any_even': any_even,
        'total_product': total_product,
        'running_product': running_product,
        'array_rank': array_rank,
        'area': area,
    }


# =============================================================================
# SECTION 4: MATRIX CLASS (Deprecated in NumPy 1.15+, to be removed)
# =============================================================================

def matrix_stress_test():
    """Test np.matrix usage - deprecated and to be removed."""

    # Creating matrices
    m1 = np.matrix([[1, 2], [3, 4]])
    m2 = np.matrix([[5, 6], [7, 8]])

    # Matrix multiplication with * operator (different from ndarray!)
    m_product = m1 * m2

    # Matrix power
    m_squared = m1 ** 2

    # Matrix inverse
    m_inv = m1.I

    # Matrix transpose
    m_trans = m1.T

    # Matrix from string
    m_str = np.matrix('1 2; 3 4')

    # Mixing matrix and array operations (problematic!)
    arr = np.array([[1, 2], [3, 4]])
    mixed = m1 * arr  # Returns matrix!

    # Matrix-specific attributes
    m_flat = m1.A1  # Flatten to 1D array
    m_array = m1.A  # Convert to array

    return {
        'm_product': m_product,
        'm_squared': m_squared,
        'm_inv': m_inv,
    }


# =============================================================================
# SECTION 5: np.MachAr (Removed in NumPy 2.0)
# =============================================================================

def machar_stress_test():
    """Test np.MachAr usage - completely removed in NumPy 2.0."""

    # MachAr for float64
    machar_float64 = np.MachAr()

    # Getting machine parameters
    eps = machar_float64.eps
    huge = machar_float64.huge
    tiny = machar_float64.tiny
    precision = machar_float64.precision

    # MachAr with custom float type
    machar_float32 = np.MachAr(float_conv=np.float32)

    return {
        'eps': eps,
        'huge': huge,
        'tiny': tiny,
        'precision': precision,
    }


# =============================================================================
# SECTION 6: LINEAR ALGEBRA WITH DEPRECATED PATTERNS
# =============================================================================

def linalg_stress_test():
    """Test linear algebra operations with deprecated patterns."""

    # Create test matrices with deprecated types
    A = np.array([[1, 2], [3, 4]], dtype=np.float64)
    B = np.array([[5, 6], [7, 8]], dtype=np.float64)

    # Matrix multiplication patterns
    # Old style: np.dot() for matrix multiply
    C = np.dot(A, B)

    # Modern style: @ operator (Python 3.5+) - should be preserved
    D = A @ B

    # Matrix operations
    A_inv = inv(A)
    A_det = det(A)
    eigenvalues, eigenvectors = eig(A)
    U, S, Vt = svd(A)

    # Using np.matrix for convenience (deprecated!)
    M = np.matrix(A)
    M_inv = M.I

    # Solving linear equations with deprecated types
    b = np.array([1, 2], dtype=np.float64)
    x = np.linalg.solve(A, b)

    # QR decomposition
    Q, R = np.linalg.qr(A)

    # Cholesky decomposition (requires positive definite matrix)
    P = np.array([[4, 2], [2, 3]], dtype=np.float64)
    L = np.linalg.cholesky(P)

    return {
        'C': C,
        'D': D,
        'A_inv': A_inv,
        'A_det': A_det,
        'eigenvalues': eigenvalues,
    }


# =============================================================================
# SECTION 7: FFT OPERATIONS WITH DEPRECATED TYPES
# =============================================================================

def fft_stress_test():
    """Test FFT operations with deprecated type patterns."""

    # Create signal with deprecated type
    t = np.linspace(0, 1, 1000, dtype=np.float64)
    signal = np.sin(2 * np.pi * 10 * t) + 0.5 * np.sin(2 * np.pi * 20 * t)
    signal = signal.astype(np.complex128)  # Deprecated type!

    # Forward FFT
    spectrum = fft(signal)

    # Inverse FFT
    reconstructed = ifft(spectrum)

    # 2D FFT with deprecated types
    image = np.random.rand(64, 64).astype(np.float64)
    image_spectrum = np.fft.fft2(image)

    # FFT frequency calculation
    freqs = np.fft.fftfreq(len(signal), d=1/1000)

    # Real FFT
    real_signal = signal.real.astype(np.float64)
    real_spectrum = np.fft.rfft(real_signal)

    return {
        'spectrum': spectrum,
        'reconstructed': reconstructed,
        'freqs': freqs,
    }


# =============================================================================
# SECTION 8: RANDOM NUMBER GENERATION (Old vs New API)
# =============================================================================

def random_stress_test():
    """Test random number generation with old API patterns."""

    # Old API: using np.random directly (legacy, but still works)
    np.random.seed(42)

    # Deprecated in favor of Generator
    rand_uniform = np.random.rand(10)
    rand_normal = np.random.randn(10)
    rand_int = np.random.randint(0, 100, 10)

    # Random choice with deprecated behavior
    choice = np.random.choice([1, 2, 3, 4, 5], size=3, replace=False)

    # Random permutation
    arr = np.array([1, 2, 3, 4, 5])
    perm = np.random.permutation(arr)

    # Random shuffle (in-place)
    arr_copy = arr.copy()
    np.random.shuffle(arr_copy)

    # RandomState (legacy)
    rng_legacy = np.random.RandomState(42)
    legacy_sample = rng_legacy.random_sample(10)

    # New API: Generator (NumPy 1.17+) - should be preserved
    rng = np.random.default_rng(42)
    new_sample = rng.random(10)

    # Using deprecated dtype in random
    random_float = np.random.random(10).astype(np.float64)
    random_int = np.random.randint(0, 100, 10).astype(np.int_)

    return {
        'rand_uniform': rand_uniform,
        'rand_normal': rand_normal,
        'rand_int': rand_int,
        'legacy_sample': legacy_sample,
        'new_sample': new_sample,
    }


# =============================================================================
# SECTION 9: MASKED ARRAYS WITH DEPRECATED PATTERNS
# =============================================================================

def masked_array_stress_test():
    """Test masked array operations with deprecated patterns."""

    # Create masked array with deprecated types
    data = np.array([1, 2, 3, 4, 5], dtype=np.float64)
    mask = np.array([False, False, True, False, False], dtype=np.bool_)

    ma = masked_array(data, mask=mask)

    # Operations on masked arrays
    ma_sum = ma.sum()
    ma_mean = ma.mean()
    ma_std = ma.std()

    # Masked array with fill value
    ma_filled = ma.filled(-np.inf)  # Deprecated constant!

    # Masking based on condition
    arr = np.array([1.0, np.inf, 2.0, np.nan, 3.0])
    masked_inf = np.ma.masked_where(arr == np.inf, arr)
    masked_nan = np.ma.masked_invalid(arr)

    # Combined operations
    result = np.all(masked_nan.mask == False)  # Deprecated function!

    return {
        'ma_sum': ma_sum,
        'ma_mean': ma_mean,
        'ma_filled': ma_filled,
    }


# =============================================================================
# SECTION 10: BROADCASTING EDGE CASES WITH DEPRECATED TYPES
# =============================================================================

def broadcasting_stress_test():
    """Test broadcasting with deprecated type patterns."""

    # Create arrays with deprecated types
    a = np.array([1, 2, 3], dtype=np.float64)
    b = np.array([[1], [2], [3]], dtype=np.float64)

    # Broadcasting operations
    c = a + b  # (3,) + (3, 1) = (3, 3)

    # Complex broadcasting with deprecated types
    x = np.array([[1, 2, 3]], dtype=np.complex128)
    y = np.array([[1], [2], [3]], dtype=np.complex128)
    z = x * y  # (1, 3) * (3, 1) = (3, 3)

    # Broadcasting with object arrays (deprecated type)
    obj_arr = np.array([1, 2, 3], dtype=np.object_)
    broadcasted = obj_arr + np.array([10])

    # Boolean operations with broadcasting
    bool_arr = np.array([True, False, True], dtype=np.bool_)
    bool_result = np.all(bool_arr)  # Deprecated function!

    # Using deprecated constants in broadcasting
    arr_with_inf = np.array([1.0, 2.0, 3.0]) + np.inf
    arr_clamped = np.clip(arr_with_inf, -np.inf, np.inf)

    return {
        'c': c,
        'z': z,
        'bool_result': bool_result,
    }


# =============================================================================
# SECTION 11: UFUNC OPERATIONS WITH DEPRECATED PATTERNS
# =============================================================================

def ufunc_stress_test():
    """Test ufunc operations with deprecated patterns."""

    # Create test arrays with deprecated types
    a = np.array([1, 2, 3, 4, 5], dtype=np.float64)
    b = np.array([5, 4, 3, 2, 1], dtype=np.float64)

    # Basic ufuncs
    add_result = np.add(a, b)
    multiply_result = np.multiply(a, b)

    # Ufunc reduce with deprecated types
    sum_result = np.add.reduce(a)
    prod_result = np.multiply.reduce(a)  # vs np.product (deprecated)

    # Ufunc accumulate
    cumsum = np.add.accumulate(a)
    cumprod = np.multiply.accumulate(a)  # vs np.cumproduct (deprecated)

    # Ufunc at (in-place operation)
    arr = np.array([1, 2, 3, 4, 5], dtype=np.float64)
    np.add.at(arr, [0, 2, 4], 10)

    # Custom output array with deprecated type
    out = np.zeros(5, dtype=np.float64)
    np.add(a, b, out=out)

    # Comparison ufuncs with deprecated types
    bool_mask = np.greater(a, 2).astype(np.bool_)

    # Using alltrue/sometrue with ufunc results
    all_gt = np.all(a > 0)  # Deprecated!
    any_gt = np.any(b < 3)  # Deprecated!

    return {
        'add_result': add_result,
        'sum_result': sum_result,
        'cumsum': cumsum,
        'all_gt': all_gt,
    }


# =============================================================================
# SECTION 12: EDGE CASES AND CORNER CASES
# =============================================================================

def edge_case_stress_test():
    """Test edge cases and corner cases with deprecated patterns."""

    # Empty array with deprecated type
    empty = np.array([], dtype=np.float64)

    # Single element with deprecated type
    single = np.array([42], dtype=np.int_)

    # Very large array with deprecated type
    large = np.zeros(1000000, dtype=np.float64)

    # Multi-dimensional with deprecated types
    multi_dim = np.zeros((10, 10, 10), dtype=np.complex128)

    # Nested operations with multiple deprecated patterns
    result = np.all(
        np.array([True, True, True], dtype=np.bool_)
    )  # Deprecated function + type!

    # Using rank() on different dimension arrays
    r1 = np.rank(np.array([1]))  # 1D
    r2 = np.rank(np.array([[1]]))  # 2D
    r3 = np.rank(np.array([[[1]]]))  # 3D

    # Infinity comparisons with deprecated constants
    inf_comparisons = {
        'pinf_gt_ninf': np.inf > -np.inf,
        'inf_eq_pinf': np.inf == np.inf,
        'nan_neq_nan': np.nan != np.nan,
    }

    # Chained deprecated operations
    arr = np.array([1, 2, 3, 4, 5], dtype=np.float64)
    chained = np.trapezoid(
        np.cumprod(arr) / np.prod(arr),
        dx=1.0
    )

    return {
        'result': result,
        'r1': r1,
        'r2': r2,
        'r3': r3,
        'inf_comparisons': inf_comparisons,
        'chained': chained,
    }


# =============================================================================
# SECTION 13: COMPLEX REAL-WORLD SCENARIO
# =============================================================================

class ScientificSimulation:
    """A complex class using many deprecated NumPy patterns."""

    def __init__(self, n_particles: int = 100):
        """Initialize simulation with deprecated types."""
        self.n_particles = n_particles

        # Particle positions (deprecated type)
        self.positions = np.random.rand(n_particles, 3).astype(np.float64)

        # Particle velocities (deprecated type)
        self.velocities = np.zeros((n_particles, 3), dtype=np.float64)

        # Particle masses (deprecated type)
        self.masses = np.ones(n_particles, dtype=np.float64)

        # Active particles mask (deprecated type)
        self.active = np.ones(n_particles, dtype=np.bool_)

        # Time step
        self.dt = 0.01

        # Physical constants with deprecated values
        self.G = 6.674e-11
        self.max_force = np.inf
        self.min_distance = 0.0 + 1e-10

    def compute_forces(self) -> np.ndarray:
        """Compute gravitational forces between particles."""
        forces = np.zeros((self.n_particles, 3), dtype=np.float64)

        for i in range(self.n_particles):
            if not self.active[i]:
                continue

            for j in range(i + 1, self.n_particles):
                if not self.active[j]:
                    continue

                # Calculate distance
                r_vec = self.positions[j] - self.positions[i]
                r_mag = np.sqrt(np.prod(r_vec ** 2))  # Deprecated!

                if r_mag < self.min_distance:
                    r_mag = self.min_distance

                # Calculate force
                f_mag = self.G * self.masses[i] * self.masses[j] / (r_mag ** 2)
                f_vec = f_mag * r_vec / r_mag

                # Clamp force
                f_vec = np.clip(f_vec, -np.inf, self.max_force)

                forces[i] += f_vec
                forces[j] -= f_vec

        return forces

    def step(self) -> None:
        """Advance simulation by one time step."""
        forces = self.compute_forces()

        # Update velocities
        accelerations = forces / self.masses[:, np.newaxis]
        self.velocities += accelerations * self.dt

        # Update positions
        self.positions += self.velocities * self.dt

        # Check for particles at infinity
        at_inf = np.all(np.abs(self.positions) == np.inf, axis=1)  # Deprecated!
        self.active[at_inf] = False

    def run(self, n_steps: int) -> dict:
        """Run simulation for n_steps."""
        for _ in range(n_steps):
            self.step()

        return {
            'final_positions': self.positions,
            'final_velocities': self.velocities,
            'active_count': np.all(self.active),  # Deprecated!
            'total_momentum': np.prod(self.masses * np.sum(self.velocities, axis=1)),  # Deprecated!
        }


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """Run all stress tests and report results."""
    print("NumPy 1.x -> 2.x Migration Stress Test")
    print("=" * 50)

    # Run all tests
    tests = [
        ("Type Aliases", type_alias_stress_test),
        ("Constants", constant_stress_test),
        ("Function Renames", function_rename_stress_test),
        ("Matrix Class", matrix_stress_test),
        ("MachAr", machar_stress_test),
        ("Linear Algebra", linalg_stress_test),
        ("FFT Operations", fft_stress_test),
        ("Random Numbers", random_stress_test),
        ("Masked Arrays", masked_array_stress_test),
        ("Broadcasting", broadcasting_stress_test),
        ("Ufunc Operations", ufunc_stress_test),
        ("Edge Cases", edge_case_stress_test),
    ]

    for name, test_func in tests:
        try:
            result = test_func()
            print(f"[PASS] {name}")
        except Exception as e:
            print(f"[FAIL] {name}: {e}")

    # Run simulation
    print("\n" + "=" * 50)
    print("Running Scientific Simulation...")
    try:
        sim = ScientificSimulation(n_particles=10)
        result = sim.run(100)
        print(f"[PASS] Scientific Simulation - {result['active_count']} particles active")
    except Exception as e:
        print(f"[FAIL] Scientific Simulation: {e}")

    print("\n" + "=" * 50)
    print("Stress test complete!")


if __name__ == "__main__":
    main()
