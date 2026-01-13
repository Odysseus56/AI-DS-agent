"""
LLM Client for AI Data Scientist Agent.

This module provides LLM integration for dataset summarization.
The main agent logic is in react_agent.py.
"""
import os
from openai import OpenAI
import streamlit as st
from config import MODEL_FAST

# Initialize OpenAI client with API key
# Try Streamlit secrets first (for cloud deployment), fall back to environment variable (for local dev)
try:
    api_key = st.secrets["OPENAI_API_KEY"]
except (KeyError, FileNotFoundError):
    api_key = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=api_key)


def get_data_summary_from_llm(data_context: str, max_tokens: int = 2000) -> str:
    """
    Send data summary to LLM and get a concise, business-friendly summary.
    Used during dataset upload to provide user-friendly insights.
    
    Args:
        data_context: The technical data summary from data_analyzer
        max_tokens: Maximum tokens for the response (cost control)
    
    Returns:
        str: LLM's summary of the data in plain English
    """
    system_prompt = """You are a data scientist assistant helping business teams understand their data.
Your job is to:
1. Analyze the provided dataset summary
2. Identify key insights, patterns, and data quality issues
3. Explain findings in clear, non-technical language suitable for business stakeholders
4. Highlight any concerns or opportunities in the data

Format your response with clear headers and bullet points for easy scanning. Be concise and actionable."""

    user_prompt = f"""Here is a summary of a dataset that was just uploaded:

{data_context}

Please provide an executive summary of this dataset using the following structure:

**📊 Dataset Overview:**
- Brief description of what the data contains
- Key dimensions (rows, columns, time period if applicable)

**🔍 Key Insights:**
- Notable patterns or trends
- Important metrics or statistics

**⚠️ Data Quality:**
- Missing values or completeness issues
- Any data quality concerns

**💡 Opportunities:**
- Potential use cases or analyses
- Recommendations for next steps

Use bullet points and keep each point concise (1-2 sentences max)."""

    try:
        response = client.chat.completions.create(
            model=MODEL_FAST,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=max_tokens,
            temperature=0.7
        )
        
        return response.choices[0].message.content
    
    except Exception as e:
        return f"Error communicating with LLM: {str(e)}"
