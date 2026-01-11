"""
Data analysis utilities for generating dataset summaries and statistics.

This module provides functions to create both verbose and concise summaries
of pandas DataFrames for LLM consumption and UI display.
"""
import pandas as pd
import numpy as np
from config import SAMPLE_ROWS_COUNT


def generate_data_summary(df: pd.DataFrame) -> str:
    """
    Generate a comprehensive but concise summary of the dataset.
    
    This function creates a detailed text-based report that will be sent to the LLM.
    The LLM uses this context to understand the data and answer questions about it.
    
    Returns a formatted string suitable for LLM consumption.
    """
    # List to collect all parts of the summary (will be joined at the end)
    summary_parts = []
    
    # ==== SECTION 1: Basic Dataset Dimensions ====
    summary_parts.append(f"Dataset Shape: {df.shape[0]} rows × {df.shape[1]} columns\n")
    
    # ==== SECTION 2: Detailed Column Information ====
    summary_parts.append("Column Information:")
    for col in df.columns:
        # Get data type for this column
        dtype = df[col].dtype
        
        # Calculate missing values (critical for data quality assessment)
        null_count = df[col].isnull().sum()
        null_pct = (null_count / len(df)) * 100
        
        # Start building the column description
        col_info = f"  - {col} ({dtype})"
        
        # If there are missing values, flag them prominently
        if null_count > 0:
            col_info += f" - {null_count} missing ({null_pct:.1f}%)"
        
        # Add type-specific metadata:
        # For numeric columns: show the data range
        if dtype in ['int64', 'float64']:
            col_info += f" - Range: [{df[col].min()}, {df[col].max()}]"
        # For categorical/text columns: show cardinality (uniqueness)
        elif dtype == 'object':
            unique_count = df[col].nunique()
            col_info += f" - {unique_count} unique values"
            
        summary_parts.append(col_info)
    
    # ==== SECTION 3: Statistical Summary ====
    # Use pandas describe() to get mean, std, quartiles, etc.
    # include='all' ensures both numeric and categorical columns are included
    summary_parts.append("\nDescriptive Statistics:")
    desc_stats = df.describe(include='all').to_string()
    summary_parts.append(desc_stats)
    
    # ==== SECTION 4: Sample Data ====
    # Show first N rows so LLM can see actual data format
    summary_parts.append(f"\nFirst {SAMPLE_ROWS_COUNT} Rows:")
    summary_parts.append(df.head(SAMPLE_ROWS_COUNT).to_string())
    
    # ==== SECTION 5: Data Quality Assessment ====
    data_quality_issues = []
    
    # Check for missing values across entire dataset
    total_missing = df.isnull().sum().sum()
    if total_missing > 0:
        data_quality_issues.append(f"Total missing values: {total_missing}")
    
    # Check for duplicate rows (may indicate data collection issues)
    duplicates = df.duplicated().sum()
    if duplicates > 0:
        data_quality_issues.append(f"Duplicate rows: {duplicates}")
    
    # Only add quality issues section if issues were found
    if data_quality_issues:
        summary_parts.append("\nData Quality Issues:")
        for issue in data_quality_issues:
            summary_parts.append(f"  - {issue}")
    
    # Join all parts into a single string with newlines
    return "\n".join(summary_parts)


def generate_concise_summary(df: pd.DataFrame) -> str:
    """
    DEPRECATED: Use generate_compact_summary or generate_detailed_profile instead.
    Generate a concise summary for LLM profiling (no sample data or stats).
    
    This is used by the profiling step to avoid JSON parsing errors from verbose summaries.
    Returns only essential column information without sample data.
    """
    summary_parts = []
    
    summary_parts.append(f"Dataset Shape: {df.shape[0]} rows × {df.shape[1]} columns\n")
    summary_parts.append("Columns:")
    
    for col in df.columns:
        dtype = df[col].dtype
        null_count = df[col].isnull().sum()
        null_pct = (null_count / len(df)) * 100
        
        col_info = f"  - {col} ({dtype})"
        
        if null_count > 0:
            col_info += f" - {null_count} missing ({null_pct:.1f}%)"
        
        if dtype in ['int64', 'float64']:
            col_info += f" - Range: [{df[col].min()}, {df[col].max()}]"
        elif dtype == 'object':
            unique_count = df[col].nunique()
            col_info += f" - {unique_count} unique values"
        
        summary_parts.append(col_info)
    
    return "\n".join(summary_parts)


