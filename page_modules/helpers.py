"""
Shared Helper Functions for Page Modules

This module contains helper functions used across multiple pages:
- _process_dataset: Shared logic for processing and storing datasets
- load_sample_dataset: Load sample datasets from data/ folder
- handle_file_upload: Process uploaded CSV files
"""

import os
import pandas as pd
import streamlit as st
from datetime import datetime

from data_analyzer import generate_data_summary
from llm_client import get_data_summary_from_llm
from config import (
    MAX_FILE_SIZE_BYTES,
    MAX_DATASET_ROWS,
    ERROR_FILE_TOO_LARGE,
    ERROR_INVALID_CSV,
    ERROR_CSV_INFO,
    WARNING_DATASET_EXISTS,
    WARNING_DATASET_TRUNCATED,
    SUCCESS_FILE_UPLOADED,
    SUCCESS_SAMPLE_LOADED
)


def _process_dataset(df: pd.DataFrame, dataset_id: str, filename: str) -> bool:
    """Shared logic for processing and storing a dataset.
    
    Args:
        df: Loaded pandas DataFrame
        dataset_id: Unique identifier for the dataset
        filename: Display name for the dataset
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Auto-generate summary
    with st.spinner("📊 Analyzing your dataset..."):
        data_summary = generate_data_summary(df)
        llm_summary = get_data_summary_from_llm(data_summary)
        
        # Add dataset to collection
        st.session_state.datasets[dataset_id] = {
            'name': filename,
            'df': df,
            'data_summary': data_summary,
            'uploaded_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Set as active dataset
        st.session_state.active_dataset_id = dataset_id
        
        # Add summary to unified chat if this is the first dataset
        if len(st.session_state.datasets) == 1:
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"**Dataset '{filename}' loaded successfully!**\n\n{llm_summary}",
                "type": "summary",
                "metadata": {"dataset_id": dataset_id}
            })
        else:
            # For additional datasets, add a simpler message
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"**Dataset '{filename}' added!** You can now ask questions about it.\n\n{llm_summary}",
                "type": "summary",
                "metadata": {"dataset_id": dataset_id}
            })
        
        # Log the summary
        st.session_state.logger.log_summary_generation(f"Dataset: {filename}", llm_summary)
    
    return True


def load_sample_dataset(file_path: str, filename: str) -> bool:
    """Load a sample dataset from the data/ folder.
    
    Args:
        file_path: Full path to the CSV file
        filename: Display name for the dataset
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Generate dataset ID from filename
    dataset_id = filename.replace('.csv', '').lower().replace(' ', '_').replace('-', '_')
    
    # Check if dataset already exists
    if dataset_id in st.session_state.datasets:
        st.warning(f"⚠️ Dataset '{filename}' is already loaded.")
        st.session_state.active_dataset_id = dataset_id
        return True
    
    try:
        # Load CSV with row limit to prevent memory issues
        df = pd.read_csv(file_path, nrows=MAX_DATASET_ROWS)
        
        # Warn if file was truncated
        if len(df) == MAX_DATASET_ROWS:
            st.warning(WARNING_DATASET_TRUNCATED)
    except Exception as e:
        st.error(f"❌ Error reading CSV file: {str(e)}")
        st.info("Please ensure the file is a valid CSV format.")
        return False
    
    # Process the dataset using shared logic
    success = _process_dataset(df, dataset_id, filename)
    
    if success:
        st.success(SUCCESS_SAMPLE_LOADED.format(name=filename))
    
    return success


def handle_file_upload(uploaded_file) -> bool:
    """Process uploaded CSV file and add to datasets.
    
    Args:
        uploaded_file: Streamlit UploadedFile object
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Validate file size (100MB limit)
    if uploaded_file.size > MAX_FILE_SIZE_BYTES:
        st.error(ERROR_FILE_TOO_LARGE)
        return False
    
    # Generate dataset ID from filename
    dataset_id = uploaded_file.name.replace('.csv', '').lower().replace(' ', '_').replace('-', '_')
    
    # Check if dataset already exists
    if dataset_id in st.session_state.datasets:
        st.warning(WARNING_DATASET_EXISTS.format(name=uploaded_file.name))
        st.session_state.active_dataset_id = dataset_id
        return True
    
    try:
        # Load CSV with row limit to prevent memory issues
        df = pd.read_csv(uploaded_file, nrows=MAX_DATASET_ROWS)
        
        # Warn if file was truncated
        if len(df) == MAX_DATASET_ROWS:
            st.warning(WARNING_DATASET_TRUNCATED)
    except Exception as e:
        st.error(ERROR_INVALID_CSV.format(error=str(e)))
        st.info(ERROR_CSV_INFO)
        return False
    
    # Process the dataset using shared logic
    success = _process_dataset(df, dataset_id, uploaded_file.name)
    
    if success:
        st.success(SUCCESS_FILE_UPLOADED.format(name=uploaded_file.name))
    
    return success
