import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file (contains OPENAI_API_KEY)
# This must be called before creating the OpenAI client
load_dotenv()

# Initialize OpenAI client with API key from environment variable
# This client is reused across all function calls (efficient connection pooling)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def get_data_summary_from_llm(data_context: str, max_tokens: int = 2000) -> str:
    """
    Send data summary to LLM and get a concise, business-friendly summary.
    
    This is the main "translation" function: it takes technical data analysis
    and converts it into language that non-technical stakeholders can understand.
    
    Args:
        data_context: The technical data summary from data_analyzer
        max_tokens: Maximum tokens for the response (cost control - prevents runaway bills)
    
    Returns:
        str: LLM's summary of the data in plain English
    """
    # ==== SYSTEM PROMPT: Define the LLM's role and behavior ====
    # This is like giving the AI a job description and instructions
    # The system prompt stays consistent across all requests
    system_prompt = """You are a data scientist assistant helping business teams understand their data.
Your job is to:
1. Analyze the provided dataset summary
2. Identify key insights, patterns, and data quality issues
3. Explain findings in clear, non-technical language suitable for business stakeholders
4. Highlight any concerns or opportunities in the data

Be concise but thorough. Focus on actionable insights."""

    # ==== USER PROMPT: The actual request we're making ====
    # This contains the specific data we want analyzed
    # f-string allows us to inject the data_context variable
    user_prompt = f"""Here is a summary of a dataset that was just uploaded:

{data_context}

Please provide a concise paragraph summarizing this dataset for a non-technical business audience. 
Focus on what the data contains, its quality, and any notable patterns or issues."""

    try:
        # ==== MAKE API CALL TO OPENAI ====
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Cost-effective model, good for data analysis
            messages=[
                {"role": "system", "content": system_prompt},  # AI's persona
                {"role": "user", "content": user_prompt}       # Our request
            ],
            max_tokens=max_tokens,  # Limit response length (cost control)
            temperature=0.7  # Controls randomness (0=deterministic, 1=creative)
        )
        
        # Extract the text content from the API response
        return response.choices[0].message.content
    
    except Exception as e:
        # Graceful error handling - return error message instead of crashing
        return f"Error communicating with LLM: {str(e)}"


def ask_question_about_data(question: str, data_context: str, max_tokens: int = 2000) -> str:
    """
    Ask a specific question about the dataset.
    
    This function enables interactive Q&A. Users can ask follow-up questions
    after seeing the initial summary. The LLM has access to the full data context
    so it can answer specific questions about columns, patterns, or issues.
    
    Args:
        question: User's question about the data (e.g., "What's the average age?")
        data_context: The technical data summary (same one used for initial summary)
        max_tokens: Maximum tokens for the response (cost control)
    
    Returns:
        str: LLM's answer to the user's question
    """
    # ==== SYSTEM PROMPT: Define the Q&A assistant's behavior ====
    # Different from the summary prompt - this one focuses on answering questions
    # Key instruction: be honest about limitations (don't make up answers)
    system_prompt = """You are an expert data scientist helping business teams analyze their data.
Answer questions clearly and provide actionable insights.
If the question requires calculations or deeper analysis, explain what analysis would be needed.
Always be honest about limitations of what you can determine from the summary alone."""

    # ==== USER PROMPT: Provide context + user's question ====
    # We send the full data context again so the LLM can reference it
    # This allows the LLM to answer questions like "What's in column X?"
    user_prompt = f"""Dataset Summary:
{data_context}

User Question: {question}

Please provide a clear, helpful answer."""

    try:
        # ==== MAKE API CALL TO OPENAI ====
        # Same pattern as get_data_summary_from_llm, but different prompts
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Same cost-effective model
            messages=[
                {"role": "system", "content": system_prompt},  # Q&A assistant persona
                {"role": "user", "content": user_prompt}       # Context + question
            ],
            max_tokens=max_tokens,  # Limit response length
            temperature=0.7  # Slightly creative but still focused
        )
        
        # Extract and return the answer
        return response.choices[0].message.content
    
    except Exception as e:
        # Graceful error handling - show error instead of crashing
        return f"Error communicating with LLM: {str(e)}"
