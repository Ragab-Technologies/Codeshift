"""
Stress Test: Complex Pandas 1.x -> 2.x Migration Scenarios

This file contains extensive usage of deprecated Pandas 1.x patterns
that need to be migrated to Pandas 2.x compatible code.

DEPRECATED PATTERNS TESTED:
- DataFrame.append() -> pd.concat()
- Series/DataFrame.iteritems() -> items()
- inplace=True patterns (still work but discouraged)
- .values -> .to_numpy()
- Index.is_monotonic -> is_monotonic_increasing
- MultiIndex operations
- Groupby with apply and transform
- Pivot tables and melting
- Rolling windows and expanding
- Merge, join, concat operations
- read_csv, read_excel deprecated params
- Styler operations
- Sparse accessor usage
- Datetime accessor deprecated methods
"""

from datetime import datetime

import numpy as np
import pandas as pd

# =============================================================================
# SECTION 1: DataFrame.append() - DEPRECATED in 2.0
# =============================================================================

def build_dataframe_with_append():
    """Build a DataFrame using the deprecated append method."""
    df = pd.DataFrame({'A': [1, 2], 'B': [3, 4]})

    # Simple append - DEPRECATED
    df = pd.concat([df, {'A': 5, 'B': 6}], ignore_index=True)

    # Append another DataFrame - DEPRECATED
    df2 = pd.DataFrame({'A': [7, 8], 'B': [9, 10]})
    df = pd.concat([df, df2], ignore_index=True)

    # Append multiple DataFrames in a loop - DEPRECATED
    for i in range(5):
        new_row = pd.DataFrame({'A': [i * 10], 'B': [i * 20]})
        df = pd.concat([df, new_row], ignore_index=True)

    # Append with sort parameter - DEPRECATED
    df3 = pd.DataFrame({'B': [100], 'A': [200]})
    df = pd.concat([df, df3], ignore_index=True)

    return df


def accumulate_results_with_append():
    """Accumulate results using deprecated append pattern."""
    results = pd.DataFrame(columns=['name', 'score', 'timestamp'])

    names = ['Alice', 'Bob', 'Charlie', 'Diana', 'Eve']
    for name in names:
        row = pd.DataFrame({
            'name': [name],
            'score': [np.random.randint(0, 100)],
            'timestamp': [datetime.now()]
        })
        results = pd.concat([results, row], ignore_index=True)

    return results


def chain_append_operations():
    """Chain multiple append operations - heavily deprecated pattern."""
    base = pd.DataFrame({'x': [], 'y': [], 'z': []})

    # Chain appends - very inefficient and deprecated
    result = pd.concat([pd.concat([pd.concat([pd.concat([base, {'x': 1, 'y': 2, 'z': 3}], ignore_index=True), {'x': 4, 'y': 5, 'z': 6}], ignore_index=True), {'x': 7, 'y': 8, 'z': 9}], ignore_index=True), pd.DataFrame({'x': [10], 'y': [11], 'z': [12]})], ignore_index=True)

    return result


# =============================================================================
# SECTION 2: iteritems() - DEPRECATED in 2.0, removed in 2.0
# =============================================================================

def iterate_series_columns():
    """Iterate over DataFrame columns using deprecated iteritems."""
    df = pd.DataFrame({
        'col1': [1, 2, 3, 4, 5],
        'col2': ['a', 'b', 'c', 'd', 'e'],
        'col3': [1.1, 2.2, 3.3, 4.4, 5.5]
    })

    column_stats = {}

    # iteritems() is DEPRECATED - should use items()
    for col_name, col_data in df.items():
        if col_data.dtype in ['int64', 'float64']:
            column_stats[col_name] = {
                'mean': col_data.mean(),
                'std': col_data.std(),
                'min': col_data.min(),
                'max': col_data.max()
            }

    return column_stats


def iterate_series_items():
    """Iterate over Series using deprecated iteritems."""
    series = pd.Series({'a': 100, 'b': 200, 'c': 300, 'd': 400})

    # iteritems() on Series is DEPRECATED
    result = {}
    for key, value in series.items():
        result[key] = value * 2

    return result


def process_dataframe_columns_iteritems():
    """Complex processing using iteritems."""
    df = pd.DataFrame(np.random.randn(100, 5), columns=['A', 'B', 'C', 'D', 'E'])

    transformations = {}

    # Nested iteritems usage - DEPRECATED
    for col_name, col_series in df.items():
        inner_stats = {}
        for idx, val in col_series.items():
            if idx < 10:
                inner_stats[idx] = val ** 2
        transformations[col_name] = inner_stats

    return transformations


