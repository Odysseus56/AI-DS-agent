"""
Environment Detection and Configuration Utility

This module provides utilities to detect and configure the operating environment
(local CLI vs Streamlit web UI) and adjust logging behavior accordingly.
"""
import os
from typing import Literal

# Import config constants
from config import (
    DEFAULT_ENVIRONMENT_MODE,
    ENV_ENVIRONMENT_MODE,
    LOG_LOCAL_DIR,
    LOG_CLI_DIR
)


EnvironmentMode = Literal["local", "streamlit"]


def get_environment_mode() -> EnvironmentMode:
    """
    Detect the current operating environment.
    
    Priority:
    1. Environment variable ENVIRONMENT_MODE (manual override)
    2. DEFAULT_ENVIRONMENT_MODE from config.py
    
    Returns:
        "local" for CLI/headless mode or "streamlit" for web UI mode
    """
    mode = os.getenv(ENV_ENVIRONMENT_MODE, DEFAULT_ENVIRONMENT_MODE).lower()
    
    if mode not in ["local", "streamlit"]:
        print(f"⚠️ Invalid ENVIRONMENT_MODE '{mode}', defaulting to '{DEFAULT_ENVIRONMENT_MODE}'")
        mode = DEFAULT_ENVIRONMENT_MODE
    
    return mode


def is_local_environment() -> bool:
    """Check if running in local/CLI environment."""
    return get_environment_mode() == "local"


def is_streamlit_environment() -> bool:
    """Check if running in Streamlit web UI environment."""
    return get_environment_mode() == "streamlit"


def should_save_visualizations() -> bool:
    """
    Determine if visualizations should be saved to logs.
    
    Local environment: YES - saves matplotlib/plotly figures as base64 in markdown logs
    Streamlit environment: NO - causes issues, visualizations shown in UI instead
    
    Returns:
        True if visualizations should be saved to logs, False otherwise
    """
    return is_local_environment()


def should_use_supabase() -> bool:
    """
    Determine if Supabase logging should be enabled.
    
    Local environment: NO - only local file logging
    Streamlit environment: YES - dual logging (local + Supabase)
    
    Can be overridden by ENABLE_SUPABASE_LOGGING environment variable.
    
    Returns:
        True if Supabase should be used, False otherwise
    """
    # Check for explicit override first
    explicit_override = os.getenv("ENABLE_SUPABASE_LOGGING")
    if explicit_override is not None:
        return explicit_override.lower() in ("true", "1", "yes")
    
    # Otherwise use environment-based default
    return is_streamlit_environment()


def get_log_directory() -> str:
    """
    Get the appropriate log directory based on environment.
    
    Local environment: logs/cli/
    Streamlit environment: logs/local/
    
    Returns:
        Path to the log directory
    """
    if is_local_environment():
        return LOG_CLI_DIR
    else:
        return LOG_LOCAL_DIR


def print_environment_info():
    """Print current environment configuration (for debugging)."""
    mode = get_environment_mode()
    print(f"Environment Mode: {mode}")
    print(f"   - Save visualizations to logs: {should_save_visualizations()}")
    print(f"   - Use Supabase logging: {should_use_supabase()}")
    print(f"   - Log directory: {get_log_directory()}")