def generate_compact_summary(df: pd.DataFrame) -> str:
    """
    Generate Summary A: Ultra-compact overview of ALL columns.
    
    Used for large datasets (>30 columns) to give LLM breadth without depth.
    ~10 tokens per column.
    
    Format: column_name (dtype): key_stat, missing%
    """
    summary_parts = []
    summary_parts.append(f"Dataset: {df.shape[0]:,} rows × {df.shape[1]} columns\n")
    summary_parts.append("All Columns (compact):")
    
    for col in df.columns:
        dtype = df[col].dtype
        null_count = df[col].isnull().sum()
        null_pct = (null_count / len(df)) * 100
        
        # Build compact one-liner
        parts = [f"{col} ({dtype})"]
        
        if dtype in ['int64', 'float64', 'int32', 'float32']:
            non_null = df[col].dropna()
            if len(non_null) > 0:
                parts.append(f"unique={non_null.nunique()}")
                parts.append(f"mean={non_null.mean():.1f}")
        elif dtype == 'object':
            parts.append(f"unique={df[col].nunique()}")
            mode_val = df[col].mode()
            if len(mode_val) > 0:
                mode_str = str(mode_val[0])[:20]  # Truncate long strings
                parts.append(f"mode='{mode_str}'")
        
        if null_count > 0:
            parts.append(f"missing={null_pct:.1f}%")
        
        summary_parts.append(f"  {', '.join(parts)}")
    
    return "\n".join(summary_parts)


