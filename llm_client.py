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


def classify_question_type(question: str, data_context: str, chat_history: list = None) -> str:
    """
    Classify the type of question to determine the best approach to answer it.
    
    Args:
        question: User's question
        data_context: Dataset summary for context
        chat_history: List of previous messages for conversation context
    
    Returns:
        str: One of 'VISUALIZATION', 'ANALYSIS', or 'CONCEPTUAL'
    """
    system_prompt = """You are a data analysis assistant. Your job is to classify user questions into three categories:

1. VISUALIZATION - Questions that require creating plots, charts, or graphs
   Examples:
   - "Show me a histogram of ages"
   - "Create a scatter plot of price vs quantity"
   - "Plot the distribution of sales"
   - "Draw a correlation heatmap"
   - "Visualize the trend over time"

2. ANALYSIS - Questions that require calculations, aggregations, or data analysis but NOT visualization
   Examples:
   - "What's the average age?"
   - "Show average values for each category" (just numbers, not a plot)
   - "How many customers are from California?"
   - "Calculate the correlation between X and Y"
   - "Find the top 5 products by sales"
   - "What percentage of users are active?"

3. CONCEPTUAL - General questions about methodology, interpretation, or recommendations
   Examples:
   - "How should I analyze customer churn?"
   - "What does this correlation mean?"
   - "What analysis approach should I use?"
   - "Explain what a p-value is"

IMPORTANT:
- If the user explicitly asks for a plot/chart/graph/visualization, choose VISUALIZATION
- If they want to "see" or "show" numeric results (averages, counts, etc.), choose ANALYSIS
- Only choose CONCEPTUAL if no data calculation or visualization is needed

Respond with ONLY one word: VISUALIZATION, ANALYSIS, or CONCEPTUAL."""

    # Build messages array with conversation history
    messages = [{"role": "system", "content": system_prompt}]
    
    # Add recent conversation history (last 10 messages = 5 Q&A pairs)
    if chat_history:
        recent_messages = chat_history[-10:]
        for msg in recent_messages:
            # Only include user and assistant messages, skip system messages
            if msg["role"] in ["user", "assistant"]:
                content = msg["content"]
                
                # Enrich assistant messages with code/results if available
                if msg["role"] == "assistant" and msg.get("metadata"):
                    metadata = msg["metadata"]
                    if metadata.get("type") == "analysis":
                        # Include code and raw result for analysis
                        content += f"\n\n[Code executed: {metadata.get('code', 'N/A')}]"
                        content += f"\n[Raw result: {metadata.get('raw_result', 'N/A')}]"
                    elif metadata.get("type") == "visualization":
                        # Include code for visualizations
                        content += f"\n\n[Visualization code: {metadata.get('code', 'N/A')}]"
                
                messages.append({
                    "role": msg["role"],
                    "content": content
                })
    
    # Add current question with dataset context
    current_prompt = f"""Dataset Summary:
{data_context}

Classify this question. Respond with only: VISUALIZATION, ANALYSIS, or CONCEPTUAL.

Question: {question}"""
    
    messages.append({"role": "user", "content": current_prompt})

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=10,
            temperature=0
        )
        
        classification = response.choices[0].message.content.strip().upper()
        
        # Validate response
        if classification in ['VISUALIZATION', 'ANALYSIS', 'CONCEPTUAL']:
            return classification
        else:
            # Default to ANALYSIS if unclear
            return 'ANALYSIS'
    
    except Exception as e:
        # Default to ANALYSIS if classification fails
        return 'ANALYSIS'


def generate_analysis_code(question: str, data_context: str, chat_history: list = None, max_tokens: int = 1500) -> str:
    """
    Generate Python code to answer an analytical question about the data.
    
    This is different from visualization code - it focuses on calculations,
    aggregations, and returning text/numeric results rather than plots.
    
    Args:
        question: User's analytical question
        data_context: Dataset summary
        chat_history: List of previous messages for conversation context
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

CRITICAL RULES:
- ALWAYS perform actual calculations using the dataframe 'df'
- NEVER hardcode answers or create fake dictionaries with guessed values
- NEVER assume what the answer should be - let the code calculate it
- If the question references previous results, recalculate them from 'df'
- All comparisons, aggregations, and analysis MUST use actual data operations

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

Example for "Are the average values higher than 10?":
averages = df[['col1', 'col2']].mean()
result = averages > 10

Return ONLY the Python code, no explanations or markdown."""

    # Build messages array with conversation history
    messages = [{"role": "system", "content": system_prompt}]
    
    # Add recent conversation history (last 10 messages = 5 Q&A pairs)
    if chat_history:
        recent_messages = chat_history[-10:]
        for msg in recent_messages:
            if msg["role"] in ["user", "assistant"]:
                content = msg["content"]
                
                # Enrich assistant messages with code/results if available
                if msg["role"] == "assistant" and msg.get("metadata"):
                    metadata = msg["metadata"]
                    if metadata.get("type") == "analysis":
                        # Include code and raw result for analysis
                        content += f"\n\n[Code executed: {metadata.get('code', 'N/A')}]"
                        content += f"\n[Raw result: {metadata.get('raw_result', 'N/A')}]"
                    elif metadata.get("type") == "visualization":
                        # Include code for visualizations
                        content += f"\n\n[Visualization code: {metadata.get('code', 'N/A')}]"
                
                messages.append({
                    "role": msg["role"],
                    "content": content
                })
    
    # Add current question with dataset context
    current_prompt = f"""Dataset Summary:
{data_context}

Generate Python code to answer this question. Store the result in a variable called 'result'.

Question: {question}"""
    
    messages.append({"role": "user", "content": current_prompt})

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
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