# =============================================================================
# SECTION 3: .values vs .to_numpy() - .values is soft-deprecated
# =============================================================================

def extract_arrays_with_values():
    """Extract numpy arrays using deprecated .values attribute."""
    df = pd.DataFrame({
        'integers': [1, 2, 3, 4, 5],
        'floats': [1.1, 2.2, 3.3, 4.4, 5.5],
        'strings': ['a', 'b', 'c', 'd', 'e']
    })

    # .values is soft-deprecated, use .to_numpy()
    int_array = df['integers'].values
    float_array = df['floats'].values
    all_values = df.values

    # Operations on values
    result = int_array + float_array

    # Using values for matrix operations
    matrix = df[['integers', 'floats']].values
    transposed = matrix.T

    return result, transposed


def values_in_calculations():
    """Use .values in various calculations."""
    series = pd.Series([10, 20, 30, 40, 50])

    # Multiple uses of .values - should be .to_numpy()
    arr = series.values
    squared = series.values ** 2
    mean_val = series.values.mean()

    # Combining with numpy operations
    result = np.dot(series.values, series.values)

    return arr, squared, mean_val, result


def values_type_coercion():
    """Test .values with type coercion scenarios."""
    # DatetimeIndex values
    dates = pd.date_range('2020-01-01', periods=10)
    date_values = dates.values  # Should use to_numpy()

    # Categorical values
    cat_series = pd.Categorical(['a', 'b', 'c', 'a', 'b'])
    cat_values = pd.Series(cat_series).values  # Should use to_numpy()

    # Sparse array values
    sparse_series = pd.arrays.SparseArray([0, 0, 1, 0, 2, 0, 0, 3])
    sparse_values = pd.Series(sparse_series).values

    return date_values, cat_values, sparse_values


# =============================================================================
# SECTION 4: Index operations - is_monotonic deprecated
# =============================================================================

def check_index_monotonicity():
    """Check index monotonicity using deprecated attributes."""
    df = pd.DataFrame({'value': [1, 2, 3, 4, 5]}, index=[1, 2, 3, 4, 5])

    # is_monotonic is DEPRECATED - use is_monotonic_increasing
    is_mono = df.index.is_monotonic_increasing

    # Also check on a non-monotonic index
    df2 = pd.DataFrame({'value': [1, 2, 3]}, index=[3, 1, 2])
    is_mono2 = df2.index.is_monotonic_increasing

    # Series index check
    series = pd.Series([10, 20, 30], index=['a', 'b', 'c'])
    is_mono_series = series.index.is_monotonic_increasing

    return is_mono, is_mono2, is_mono_series


def index_operations_deprecated():
    """Various deprecated index operations."""
    idx = pd.Index([1, 2, 3, 4, 5])

    # is_monotonic deprecated
    mono = idx.is_monotonic_increasing

    # Create DatetimeIndex
    date_idx = pd.DatetimeIndex(['2020-01-01', '2020-01-02', '2020-01-03'])
    date_mono = date_idx.is_monotonic_increasing

    # RangeIndex monotonicity
    range_idx = pd.RangeIndex(start=0, stop=10, step=2)
    range_mono = range_idx.is_monotonic_increasing

    return mono, date_mono, range_mono


# =============================================================================
# SECTION 5: MultiIndex operations
# =============================================================================

def create_and_manipulate_multiindex():
    """Create and manipulate MultiIndex DataFrames."""
    arrays = [
        ['bar', 'bar', 'baz', 'baz', 'foo', 'foo'],
        ['one', 'two', 'one', 'two', 'one', 'two']
    ]
    tuples = list(zip(*arrays))
    index = pd.MultiIndex.from_tuples(tuples, names=['first', 'second'])

    df = pd.DataFrame(np.random.randn(6, 3), index=index, columns=['A', 'B', 'C'])

    # Check monotonicity - DEPRECATED
    is_mono = df.index.is_monotonic_increasing

    # Various MultiIndex operations
    level_values = df.index.get_level_values(0).values  # .values deprecated

    # Iterating with iteritems - DEPRECATED
    stats = {}
    for col_name, col_data in df.items():
        stats[col_name] = col_data.values.mean()  # .values deprecated

    return df, is_mono, stats


def multiindex_append_operations():
    """Append operations with MultiIndex DataFrames."""
    idx1 = pd.MultiIndex.from_product([['A', 'B'], [1, 2]])
    df1 = pd.DataFrame({'val': [1, 2, 3, 4]}, index=idx1)

    idx2 = pd.MultiIndex.from_product([['C'], [1, 2]])
    df2 = pd.DataFrame({'val': [5, 6]}, index=idx2)

    # Append with MultiIndex - DEPRECATED
    result = pd.concat([df1, df2])

    # Check resulting index
    mono = result.index.is_monotonic_increasing  # DEPRECATED

    return result, mono


