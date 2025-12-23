import os
import json
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file (contains OPENAI_API_KEY)
load_dotenv()

# Initialize OpenAI client with API key from environment variable
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


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

Be concise but thorough. Focus on actionable insights."""

    user_prompt = f"""Here is a summary of a dataset that was just uploaded:

{data_context}

Please provide a concise paragraph summarizing this dataset for a non-technical business audience. 
Focus on what the data contains, its quality, and any notable patterns or issues."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
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


# ==== 4-STEP ARCHITECTURE ====

def create_execution_plan(question: str, data_context: str, chat_history: list = None) -> dict:
    """
    Step 1: Analyze the question and create an execution plan.
    
    Args:
        question: User's question
        data_context: Combined dataset summaries
        chat_history: Previous conversation messages
    
    Returns:
        dict: {
            "needs_code": bool,
            "needs_evaluation": bool,
            "needs_explanation": bool,
            "reasoning": str
        }
    """
    system_prompt = """You are a data analysis planning assistant. Your job is to analyze user questions and determine the best approach to answer them.

You have access to these steps:
- Step 2: CODE - Write Python code to analyze data or create visualizations
- Step 3: EVALUATION - Examine code results and interpret findings
- Step 4: EXPLANATION - Provide a high-level answer to the user

Your task is to decide which steps are needed for the given question.

IMPORTANT RULES:
- Step 3 (EVALUATION) can only run if Step 2 (CODE) runs
- Step 4 (EXPLANATION) should almost always run (unless the code output is self-explanatory)
- For conceptual questions, skip code and evaluation
- For data questions, use code to get actual results (never guess)
- Code is stateless - previous data transformations must be regenerated if needed

EXAMPLES:

Question: "What is correlation?"
Plan: needs_code=false, needs_evaluation=false, needs_explanation=true
Reasoning: Conceptual question, no data analysis needed

Question: "Show me a histogram of ages"
Plan: needs_code=true, needs_evaluation=false, needs_explanation=true
Reasoning: Need code to create visualization, explanation describes what it shows

Question: "Does the data have collinearity issues?"
Plan: needs_code=true, needs_evaluation=true, needs_explanation=true
Reasoning: Need code to calculate correlations, evaluation to interpret values, explanation to answer question

Question: "What's the average salary?"
Plan: needs_code=true, needs_evaluation=false, needs_explanation=true
Reasoning: Need code to calculate, explanation to present result in context

Question: "Calculate the mean and tell me if it's unusually high"
Plan: needs_code=true, needs_evaluation=true, needs_explanation=true
Reasoning: Need code to calculate, evaluation to assess if high, explanation to answer

Return your response as JSON:
{
  "needs_code": true/false,
  "needs_evaluation": true/false,
  "needs_explanation": true/false,
  "reasoning": "brief explanation"
}"""

    messages = [{"role": "system", "content": system_prompt}]
    
    if chat_history:
        recent_messages = chat_history[-6:]
        for msg in recent_messages:
            if msg["role"] in ["user", "assistant"]:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
    
    user_prompt = f"""Dataset Summary:
{data_context}

User Question: {question}

Create an execution plan for this question."""
    
    messages.append({"role": "user", "content": user_prompt})
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=200,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        plan = json.loads(response.choices[0].message.content)
        
        if "needs_code" not in plan:
            plan["needs_code"] = False
        if "needs_evaluation" not in plan:
            plan["needs_evaluation"] = False
        if "needs_explanation" not in plan:
            plan["needs_explanation"] = True
        if "reasoning" not in plan:
            plan["reasoning"] = "Plan created"
        
        if plan["needs_evaluation"] and not plan["needs_code"]:
            plan["needs_evaluation"] = False
        
        return plan
    
    except Exception as e:
        return {
            "needs_code": True,
            "needs_evaluation": False,
            "needs_explanation": True,
            "reasoning": f"Error creating plan: {str(e)}"
        }


