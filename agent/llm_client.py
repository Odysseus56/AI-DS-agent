"""
LLM Client - Centralized OpenAI client initialization.

This module provides a single source of truth for the OpenAI client,
avoiding duplicate initialization code across modules.
"""

import os
from openai import OpenAI

# Lazy initialization - client is created on first use
_client = None


def get_openai_client() -> OpenAI:
    """
    Get the OpenAI client instance.
    
    Uses lazy initialization to create the client on first use.
    Tries Streamlit secrets first, falls back to environment variable.
    
    Returns:
        OpenAI: The initialized OpenAI client
    """
    global _client
    
    if _client is None:
        # Try Streamlit secrets first (for cloud deployment)
        try:
            import streamlit as st
            api_key = st.secrets["OPENAI_API_KEY"]
        except (KeyError, FileNotFoundError, ImportError):
            # Fall back to environment variable (for local dev / CLI)
            api_key = os.getenv("OPENAI_API_KEY")
        
        if not api_key:
            raise ValueError(
                "OpenAI API key not found. Set OPENAI_API_KEY environment variable "
                "or add it to Streamlit secrets."
            )
        
        _client = OpenAI(api_key=api_key)
    
    return _client