# =============================================================================
# SECTION 6: Groupby with apply and transform
# =============================================================================

def groupby_operations():
    """Complex groupby operations."""
    df = pd.DataFrame({
        'group': ['A', 'A', 'B', 'B', 'C', 'C'] * 10,
        'subgroup': ['x', 'y'] * 30,
        'value1': np.random.randn(60),
        'value2': np.random.randn(60)
    })

    # Groupby with iteritems - DEPRECATED pattern
    grouped = df.groupby('group')
    group_stats = {}
    for name, group in grouped:
        for col_name, col_data in group.items():
            if col_name not in ['group', 'subgroup']:
                key = f"{name}_{col_name}"
                group_stats[key] = col_data.values.mean()  # .values deprecated

    # Groupby apply with values
    def custom_agg(x):
        return pd.Series({
            'mean': x['value1'].values.mean(),  # .values deprecated
            'std': x['value2'].values.std()     # .values deprecated
        })

    agg_result = grouped.apply(custom_agg)

    return group_stats, agg_result


def groupby_transform_operations():
    """Groupby transform with deprecated patterns."""
    df = pd.DataFrame({
        'category': ['A', 'A', 'B', 'B', 'A', 'B'] * 5,
        'value': np.random.randn(30)
    })

    # Transform operation
    df['normalized'] = df.groupby('category')['value'].transform(
        lambda x: (x - x.values.mean()) / x.values.std()  # .values deprecated
    )

    # Multiple transforms with append - DEPRECATED
    results = pd.DataFrame()
    for cat in df['category'].unique():
        subset = df[df['category'] == cat].copy()
        subset['rank'] = subset['value'].rank()
        results = pd.concat([results, subset], ignore_index=True)  # DEPRECATED

    return results


# =============================================================================
# SECTION 7: Pivot tables and melting
# =============================================================================

def pivot_operations():
    """Pivot table operations with deprecated patterns."""
    df = pd.DataFrame({
        'date': pd.date_range('2020-01-01', periods=20),
        'category': ['A', 'B'] * 10,
        'subcategory': ['x', 'x', 'y', 'y'] * 5,
        'value': np.random.randn(20)
    })

    # Create pivot table
    pivot = df.pivot_table(
        values='value',
        index='date',
        columns=['category', 'subcategory'],
        aggfunc='mean'
    )

    # Check monotonicity of pivot index - DEPRECATED
    is_mono = pivot.index.is_monotonic_increasing

    # Iterate over pivot columns - DEPRECATED
    col_means = {}
    for col_name, col_data in pivot.items():
        col_means[col_name] = col_data.values.mean()  # .values deprecated

    return pivot, col_means


def melt_and_reshape():
    """Melt and reshape operations."""
    df = pd.DataFrame({
        'id': [1, 2, 3],
        'var_a': [10, 20, 30],
        'var_b': [40, 50, 60],
        'var_c': [70, 80, 90]
    })

    # Melt operation
    melted = pd.melt(df, id_vars=['id'], value_vars=['var_a', 'var_b', 'var_c'])

    # Accumulate reshaped data with append - DEPRECATED
    final = pd.DataFrame()
    for var in ['var_a', 'var_b', 'var_c']:
        subset = melted[melted['variable'] == var]
        subset = subset.assign(processed=subset['value'].values * 2)  # .values deprecated
        final = pd.concat([final, subset], ignore_index=True)  # DEPRECATED

    return final


# =============================================================================
# SECTION 8: Rolling windows and expanding
# =============================================================================

def rolling_window_operations():
    """Rolling window calculations with deprecated patterns."""
    df = pd.DataFrame({
        'timestamp': pd.date_range('2020-01-01', periods=100, freq='H'),
        'value': np.random.randn(100).cumsum()
    })
    df = df.set_index('timestamp')

    # Rolling calculations
    df['rolling_mean'] = df['value'].rolling(window=10).mean()
    df['rolling_std'] = df['value'].rolling(window=10).std()

    # Check index monotonicity - DEPRECATED
    is_mono = df.index.is_monotonic_increasing

    # Extract values - DEPRECATED
    rolling_values = df['rolling_mean'].values

    # Iterate over rolling results - DEPRECATED
    stats = {}
    for col_name, col_data in df.items():
        stats[col_name] = {
            'min': col_data.values.min(),  # .values deprecated
            'max': col_data.values.max()   # .values deprecated
        }

    return df, stats


