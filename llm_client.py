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


def should_use_code_for_question(question: str, data_context: str) -> bool:
    """
    Evaluate if a question requires code execution to answer accurately.
    
    Args:
        question: User's question
        data_context: Dataset summary for context
    
    Returns:
        bool: True if question requires code execution, False otherwise
    """
    system_prompt = """You are a data analysis assistant. Your job is to determine if a user's question 
requires executing Python code on the dataset to answer accurately.

Questions that REQUIRE CODE:
- Calculations (averages, sums, counts, correlations, etc.)
- Statistical analysis (distributions, outliers, trends)
- Data filtering or aggregation
- Specific values or comparisons from the data
- Pattern detection or anomaly identification

Questions that DON'T require code:
- General data science concepts
- Interpretation of already-provided summary statistics
- Recommendations on analysis approaches
- Questions about methodology

Respond with ONLY 'YES' or 'NO'."""

    user_prompt = f"""Dataset Summary:
{data_context}

User Question: {question}

Does this question require executing Python code on the dataset? Answer YES or NO."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=10,
            temperature=0
        )
        
        answer = response.choices[0].message.content.strip().upper()
        return "YES" in answer
    
    except Exception as e:
        # Default to code execution if evaluation fails
        return True


def generate_analysis_code(question: str, data_context: str, max_tokens: int = 1500) -> str:
    """
    Generate Python code to answer an analytical question about the data.
    
    This is different from visualization code - it focuses on calculations,
    aggregations, and returning text/numeric results rather than plots.
    
    Args:
        question: User's analytical question
        data_context: Dataset summary
        max_tokens: Maximum tokens for response
    
    Returns:
        str: Python code to execute
    """
    system_prompt = """You are an expert data analyst who writes Python code to answer questions about datasets.

Your job is to:
1. Write clean, executable Python code using pandas and numpy
2. Focus on calculations, aggregations, filtering, and analysis
3. Store results in variables that can be printed
4. Use clear variable names for results

IMPORTANT CODE REQUIREMENTS:
- Use the variable 'df' (already available) for the dataframe
- Import statements NOT needed (pandas as pd, numpy as np already imported)
- Store final result in a variable called 'result'
- The result should be a value, string, dataframe, or series that can be printed
- Keep code concise and focused on answering the specific question
- Handle potential errors (missing columns, data types, etc.)

Example for "What's the average age?":
result = df['age'].mean()

Example for "How many customers are from California?":
result = len(df[df['state'] == 'California'])

Example for "Show top 5 products by sales":
result = df.groupby('product')['sales'].sum().sort_values(ascending=False).head(5)

Return ONLY the Python code, no explanations or markdown."""

    user_prompt = f"""Dataset Summary:
{data_context}

User Question: {question}

Generate Python code to answer this question. Store the result in a variable called 'result'."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=max_tokens,
            temperature=0.3
        )
        
        code = response.choices[0].message.content.strip()
        
        # Remove markdown code fences if present
        if code.startswith("```"):
            lines = code.split("\n")
            code = "\n".join(lines[1:-1]) if len(lines) > 2 else code
            code = code.replace("```python", "").replace("```", "").strip()
        
        return code
    
    except Exception as e:
        return f"# Error generating code: {str(e)}"


def format_code_result_as_answer(question: str, code: str, result: str, data_context: str) -> str:
    """
    Take the code execution result and format it as a natural language answer.
    
    Args:
        question: Original user question
        code: The code that was executed
        result: The output from code execution
        data_context: Dataset summary for context
    
    Returns:
        str: Natural language answer
    """
    system_prompt = """You are a data analyst explaining results to business stakeholders.

Your job is to:
1. Take the code execution result and format it as a clear, natural language answer
2. Directly answer the user's question
3. Provide context and interpretation when helpful
4. Keep it concise but informative
5. If the result shows a dataframe or series, format it nicely

Do NOT:
- Show the code unless specifically asked
- Use overly technical jargon
- Make assumptions beyond what the data shows"""

    user_prompt = f"""User Question: {question}

Code Executed:
{code}

Result:
{result}

Please provide a clear, natural language answer to the user's question based on this result."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=1000,
            temperature=0.7
        )
        
        return response.choices[0].message.content
    
    except Exception as e:
        return f"Result: {result}\n\n(Error formatting answer: {str(e)})"


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
    # This is now only used for non-data questions (conceptual, methodological)
    system_prompt = """You are an expert data scientist helping business teams understand data analysis concepts.
