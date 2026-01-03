import pandas as pd
import numpy as np


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
    # Show first 5 rows so LLM can see actual data format
    summary_parts.append("\nFirst 5 Rows:")
    summary_parts.append(df.head().to_string())
    
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