def expanding_window_operations():
    """Expanding window operations."""
    series = pd.Series(np.random.randn(50))

    # Expanding calculations
    expanding_mean = series.expanding().mean()
    expanding_std = series.expanding().std()

    # Combine results using append - DEPRECATED
    results = pd.DataFrame()
    results = pd.concat([results, pd.DataFrame({'type': ['mean'] * len(expanding_mean), 'value': expanding_mean.values})], ignore_index=True)
    results = pd.concat([results, pd.DataFrame({'type': ['std'] * len(expanding_std), 'value': expanding_std.values})], ignore_index=True)

    return results


# =============================================================================
# SECTION 9: Merge, join, concat operations
# =============================================================================

def merge_operations():
    """Various merge operations with deprecated patterns."""
    df1 = pd.DataFrame({
        'key': ['A', 'B', 'C', 'D'],
        'value1': [1, 2, 3, 4]
    })

    df2 = pd.DataFrame({
        'key': ['B', 'C', 'D', 'E'],
        'value2': [5, 6, 7, 8]
    })

    # Standard merge
    merged = pd.merge(df1, df2, on='key', how='outer')

    # Accumulate merge results - DEPRECATED
    all_merges = pd.DataFrame()
    for how in ['inner', 'outer', 'left', 'right']:
        result = pd.merge(df1, df2, on='key', how=how)
        result['merge_type'] = how
        all_merges = pd.concat([all_merges, result], ignore_index=True)  # DEPRECATED

    # Check values - DEPRECATED
    merge_values = merged['value1'].values

    return all_merges


def join_operations():
    """DataFrame join operations."""
    df1 = pd.DataFrame({'A': [1, 2, 3]}, index=['a', 'b', 'c'])
    df2 = pd.DataFrame({'B': [4, 5, 6]}, index=['a', 'b', 'd'])

    # Join operation
    joined = df1.join(df2, how='outer')

    # Check index - DEPRECATED
    is_mono = joined.index.is_monotonic_increasing

    # Iterate - DEPRECATED
    col_info = {}
    for col_name, col_data in joined.items():
        col_info[col_name] = col_data.values  # .values deprecated

    return joined, col_info


def concat_operations():
    """Concatenation operations."""
    dfs = [
        pd.DataFrame({'A': [1, 2], 'B': [3, 4]}),
        pd.DataFrame({'A': [5, 6], 'B': [7, 8]}),
        pd.DataFrame({'A': [9, 10], 'B': [11, 12]})
    ]

    # Standard concat
    concatenated = pd.concat(dfs, ignore_index=True)

    # Build up with append - DEPRECATED (should use concat)
    result = pd.DataFrame(columns=['A', 'B'])
    for df in dfs:
        result = pd.concat([result, df], ignore_index=True)  # DEPRECATED

    return concatenated, result


# =============================================================================
# SECTION 10: read_csv, read_excel with deprecated params
# =============================================================================

def read_csv_deprecated_params():
    """Demonstrate deprecated read_csv parameters."""
    # Note: These would fail at runtime without actual files,
    # but the code patterns show deprecated usage

    # Example of deprecated parameters (would need actual file to run):
    # - squeeze parameter is deprecated
    # - prefix parameter handling changed
    # - error_bad_lines and warn_bad_lines deprecated

    csv_options_deprecated = {
        'squeeze': True,  # DEPRECATED in 1.4, removed in 2.0
        'error_bad_lines': False,  # DEPRECATED
        'warn_bad_lines': True,  # DEPRECATED
    }

    # New way would use on_bad_lines parameter
    csv_options_new = {
        'on_bad_lines': 'skip'  # New in 1.3+
    }

    return csv_options_deprecated, csv_options_new


def read_excel_deprecated_patterns():
    """Demonstrate deprecated read_excel patterns."""
    # Deprecated parameters that changed in 2.0
    excel_options_deprecated = {
        'squeeze': True,  # DEPRECATED
        'convert_float': True,  # DEPRECATED behavior changed
    }

    return excel_options_deprecated


# =============================================================================
# SECTION 11: Styler operations
# =============================================================================

def styler_operations():
    """Styler operations with various patterns."""
    df = pd.DataFrame({
        'A': [1, 2, 3, 4, 5],
        'B': [10, 20, 30, 40, 50],
        'C': [-1, -2, 3, 4, -5]
    })

    # Create styler
    styled = df.style

    # Apply styling functions
    styled = styled.highlight_max(axis=0)
    styled = styled.highlight_min(axis=0)

    # Format values
    styled = styled.format('{:.2f}')

    # Background gradient
    styled = styled.background_gradient(cmap='viridis')

    # Get underlying values - pattern that might change
    for col_name, col_data in df.items():  # DEPRECATED
        print(f"Column {col_name}: mean = {col_data.values.mean()}")  # .values deprecated

    return styled