def generate_unified_code(question: str, data_context: str, chat_history: list = None, max_tokens: int = 2000) -> str:
    """
    Step 2: Generate Python code to answer the question.
    Unified function for both visualization and analysis.
    
    Args:
        question: User's question
        data_context: Combined dataset summaries
        chat_history: Previous conversation messages
        max_tokens: Maximum tokens for response
    
    Returns:
        str: Python code to execute
    """
    system_prompt = """You are an expert data analyst who writes Python code to answer questions.

Your job is to write clean, executable Python code using pandas, numpy, and Plotly.

IMPORTANT CODE REQUIREMENTS:
- Access datasets using the 'datasets' dictionary: datasets['dataset_id']
- For single dataset scenarios, 'df' is also available for backward compatibility
- Import statements NOT needed (pd, np, plt, px, go, make_subplots already imported)
- Available libraries: sklearn, scipy, statsmodels (sm, smf), seaborn (sns)
- For visualizations: Store the final figure in a variable called 'fig'
- For analysis: Store the final result in a variable called 'result'
- Code is stateless - if you need previous transformations, regenerate them
- You can reference previous code from chat history and reuse patterns

CRITICAL: DATAFRAME OPERATIONS & VARIABLE SCOPE
- When you add a column to a DataFrame, that column only exists in that specific DataFrame object
- If you create subsets (e.g., treatment_data = data[data['col'] == value]), those subsets are COPIES
- Columns added to the parent DataFrame AFTER creating subsets will NOT appear in the subsets
- ALWAYS add all derived columns BEFORE splitting data into subsets
- Example of CORRECT order:
  1. data['new_column'] = calculation
  2. subset1 = data[data['condition'] == True]  # subset1 now has 'new_column'
- Example of INCORRECT order:
  1. subset1 = data[data['condition'] == True]
  2. data['new_column'] = calculation  # subset1 does NOT have 'new_column'

DEFENSIVE PROGRAMMING:
- Before using a column, verify it exists: if 'column_name' in df.columns
- Add comments explaining data flow and which columns exist at each step
- When performing multi-step transformations, document the state of your DataFrame
- Use meaningful variable names that indicate what data they contain

VISUALIZATION GUIDELINES:
- Use Plotly (px for simple charts, go for complex ones)
- Use make_subplots for multiple plots
- Set proper titles, labels, and templates (plotly_white)
- Store final figure in 'fig'

ANALYSIS GUIDELINES:
- Perform actual calculations, never hardcode results
- Store final result in 'result' variable
- Result can be a value, string, dataframe, or dictionary

EXAMPLES:

Single dataset histogram:
fig = px.histogram(df, x='age', title='Age Distribution', template='plotly_white')

Multi-dataset comparison:
fig = go.Figure()
fig.add_trace(go.Scatter(x=datasets['dataset1']['date'], y=datasets['dataset1']['value'], name='Dataset 1'))
fig.add_trace(go.Scatter(x=datasets['dataset2']['date'], y=datasets['dataset2']['value'], name='Dataset 2'))
fig.update_layout(title='Comparison', template='plotly_white')

Calculate average:
result = df['salary'].mean()

Correlation matrix:
result = df[['col1', 'col2', 'col3']].corr()

Return ONLY the Python code, no explanations or markdown."""

    messages = [{"role": "system", "content": system_prompt}]
    
    if chat_history:
        recent_messages = chat_history[-10:]
        for msg in recent_messages:
            if msg["role"] in ["user", "assistant"]:
                content = msg["content"]
                
                if msg["role"] == "assistant" and msg.get("metadata"):
                    metadata = msg["metadata"]
                    if metadata.get("code"):
                        content += f"\n\n[Previous code: {metadata.get('code')}]"
                
                messages.append({
                    "role": msg["role"],
                    "content": content
                })
    
    user_prompt = f"""Dataset Summary:
{data_context}

Generate Python code to answer this question.

IMPORTANT: If multiple datasets are listed above, access them using datasets['dataset_id'].
If only one dataset is available, you can use 'df' for convenience.

Question: {question}"""
    
    messages.append({"role": "user", "content": user_prompt})
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.3
        )
        
        code = response.choices[0].message.content.strip()
        
        if code.startswith("```"):
            lines = code.split("\n")
            code = "\n".join(lines[1:-1]) if len(lines) > 2 else code
            code = code.replace("```python", "").replace("```", "").strip()
        
        return code
    
    except Exception as e:
        return f"# Error generating code: {str(e)}"