Answer questions clearly and provide actionable insights.
Focus on methodology, interpretation, and recommendations.
This is for general questions that don't require specific calculations on the dataset."""

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


def generate_visualization_code(question: str, data_context: str, max_tokens: int = 2000) -> tuple:
    """
    Generate Python code for data visualization based on user question.
    
    This function asks the LLM to write matplotlib/seaborn code to visualize the data.
    Returns both the code and a short explanation of what the visualization shows.
    
    Args:
        question: User's question requesting visualization (e.g., "Show correlation heatmap")
        data_context: The technical data summary
        max_tokens: Maximum tokens for the response
    
    Returns:
        tuple: (code: str, explanation: str) - Python code and text explanation
    """
    # ==== SYSTEM PROMPT: Define the code generation assistant's behavior ====
    system_prompt = """You are an expert data visualization specialist helping business teams visualize their data.

Your job is to:
1. Generate clean, executable Python code using matplotlib and pandas
2. Create professional, publication-quality visualizations
3. Use subplots when multiple related charts are needed
4. Always include proper labels, titles, and legends
5. Provide a brief explanation of what the visualization shows

IMPORTANT CODE REQUIREMENTS:
- Use the variable 'df' (already available) for the dataframe
- Import statements NOT needed (pandas, numpy, matplotlib already imported)
- Always call plt.tight_layout() before showing plots
- Use clear, descriptive titles and axis labels
- For multiple plots, use plt.subplots() to create a figure with multiple subplots

PDF-FRIENDLY VISUALIZATION REQUIREMENTS (unless user specifies otherwise):
- Set figure size to be PDF-compatible: use plt.figure(figsize=(8, 6)) for single plots
- For multiple subplots, use figsize=(10, 8) or similar reasonable dimensions
- Avoid extremely wide or tall figures that won't fit on a standard PDF page
- Use readable font sizes (at least 10pt for labels, 12pt for titles)
- Ensure sufficient spacing between subplots with plt.tight_layout()
- Keep aspect ratios reasonable (avoid extreme width/height ratios)

Return your response in this exact format:
CODE:
[your Python code here]

EXPLANATION:
[1-2 sentence explanation of what the visualization shows and key insights]"""

    # ==== USER PROMPT: Provide context + visualization request ====
    user_prompt = f"""Dataset Summary:
{data_context}

User Request: {question}

Please generate Python code to create the requested visualization and provide a brief explanation."""

    try:
        # ==== MAKE API CALL TO OPENAI ====
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=max_tokens,
            temperature=0.7
        )
        
        # Extract response and parse CODE and EXPLANATION sections
        full_response = response.choices[0].message.content
        
        # Parse the response to extract code and explanation
        code = ""
        explanation = ""
        
        if "CODE:" in full_response and "EXPLANATION:" in full_response:
            parts = full_response.split("EXPLANATION:")
            code_section = parts[0].replace("CODE:", "").strip()
            explanation = parts[1].strip()
            
            # Remove markdown code fences if present
            if code_section.startswith("```"):
                lines = code_section.split("\n")
                # Remove first line (```python or ```) and last line (```)
                code = "\n".join(lines[1:-1]) if len(lines) > 2 else code_section
            else:
                code = code_section
        else:
            # Fallback: treat entire response as code
            code = full_response
            explanation = "Visualization generated based on your request."
        
        return code.strip(), explanation.strip()
    
    except Exception as e:
        # Graceful error handling
        error_msg = f"Error communicating with LLM: {str(e)}"
        return "", error_msg