def styler_with_subsets():
    """Styler with subset operations."""
    df = pd.DataFrame(
        np.random.randn(10, 5),
        columns=['A', 'B', 'C', 'D', 'E']
    )

    # Various styling operations
    styled = (df.style
        .highlight_max(subset=['A', 'B'])
        .highlight_min(subset=['C', 'D'])
        .format('{:.3f}', subset=['E']))

    # Accessing values through iteration - DEPRECATED patterns
    subset_stats = {}
    for col, data in df[['A', 'B']].items():  # DEPRECATED
        subset_stats[col] = data.values.tolist()  # .values deprecated

    return styled, subset_stats


# =============================================================================
# SECTION 12: Sparse accessor usage
# =============================================================================

def sparse_array_operations():
    """Sparse array and accessor operations."""
    # Create sparse data
    sparse_data = pd.arrays.SparseArray([0, 0, 1, 0, 2, 0, 0, 3, 0, 0])
    series = pd.Series(sparse_data)

    # Access sparse properties
    fill_value = series.sparse.fill_value
    density = series.sparse.density

    # Get values - behavior might differ
    values = series.values  # .values deprecated

    # Convert to dense
    dense = series.sparse.to_dense()
    dense_values = dense.values  # .values deprecated

    return {
        'fill_value': fill_value,
        'density': density,
        'values': values,
        'dense_values': dense_values
    }


def sparse_dataframe_operations():
    """Sparse DataFrame operations."""
    df = pd.DataFrame({
        'A': pd.arrays.SparseArray([0, 1, 0, 0, 2]),
        'B': pd.arrays.SparseArray([0, 0, 3, 0, 0]),
        'C': [1, 2, 3, 4, 5]  # Regular column
    })

    # Iterate over columns - DEPRECATED
    sparse_info = {}
    for col_name, col_data in df.items():
        if hasattr(col_data, 'sparse'):
            sparse_info[col_name] = {
                'density': col_data.sparse.density,
                'values': col_data.values.tolist()  # .values deprecated
            }

    return sparse_info


# =============================================================================
# SECTION 13: Datetime accessor deprecated methods
# =============================================================================

def datetime_operations():
    """Datetime operations with deprecated patterns."""
    dates = pd.date_range('2020-01-01', periods=100, freq='D')
    df = pd.DataFrame({
        'date': dates,
        'value': np.random.randn(100)
    })

    # Extract datetime components
    df['year'] = df['date'].dt.year
    df['month'] = df['date'].dt.month
    df['day'] = df['date'].dt.day

    # Check date index monotonicity - DEPRECATED when set as index
    df_indexed = df.set_index('date')
    is_mono = df_indexed.index.is_monotonic_increasing  # DEPRECATED

    # Get values - DEPRECATED
    date_values = df['date'].values

    # Iterate - DEPRECATED
    for col_name, col_data in df.items():
        if col_name == 'date':
            continue
        print(f"{col_name}: {col_data.values.mean()}")  # .values deprecated

    return df_indexed, is_mono


def timedelta_operations():
    """Timedelta operations."""
    timedeltas = pd.to_timedelta(['1 day', '2 days', '3 days', '4 days', '5 days'])
    series = pd.Series(timedeltas)

    # Access components
    days = series.dt.days

    # Get values - DEPRECATED
    td_values = series.values
    day_values = days.values

    # Create DataFrame and iterate - DEPRECATED
    df = pd.DataFrame({'td': timedeltas, 'days': days})
    for col_name, col_data in df.items():
        print(f"{col_name}: {col_data.values}")  # .values deprecated

    return df


def period_operations():
    """Period operations."""
    periods = pd.period_range('2020-01', periods=12, freq='M')
    df = pd.DataFrame({
        'period': periods,
        'value': np.random.randn(12)
    })

    # Set period as index and check monotonicity - DEPRECATED
    df_indexed = df.set_index('period')
    is_mono = df_indexed.index.is_monotonic_increasing  # DEPRECATED

    # Extract values - DEPRECATED
    period_values = df['period'].values

    return df_indexed, is_mono, period_values


# =============================================================================
# SECTION 14: Complex real-world scenario combining multiple patterns
# =============================================================================