def format_code_result_as_answer(question: str, code: str, result: str, data_context: str, chat_history: list = None) -> str:
    """
    Take the code execution result and format it as a natural language answer.
    
    Args:
        question: Original user question
        code: The code that was executed
        result: The output from code execution
        data_context: Dataset summary for context
        chat_history: List of previous messages for conversation context
    
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

    # Build messages array with conversation history
    messages = [{"role": "system", "content": system_prompt}]
    
    # Add recent conversation history (last 10 messages = 5 Q&A pairs)
    if chat_history:
        recent_messages = chat_history[-10:]
        for msg in recent_messages:
            if msg["role"] in ["user", "assistant"]:
                content = msg["content"]
                
                # Enrich assistant messages with code/results if available
                if msg["role"] == "assistant" and msg.get("metadata"):
                    metadata = msg["metadata"]
                    if metadata.get("type") == "analysis":
                        # Include code and raw result for analysis
                        content += f"\n\n[Code executed: {metadata.get('code', 'N/A')}]"
                        content += f"\n[Raw result: {metadata.get('raw_result', 'N/A')}]"
                    elif metadata.get("type") == "visualization":
                        # Include code for visualizations
                        content += f"\n\n[Visualization code: {metadata.get('code', 'N/A')}]"
                
                messages.append({
                    "role": msg["role"],
                    "content": content
                })
    
    # Add current question with code execution results
    current_prompt = f"""User Question: {question}

Code Executed:
{code}

Result:
{result}

Please provide a clear, natural language answer to the user's question based on this result."""
    
    messages.append({"role": "user", "content": current_prompt})

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
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


def generate_visualization_code(question: str, data_context: str, chat_history: list = None, max_tokens: int = 2000) -> tuple:
    """
    Generate Python code for data visualization based on user question.
    
    This function asks the LLM to write matplotlib/seaborn code to visualize the data.
    Returns both the code and a short explanation of what the visualization shows.
    
    Args:
        question: User's question requesting visualization (e.g., "Show correlation heatmap")
        data_context: The technical data summary
        chat_history: List of previous messages for conversation context
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

    # Build messages array with conversation history
    messages = [{"role": "system", "content": system_prompt}]
    
    # Add recent conversation history (last 10 messages = 5 Q&A pairs)
    if chat_history:
        recent_messages = chat_history[-10:]
        for msg in recent_messages:
            if msg["role"] in ["user", "assistant"]:
                content = msg["content"]
                
                # Enrich assistant messages with code/results if available
                if msg["role"] == "assistant" and msg.get("metadata"):
                    metadata = msg["metadata"]
                    if metadata.get("type") == "analysis":
                        # Include code and raw result for analysis
                        content += f"\n\n[Code executed: {metadata.get('code', 'N/A')}]"
                        content += f"\n[Raw result: {metadata.get('raw_result', 'N/A')}]"
                    elif metadata.get("type") == "visualization":
                        # Include code for visualizations
                        content += f"\n\n[Visualization code: {metadata.get('code', 'N/A')}]"
                
                messages.append({
                    "role": msg["role"],
                    "content": content
                })
    
    # Add current visualization request with dataset context
    current_prompt = f"""Dataset Summary:
{data_context}

Generate Python visualization code and explanation.

Request: {question}"""
    
    messages.append({"role": "user", "content": current_prompt})

    try:
        # ==== MAKE API CALL TO OPENAI ====
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.3  # Lower temperature for more consistent code generation
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
            if "```python" in code_section or "```" in code_section:
                # Extract all code between ```python and ``` markers
                import re
                # Find the last occurrence of code fence (handles nested fences)
                code_matches = re.findall(r'```python\s*(.*?)\s*```', code_section, re.DOTALL)
                if code_matches:
                    # Use the last valid code block found
                    code = code_matches[-1].strip()
                else:
                    # Fallback: try generic ``` markers
                    code_matches = re.findall(r'```\s*(.*?)\s*```', code_section, re.DOTALL)
                    if code_matches:
                        code = code_matches[-1].strip()
                    else:
                        # Remove just the fence markers
                        code = code_section.replace("```python", "").replace("```", "").strip()
            else:
                code = code_section
        else:
            # Fallback: try to extract code from markdown fences
            import re
            code_matches = re.findall(r'```python\s*(.*?)\s*```', full_response, re.DOTALL)
            if code_matches:
                code = code_matches[-1].strip()
                # Try to find explanation after the code block
                explanation_match = re.search(r'```\s*\n\s*(.+)', full_response, re.DOTALL)
                if explanation_match:
                    explanation = explanation_match.group(1).strip()
                else:
                    explanation = "Visualization generated based on your request."
            else:
                # Last resort: treat entire response as code
                code = full_response
                explanation = "Visualization generated based on your request."
        
        return code.strip(), explanation.strip()
    
    except Exception as e:
        # Graceful error handling
        error_msg = f"Error communicating with LLM: {str(e)}"
        return "", error_msg