def generate_detailed_profile(df: pd.DataFrame, columns: list = None, max_sample_values: int = 5) -> str:
    """
    Generate Summary B: Detailed profile for selected columns.
    
    Includes smart sampling, distributions, and data quality indicators.
    ~70 tokens per column.
    
    Args:
        df: DataFrame to profile
        columns: List of columns to profile (if None, profiles all)
        max_sample_values: Number of sample values to include
    
    Returns:
        Detailed profile string
    """
    if columns is None:
        columns = df.columns.tolist()
    
    summary_parts = []
    summary_parts.append(f"Detailed Profile ({len(columns)} columns):\n")
    
    for col in columns:
        if col not in df.columns:
            continue
            
        dtype = df[col].dtype
        null_count = df[col].isnull().sum()
        null_pct = (null_count / len(df)) * 100
        
        col_lines = [f"  • {col} ({dtype})"]
        
        if null_count > 0:
            col_lines.append(f"    - Missing: {null_count:,} ({null_pct:.1f}%)")
        
        if dtype in ['int64', 'float64', 'int32', 'float32']:
            # Numeric profiling with smart sampling
            non_null = df[col].dropna()
            if len(non_null) > 0:
                col_lines.append(f"    - Range: [{non_null.min():.2f}, {non_null.max():.2f}]")
                col_lines.append(f"    - Mean: {non_null.mean():.2f}, Std: {non_null.std():.2f}")
                col_lines.append(f"    - Unique: {non_null.nunique():,}")
                
                # Smart sampling: min, max, + random values
                samples = [non_null.min(), non_null.max()]
                if len(non_null) > 2:
                    n_random = min(max_sample_values - 2, len(non_null) - 2)
                    if n_random > 0:
                        random_samples = non_null.sample(n_random, random_state=42).tolist()
                        samples.extend(random_samples)
                
                sample_str = [f"{x:.2f}" for x in samples[:max_sample_values]]
                col_lines.append(f"    - Sample (min/max/random): [{', '.join(sample_str)}]")
        
        elif dtype == 'object':
            # Categorical profiling with smart sampling
            unique_count = df[col].nunique()
            col_lines.append(f"    - Unique: {unique_count:,}")
            
            # Top values (only if reasonable cardinality)
            if unique_count <= 100:
                top_vals = df[col].value_counts().head(3)
                top_str = ", ".join([f"'{k}' ({v})" for k, v in top_vals.items()])
                col_lines.append(f"    - Top: {top_str}")
            
            # Smart sampling: head, middle, tail, rare
            non_null = df[col].dropna()
            if len(non_null) > 0:
                samples = []
                n = len(non_null)
                
                # Sample from different positions
                samples.append(str(non_null.iloc[0]))
                if n > 1:
                    samples.append(str(non_null.iloc[n // 2]))
                if n > 2:
                    samples.append(str(non_null.iloc[-1]))
                
                # Add rare value if exists
                if unique_count > 3:
                    value_counts = df[col].value_counts()
                    rare_threshold = int(len(value_counts) * 0.8)
                    if rare_threshold < len(value_counts):
                        rare_val = value_counts.iloc[rare_threshold:].index[0]
                        samples.append(str(rare_val))
                
                # Deduplicate and truncate long strings
                samples = list(dict.fromkeys(samples))[:max_sample_values]
                sample_str = ", ".join([f"'{v[:50]}'" for v in samples])
                col_lines.append(f"    - Sample (head/mid/tail/rare): {sample_str}")
        
        summary_parts.append("\n".join(col_lines))
    
    return "\n".join(summary_parts)


def get_basic_stats(df: pd.DataFrame) -> dict:
    """
    Get basic statistics about the dataset as a dictionary.
    
    This is used by the UI (app.py) to display quick metrics in the sidebar.
    Returns a simple dict instead of a formatted string (unlike generate_data_summary).
    
    Useful for displaying in the UI.
    """
    return {
        # Dataset dimensions
        "rows": df.shape[0],
        "columns": df.shape[1],
        
        # Data quality metrics
        "missing_cells": df.isnull().sum().sum(),  # Total count of null values
        "duplicate_rows": df.duplicated().sum(),    # Count of duplicate rows
        
        # Column type breakdown
        "numeric_columns": len(df.select_dtypes(include=[np.number]).columns),
        "categorical_columns": len(df.select_dtypes(include=['object']).columns),
        
        # Memory footprint (helpful for performance monitoring)
        "memory_usage_mb": df.memory_usage(deep=True).sum() / 1024 / 1024
    }


def build_execution_context(datasets: dict) -> dict:
    """
    Build a structured, machine-parseable execution context for code generation.
    
    This provides the LLM with explicit information about:
    - Available datasets and their exact names
    - Dataset structure (columns, types, missing values)
    - Library versions in use
    - Pre-defined variables in the execution environment
    - API compatibility notes (e.g., pandas 2.0+ changes)
    
    Args:
        datasets: Dict of {dataset_name: DataFrame}
    
    Returns:
        dict: Structured execution context with all environment information
    """
    import pandas as pd
    import numpy as np
    
    # Import optional libraries to get versions
    try:
        import sklearn
        sklearn_version = sklearn.__version__
    except ImportError:
        sklearn_version = "not installed"
    
    try:
        import scipy
        scipy_version = scipy.__version__
    except ImportError:
        scipy_version = "not installed"
    
    try:
        import statsmodels
        statsmodels_version = statsmodels.__version__
    except ImportError:
        statsmodels_version = "not installed"
    
    # Extract dataset metadata
    dataset_metadata = {}
    for name, dataset_item in datasets.items():
        # Handle both formats: direct DataFrame or dict with 'df' key (from test_runner)
        if isinstance(dataset_item, dict) and 'df' in dataset_item:
            df = dataset_item['df']
        else:
            df = dataset_item
        
        columns_info = {}
        for col in df.columns:
            col_dtype = str(df[col].dtype)
            missing_count = int(df[col].isnull().sum())
            missing_pct = round(float(missing_count / len(df) * 100), 2) if len(df) > 0 else 0.0
            
            col_info = {
                "dtype": col_dtype,
                "missing_count": missing_count,
                "missing_pct": missing_pct
            }
            
            # Add type-specific metadata
            if df[col].dtype in ['int64', 'float64', 'int32', 'float32']:
                col_info["range"] = [float(df[col].min()), float(df[col].max())] if not df[col].isnull().all() else None
            elif df[col].dtype == 'object':
                col_info["unique_count"] = int(df[col].nunique())
            
            columns_info[col] = col_info
        
        dataset_metadata[name] = {
            "shape": [int(df.shape[0]), int(df.shape[1])],
            "columns": columns_info
        }
    
    return {
        "datasets": {
            "available": list(datasets.keys()),
            "access_pattern": "datasets['dataset_name']",
            "metadata": dataset_metadata
        },
        "environment": {
            "pre_defined_variables": {
                "datasets": f"dict with keys: {list(datasets.keys())}",
                "pd": "pandas module",
                "np": "numpy module",
                "px": "plotly.express module",
                "go": "plotly.graph_objects module",
                "make_subplots": "plotly.subplots.make_subplots function",
                "sklearn": "sklearn module (if available)",
                "scipy": "scipy module (if available)",
                "stats": "scipy.stats module (if scipy available)",
                "sm": "statsmodels.api module (if statsmodels available)",
                "smf": "statsmodels.formula.api module (if statsmodels available)"
            },
            "output_variables": {
                "fig": "Store Plotly figure here for visualizations",
                "result": "Store analysis result here (dict, DataFrame, or scalar)"
            },
            "undefined_variables": [
                "df - NOT pre-defined. You must create it explicitly: df = datasets['dataset_name']"
            ]
        },
        "library_versions": {
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "sklearn": sklearn_version,
            "scipy": scipy_version,
            "statsmodels": statsmodels_version
        },
        "api_notes": {
            "pandas_2.0_changes": [
                "value_counts().reset_index() now creates columns ['original_col', 'count'], NOT ['index', 'count']",
                "Example: df['income_bracket'].value_counts().reset_index() creates columns ['income_bracket', 'count']",
                "When using with plotly: px.bar(df, x='income_bracket', y='count') - use the actual column name, not 'index'"
            ],
            "categorical_encoding": [
                "Before using categorical columns in ML models, encode them using pd.get_dummies() or LabelEncoder",
                "Example: df_encoded = pd.get_dummies(df, columns=['income_bracket', 'credit_score_tier'])"
            ]
        }
    }