def complex_data_pipeline():
    """
    Complex data pipeline combining multiple deprecated patterns.
    This simulates a real-world data processing scenario.
    """
    # Generate sample data
    np.random.seed(42)
    n_records = 1000

    # Create base DataFrame
    df = pd.DataFrame({
        'timestamp': pd.date_range('2020-01-01', periods=n_records, freq='H'),
        'category': np.random.choice(['A', 'B', 'C', 'D'], n_records),
        'subcategory': np.random.choice(['x', 'y', 'z'], n_records),
        'metric1': np.random.randn(n_records),
        'metric2': np.random.randn(n_records) * 100,
        'metric3': np.random.exponential(10, n_records)
    })

    # Step 1: Set index and check monotonicity - DEPRECATED
    df = df.set_index('timestamp')
    print(f"Index is monotonic: {df.index.is_monotonic_increasing}")  # DEPRECATED

    # Step 2: Accumulate processed data using append - DEPRECATED
    processed = pd.DataFrame()

    for category in df['category'].unique():
        subset = df[df['category'] == category].copy()

        # Calculate rolling statistics
        subset['rolling_mean'] = subset['metric1'].rolling(window=24).mean()
        subset['rolling_std'] = subset['metric1'].rolling(window=24).std()

        # Iterate over columns - DEPRECATED
        for col_name, col_data in subset.items():
            if col_name.startswith('metric'):
                subset[f'{col_name}_normalized'] = (
                    col_data.values - col_data.values.mean()  # .values deprecated
                ) / col_data.values.std()  # .values deprecated

        # Append to results - DEPRECATED
        processed = pd.concat([processed, subset])

    # Step 3: Create summary statistics
    summary = pd.DataFrame()

    grouped = processed.groupby('category')
    for name, group in grouped:
        stats = {}
        for col_name, col_data in group.items():  # DEPRECATED
            if col_data.dtype in ['float64', 'int64']:
                stats[f'{col_name}_mean'] = col_data.values.mean()  # .values deprecated
                stats[f'{col_name}_std'] = col_data.values.std()   # .values deprecated

        stats_df = pd.DataFrame([stats])
        stats_df['category'] = name
        summary = pd.concat([summary, stats_df], ignore_index=True)  # DEPRECATED

    # Step 4: Create pivot table and analyze
    pivot = processed.reset_index().pivot_table(
        values='metric1',
        index='timestamp',
        columns='category',
        aggfunc='mean'
    )

    # Check pivot monotonicity - DEPRECATED
    print(f"Pivot index is monotonic: {pivot.index.is_monotonic_increasing}")  # DEPRECATED

    # Extract pivot values - DEPRECATED
    pivot_values = pivot.values

    # Step 5: Final aggregation with iteration - DEPRECATED
    final_stats = {}
    for col_name, col_data in pivot.items():  # DEPRECATED
        final_stats[col_name] = {
            'mean': col_data.values.mean(),  # .values deprecated
            'std': col_data.values.std(),    # .values deprecated
            'min': col_data.values.min(),    # .values deprecated
            'max': col_data.values.max()     # .values deprecated
        }

    return processed, summary, pivot, final_stats


def time_series_analysis_pipeline():
    """
    Time series analysis pipeline with multiple deprecated patterns.
    """
    # Create time series data
    dates = pd.date_range('2020-01-01', periods=365, freq='D')
    ts = pd.DataFrame({
        'date': dates,
        'value': np.sin(np.linspace(0, 4 * np.pi, 365)) * 100 + np.random.randn(365) * 10
    })
    ts = ts.set_index('date')

    # Check monotonicity - DEPRECATED
    print(f"Time series is monotonic: {ts.index.is_monotonic_increasing}")

    # Calculate various statistics
    ts['ma_7'] = ts['value'].rolling(7).mean()
    ts['ma_30'] = ts['value'].rolling(30).mean()
    ts['expanding_mean'] = ts['value'].expanding().mean()
    ts['expanding_std'] = ts['value'].expanding().std()

    # Monthly aggregation with append - DEPRECATED
    monthly = pd.DataFrame()
    for month in range(1, 13):
        month_data = ts[ts.index.month == month]
        month_stats = pd.DataFrame({
            'month': [month],
            'mean': [month_data['value'].values.mean()],  # .values deprecated
            'std': [month_data['value'].values.std()],    # .values deprecated
            'min': [month_data['value'].values.min()],    # .values deprecated
            'max': [month_data['value'].values.max()]     # .values deprecated
        })
        monthly = pd.concat([monthly, month_stats], ignore_index=True)  # DEPRECATED

    # Extract all values - DEPRECATED
    all_values = {}
    for col_name, col_data in ts.items():  # DEPRECATED
        all_values[col_name] = col_data.values  # .values deprecated

    return ts, monthly, all_values