def fix_code_with_error(question: str, failed_code: str, error_message: str, data_context: str, chat_history: list = None, max_tokens: int = 2000) -> str:
    """
    Step 2b: Fix code that failed execution by analyzing the error.
    
    Args:
        question: Original user question
        failed_code: The code that failed
        error_message: The error message from execution
        data_context: Combined dataset summaries
        chat_history: Previous conversation messages
        max_tokens: Maximum tokens for response
    
    Returns:
        str: Fixed Python code
    """
    system_prompt = """You are an expert data analyst who fixes broken Python code.

Your job is to analyze the error and generate CORRECTED code that will execute successfully.

IMPORTANT CODE REQUIREMENTS:
- Access datasets using the 'datasets' dictionary: datasets['dataset_id']
- For single dataset scenarios, 'df' is also available for backward compatibility
- Import statements NOT needed (pd, np, plt, px, go, make_subplots already imported)
- Available libraries: sklearn, scipy, statsmodels (sm, smf), seaborn (sns)
- For visualizations: Store the final figure in a variable called 'fig'
- For analysis: Store the final result in a variable called 'result'

CRITICAL: DATAFRAME OPERATIONS & VARIABLE SCOPE
- When you add a column to a DataFrame, that column only exists in that specific DataFrame object
- If you create subsets (e.g., treatment_data = data[data['col'] == value]), those subsets are COPIES
- Columns added to the parent DataFrame AFTER creating subsets will NOT appear in the subsets
- ALWAYS add all derived columns BEFORE splitting data into subsets

COMMON ERROR PATTERNS:
1. KeyError/Column not found: Check if column exists in the DataFrame at that point in execution
2. NameError: Variable used before definition or out of scope
3. AttributeError: Method doesn't exist or wrong object type
4. ValueError: Data type mismatch or invalid operation

FIXING STRATEGY:
1. Read the error message carefully to identify the root cause
2. Trace through the code to find where the issue occurs
3. Fix the specific issue without changing working parts
4. Ensure the fix maintains the original intent of the code

Return ONLY the FIXED Python code, no explanations or markdown."""

    messages = [{"role": "system", "content": system_prompt}]
    
    if chat_history:
        recent_messages = chat_history[-5:]
        for msg in recent_messages:
            if msg["role"] in ["user", "assistant"]:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"][:500]  # Truncate to save tokens
                })
    
    user_prompt = f"""Dataset Summary:
{data_context}

Original Question: {question}

Failed Code:
```python
{failed_code}
```

Error Message:
{error_message}

Analyze the error and generate FIXED code that will execute successfully."""
    
    messages.append({"role": "user", "content": user_prompt})
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.2  # Lower temperature for more deterministic fixes
        )
        
        code = response.choices[0].message.content.strip()
        
        if code.startswith("```"):
            lines = code.split("\n")
            code = "\n".join(lines[1:-1]) if len(lines) > 2 else code
            code = code.replace("```python", "").replace("```", "").strip()
        
        return code
    
    except Exception as e:
        return f"# Error fixing code: {str(e)}"


def evaluate_code_results(question: str, code: str, output: str, data_context: str, chat_history: list = None) -> str:
    """
    Step 3: Evaluate and interpret the code results.
    
    Args:
        question: User's original question
        code: The code that was executed
        output: The output from code execution (stringified)
        data_context: Combined dataset summaries
        chat_history: Previous conversation messages
    
    Returns:
        str: Evaluation and interpretation of results
    """
    system_prompt = """You are a data analysis expert who evaluates code results and interprets findings.

Your job is to:
1. Examine the actual output from code execution
2. Identify patterns, insights, or issues
3. Provide objective interpretation based on the data
4. Be specific and grounded in actual results

CRITICAL RULES:
- ONLY discuss what you see in the actual output
- NEVER make up data or hallucinate findings
- Be specific with numbers and values
- Identify trends, outliers, or notable patterns
- Keep it concise and factual

This evaluation will be used to create the final explanation for the user."""

    messages = [{"role": "system", "content": system_prompt}]
    
    user_prompt = f"""Dataset Summary:
{data_context}

User Question: {question}

Code Executed:
```python
{code}
```

Code Output:
{output}

Evaluate these results and provide your interpretation. Focus on what the data actually shows."""
    
    messages.append({"role": "user", "content": user_prompt})
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=800,
            temperature=0.5
        )
        
        return response.choices[0].message.content
    
    except Exception as e:
        return f"Error evaluating results: {str(e)}"


def generate_final_explanation(question: str, evaluation: str = None, data_context: str = None, chat_history: list = None) -> str:
    """
    Step 4: Generate final explanation for the user.
    
    Args:
        question: User's original question
        evaluation: Results from Step 3 (if available)
        data_context: Combined dataset summaries
        chat_history: Previous conversation messages
    
    Returns:
        str: User-facing explanation
    """
    system_prompt = """You are a data science communicator who explains findings to business users.

Your job is to:
1. Provide a clear, high-level answer to the user's question
2. Use plain language suitable for non-technical audiences
3. Synthesize findings from the evaluation (if provided)
4. Be concise but thorough

Keep your explanation focused and actionable."""

    messages = [{"role": "system", "content": system_prompt}]
    
    if evaluation:
        user_prompt = f"""User Question: {question}

Analysis Findings:
{evaluation}

Provide a clear, high-level explanation that answers the user's question."""
    else:
        user_prompt = f"""Dataset Summary:
{data_context}

User Question: {question}

Provide a clear explanation that answers the user's question."""
    
    messages.append({"role": "user", "content": user_prompt})
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=1000,
            temperature=0.7
        )
        
        return response.choices[0].message.content
    
    except Exception as e:
        return f"Error generating explanation: {str(e)}"