# =============================================================================
# SECTION 15: Additional edge cases and patterns
# =============================================================================

def categorical_operations():
    """Categorical data operations with deprecated patterns."""
    df = pd.DataFrame({
        'category': pd.Categorical(['a', 'b', 'c', 'a', 'b', 'c']),
        'value': [1, 2, 3, 4, 5, 6]
    })

    # Access categorical values - DEPRECATED
    cat_values = df['category'].values

    # Iterate - DEPRECATED
    for col_name, col_data in df.items():
        print(f"{col_name}: {type(col_data.values)}")  # .values deprecated

    return df


def nullable_integer_operations():
    """Nullable integer operations."""
    series = pd.Series([1, 2, None, 4, 5], dtype=pd.Int64Dtype())

    # Get values - DEPRECATED
    values = series.values

    # Check for NA
    has_na = series.isna().any()

    # Append to DataFrame - DEPRECATED
    df = pd.DataFrame()
    df = pd.concat([df, {'val': series.sum()}], ignore_index=True)  # DEPRECATED

    return series, df


def string_dtype_operations():
    """String dtype operations."""
    series = pd.Series(['hello', 'world', None, 'pandas'], dtype=pd.StringDtype())

    # Get values - DEPRECATED
    values = series.values

    # String operations
    upper = series.str.upper()
    upper_values = upper.values  # .values deprecated

    # Iterate - DEPRECATED
    for idx, val in series.items():  # DEPRECATED
        print(f"Index {idx}: {val}")

    return series, upper


def boolean_dtype_operations():
    """Boolean dtype operations."""
    series = pd.Series([True, False, None, True], dtype=pd.BooleanDtype())

    # Get values - DEPRECATED
    values = series.values

    # Operations
    inverted = ~series
    inverted_values = inverted.values  # .values deprecated

    return series, values, inverted_values


# =============================================================================
# MAIN: Run all tests
# =============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("PANDAS 1.x -> 2.x MIGRATION STRESS TEST")
    print("=" * 80)

    print("\n--- Section 1: DataFrame.append() ---")
    try:
        result = build_dataframe_with_append()
        print(f"build_dataframe_with_append: SUCCESS - {len(result)} rows")
    except Exception as e:
        print(f"build_dataframe_with_append: FAILED - {e}")

    try:
        result = accumulate_results_with_append()
        print(f"accumulate_results_with_append: SUCCESS - {len(result)} rows")
    except Exception as e:
        print(f"accumulate_results_with_append: FAILED - {e}")

    try:
        result = chain_append_operations()
        print(f"chain_append_operations: SUCCESS - {len(result)} rows")
    except Exception as e:
        print(f"chain_append_operations: FAILED - {e}")

    print("\n--- Section 2: iteritems() ---")
    try:
        result = iterate_series_columns()
        print(f"iterate_series_columns: SUCCESS - {len(result)} columns analyzed")
    except Exception as e:
        print(f"iterate_series_columns: FAILED - {e}")

    try:
        result = iterate_series_items()
        print(f"iterate_series_items: SUCCESS - {len(result)} items")
    except Exception as e:
        print(f"iterate_series_items: FAILED - {e}")

    try:
        result = process_dataframe_columns_iteritems()
        print("process_dataframe_columns_iteritems: SUCCESS")
    except Exception as e:
        print(f"process_dataframe_columns_iteritems: FAILED - {e}")

    print("\n--- Section 3: .values vs .to_numpy() ---")
    try:
        result, transposed = extract_arrays_with_values()
        print("extract_arrays_with_values: SUCCESS")
    except Exception as e:
        print(f"extract_arrays_with_values: FAILED - {e}")

    try:
        result = values_in_calculations()
        print("values_in_calculations: SUCCESS")
    except Exception as e:
        print(f"values_in_calculations: FAILED - {e}")

    print("\n--- Section 4: Index operations ---")
    try:
        result = check_index_monotonicity()
        print("check_index_monotonicity: SUCCESS")
    except Exception as e:
        print(f"check_index_monotonicity: FAILED - {e}")

    try:
        result = index_operations_deprecated()
        print("index_operations_deprecated: SUCCESS")
    except Exception as e:
        print(f"index_operations_deprecated: FAILED - {e}")

    print("\n--- Section 5: MultiIndex operations ---")
    try:
        df, is_mono, stats = create_and_manipulate_multiindex()
        print("create_and_manipulate_multiindex: SUCCESS")
    except Exception as e:
        print(f"create_and_manipulate_multiindex: FAILED - {e}")

    try:
        result, mono = multiindex_append_operations()
        print("multiindex_append_operations: SUCCESS")
    except Exception as e:
        print(f"multiindex_append_operations: FAILED - {e}")

    print("\n--- Section 6: Groupby operations ---")
    try:
        stats, agg = groupby_operations()
        print("groupby_operations: SUCCESS")
    except Exception as e:
        print(f"groupby_operations: FAILED - {e}")

    try:
        result = groupby_transform_operations()
        print(f"groupby_transform_operations: SUCCESS - {len(result)} rows")
    except Exception as e:
        print(f"groupby_transform_operations: FAILED - {e}")

    print("\n--- Section 7: Pivot and melt ---")
    try:
        pivot, means = pivot_operations()
        print("pivot_operations: SUCCESS")
    except Exception as e:
        print(f"pivot_operations: FAILED - {e}")

    try:
        result = melt_and_reshape()
        print(f"melt_and_reshape: SUCCESS - {len(result)} rows")
    except Exception as e:
        print(f"melt_and_reshape: FAILED - {e}")

    print("\n--- Section 8: Rolling and expanding ---")
    try:
        df, stats = rolling_window_operations()
        print("rolling_window_operations: SUCCESS")
    except Exception as e:
        print(f"rolling_window_operations: FAILED - {e}")

    try:
        result = expanding_window_operations()
        print(f"expanding_window_operations: SUCCESS - {len(result)} rows")
    except Exception as e:
        print(f"expanding_window_operations: FAILED - {e}")

    print("\n--- Section 9: Merge, join, concat ---")
    try:
        result = merge_operations()
        print(f"merge_operations: SUCCESS - {len(result)} rows")
    except Exception as e:
        print(f"merge_operations: FAILED - {e}")

    try:
        joined, info = join_operations()
        print("join_operations: SUCCESS")
    except Exception as e:
        print(f"join_operations: FAILED - {e}")

    try:
        concat1, concat2 = concat_operations()
        print("concat_operations: SUCCESS")
    except Exception as e:
        print(f"concat_operations: FAILED - {e}")

    print("\n--- Section 11: Styler operations ---")
    try:
        styled = styler_operations()
        print("styler_operations: SUCCESS")
    except Exception as e:
        print(f"styler_operations: FAILED - {e}")

    print("\n--- Section 12: Sparse operations ---")
    try:
        result = sparse_array_operations()
        print("sparse_array_operations: SUCCESS")
    except Exception as e:
        print(f"sparse_array_operations: FAILED - {e}")

    try:
        result = sparse_dataframe_operations()
        print("sparse_dataframe_operations: SUCCESS")
    except Exception as e:
        print(f"sparse_dataframe_operations: FAILED - {e}")

    print("\n--- Section 13: Datetime operations ---")
    try:
        df, is_mono = datetime_operations()
        print("datetime_operations: SUCCESS")
    except Exception as e:
        print(f"datetime_operations: FAILED - {e}")

    try:
        df = timedelta_operations()
        print("timedelta_operations: SUCCESS")
    except Exception as e:
        print(f"timedelta_operations: FAILED - {e}")

    try:
        df, is_mono, values = period_operations()
        print("period_operations: SUCCESS")
    except Exception as e:
        print(f"period_operations: FAILED - {e}")

    print("\n--- Section 14: Complex pipelines ---")
    try:
        processed, summary, pivot, stats = complex_data_pipeline()
        print(f"complex_data_pipeline: SUCCESS - {len(processed)} processed rows")
    except Exception as e:
        print(f"complex_data_pipeline: FAILED - {e}")

    try:
        ts, monthly, values = time_series_analysis_pipeline()
        print("time_series_analysis_pipeline: SUCCESS")
    except Exception as e:
        print(f"time_series_analysis_pipeline: FAILED - {e}")

    print("\n--- Section 15: Additional edge cases ---")
    try:
        df = categorical_operations()
        print("categorical_operations: SUCCESS")
    except Exception as e:
        print(f"categorical_operations: FAILED - {e}")

    try:
        series, df = nullable_integer_operations()
        print("nullable_integer_operations: SUCCESS")
    except Exception as e:
        print(f"nullable_integer_operations: FAILED - {e}")

    try:
        series, upper = string_dtype_operations()
        print("string_dtype_operations: SUCCESS")
    except Exception as e:
        print(f"string_dtype_operations: FAILED - {e}")

    try:
        series, values, inverted = boolean_dtype_operations()
        print("boolean_dtype_operations: SUCCESS")
    except Exception as e:
        print(f"boolean_dtype_operations: FAILED - {e}")

    print("\n" + "=" * 80)
    print("STRESS TEST COMPLETE")
    print("=" * 80)
