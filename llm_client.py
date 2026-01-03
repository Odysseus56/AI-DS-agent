import os
import json
from openai import OpenAI
import streamlit as st

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
    # Check for debug mode trigger
    debug_mode = "ERROR RECOVERY SHOWCASE" in question.upper()
    
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

CRITICAL: Before using columns in statistical models (regression, ML models):
1. Drop all date/datetime/Period columns - they cannot be used in sklearn/statsmodels
2. Use pd.to_numeric() to ensure all numeric columns are properly typed
3. Example: X = X.select_dtypes(include=[np.number]) to keep only numeric columns

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
        
        # DEBUG MODE: Inject intentional error on first attempt
        if debug_mode:
            code = _inject_intentional_error(code)
        
        return code
    
    except Exception as e:
        return f"# Error generating code: {str(e)}"


def _inject_intentional_error(code: str) -> str:
    """
    Inject a common, fixable error into the code for demo purposes.
    This is used when "ERROR RECOVERY SHOWCASE" is in the user's question.
    
    Injects one of several common errors that the LLM can easily fix:
    - Typo in column name
    - Missing .reset_index()
    - Wrong aggregation function
    """
    import random
    
    lines = code.split('\n')
    
    # Strategy 1: Add typo to a column name (most common and easy to fix)
    for i, line in enumerate(lines):
        if "'" in line and '[' in line and ('df[' in line or 'datasets[' in line):
            # Found a line with column access like df['column_name']
            # Add a typo by appending 'x' to the column name
            if "df['" in line:
                lines[i] = line.replace("df['", "df['x", 1)  # Only first occurrence
                return '\n'.join(lines)
            elif '"]["' in line:
                # For datasets['id']['column']
                parts = line.split('"]["')
                if len(parts) >= 2:
                    parts[1] = 'x' + parts[1]
                    lines[i] = '"]["'.join(parts)
                    return '\n'.join(lines)
    
    # Strategy 2: Remove .reset_index() if present (causes index issues)
    for i, line in enumerate(lines):
        if '.reset_index()' in line:
            lines[i] = line.replace('.reset_index()', '')
            return '\n'.join(lines)
    
    # Strategy 3: Change groupby aggregation to wrong function
    for i, line in enumerate(lines):
        if '.mean()' in line and 'groupby' in line:
            lines[i] = line.replace('.mean()', '.sum()')
            return '\n'.join(lines)
    
    # Fallback: Add a typo to 'result' or 'fig' variable name
    for i, line in enumerate(lines):
        if line.strip().startswith('result ='):
            lines[i] = line.replace('result =', 'resultt =', 1)
            return '\n'.join(lines)
        elif line.strip().startswith('fig ='):
            lines[i] = line.replace('fig =', 'figg =', 1)
            return '\n'.join(lines)
    
    # If no suitable injection point found, return original code
    return code


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


# ==== MVP ARCHITECTURE FUNCTIONS ====

def understand_question(question: str, data_summary: str) -> dict:
    """
    Node 0: Determine if question needs explanation only or data work.
    
    Args:
        question: User's question
        data_summary: Available datasets summary
    
    Returns:
        dict: {needs_data_work: bool, reasoning: str}
    """
    system_prompt = """You are a data science assistant that analyzes user questions.

Your job is to determine if a question requires data analysis or just a conceptual explanation.

Examples:
- "What is a p-value?" → explanation_only (conceptual question)
- "What's the average age?" → data_work (needs calculation)
- "Show me age distribution" → data_work (needs visualization)
- "Explain what correlation means" → explanation_only (conceptual)
- "How do I interpret R-squared?" → explanation_only (conceptual)
- "Calculate the correlation between X and Y" → data_work (needs calculation)

Return JSON:
{
  "needs_data_work": true/false,
  "reasoning": "brief explanation of why"
}"""

    user_prompt = f"""Available Data:
{data_summary}

User Question: {question}

Determine if this question requires data analysis or just conceptual explanation."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=200,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        return {
            "needs_data_work": result.get("needs_data_work", True),
            "reasoning": result.get("reasoning", "")
        }
    except Exception as e:
        return {"needs_data_work": True, "reasoning": f"Error: {str(e)}"}


def provide_explanation(question: str, data_summary: str = None, alignment_issues: str = None) -> str:
    """
    Node 1A: Answer conceptual/explanation questions or explain limitations.
    
    Args:
        question: User's question
        data_summary: Context (if relevant)
        alignment_issues: Alignment issues from Node 3 (if coming from failed alignment)
    
    Returns:
        str: Explanation text
    """
    system_prompt = """You are a data science educator explaining concepts to business users.

Provide clear, concise explanations using:
- Plain language suitable for non-technical audiences
- Concrete examples when helpful
- Practical context for business decisions

If explaining a limitation (data doesn't support the question):
- Clearly state what's missing
- Suggest alternatives if possible"""

    if alignment_issues:
        user_prompt = f"""Question: {question}

Available Data: {data_summary}

Limitation: {alignment_issues}

Explain why we cannot answer this question with the available data and suggest alternatives."""
    else:
        user_prompt = f"""Question: {question}

Context: {data_summary if data_summary else 'No specific data context'}

Provide a clear, concise explanation."""

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
        return f"Error generating explanation: {str(e)}"


def formulate_requirements(question: str, data_summary: str, remediation_guidance: str = None) -> dict:
    """
    Node 1B: Define what's needed to answer the question.
    
    Args:
        question: User's question
        data_summary: Available datasets
        remediation_guidance: Guidance from Node 5a (if retrying)
    
    Returns:
        dict: {variables_needed, constraints, analysis_type, success_criteria, reasoning}
    """
    system_prompt = """You are a data scientist planning an analysis. Define requirements to answer the question.

Specify:
1. VARIABLES NEEDED: Which columns/features are required?
2. DATA CONSTRAINTS: What data quality is needed? (e.g., no missing values in X, Y must be numeric)
3. ANALYSIS APPROACH: What type of analysis? (descriptive stats, visualization, correlation, regression, etc.)
4. SUCCESS CRITERIA: What output would answer the question?

Return JSON:
{
  "variables_needed": ["col1", "col2", ...],
  "constraints": ["constraint1", "constraint2", ...],
  "analysis_type": "descriptive/visualization/correlation/regression/classification/...",
  "success_criteria": "what the output should contain",
  "reasoning": "why this approach"
}"""

    user_prompt = f"""Question: {question}
Available Data: {data_summary}
{f'Remediation Guidance: {remediation_guidance}' if remediation_guidance else ''}

Define the requirements to answer this question."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=500,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        return {
            "variables_needed": result.get("variables_needed", []),
            "constraints": result.get("constraints", []),
            "analysis_type": result.get("analysis_type", "unknown"),
            "success_criteria": result.get("success_criteria", ""),
            "reasoning": result.get("reasoning", "")
        }
    except Exception as e:
        return {
            "variables_needed": [],
            "constraints": [],
            "analysis_type": "unknown",
            "success_criteria": "",
            "reasoning": f"Error: {str(e)}"
        }


def profile_data(question: str, requirements: dict, data_summary: str, remediation_guidance: str = None) -> dict:
    """
    Node 2: Examine data to understand what's actually available.
    
    Args:
        question: User's question
        requirements: What we need (from Node 1B)
        data_summary: Pre-computed summary
        remediation_guidance: Guidance from Node 5a (if retrying)
    
    Returns:
        dict: {available_columns, missing_columns, data_quality, limitations, is_suitable, reasoning}
    """
    system_prompt = """You are examining the dataset to profile what's available for this analysis.

Profile the data:
1. AVAILABLE COLUMNS: Which required columns exist?
2. DATA QUALITY: Missing values, data types, value ranges for relevant columns
3. LIMITATIONS: What's missing or problematic?
4. SUITABILITY: Can this data support the required analysis?

Return JSON:
{
  "available_columns": ["col1", "col2", ...],
  "missing_columns": ["col3", ...],
  "data_quality": {
    "col1": "description of quality",
    "col2": "description of quality"
  },
  "limitations": ["limitation1", "limitation2", ...],
  "is_suitable": true/false,
  "reasoning": "..."
}"""

    user_prompt = f"""Question: {question}
Requirements: {json.dumps(requirements)}
Dataset Summary: {data_summary}
{f'Remediation Guidance: {remediation_guidance}' if remediation_guidance else ''}

Profile the data for this analysis."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=600,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        return {
            "available_columns": result.get("available_columns", []),
            "missing_columns": result.get("missing_columns", []),
            "data_quality": result.get("data_quality", {}),
            "limitations": result.get("limitations", []),
            "is_suitable": result.get("is_suitable", True),
            "reasoning": result.get("reasoning", "")
        }
    except Exception as e:
        return {
            "available_columns": [],
            "missing_columns": [],
            "data_quality": {},
            "limitations": [f"Error: {str(e)}"],
            "is_suitable": False,
            "reasoning": f"Error profiling data: {str(e)}"
        }


def check_alignment(requirements: dict, data_profile: dict) -> dict:
    """
    Node 3: Verify data can satisfy requirements; iterate if not.
    
    Args:
        requirements: What we need
        data_profile: What we have
    
    Returns:
        dict: {aligned, gaps, recommendation, reasoning}
    """
    system_prompt = """Check if the available data can satisfy the analysis requirements.

Determine:
1. ALIGNMENT: Does data satisfy requirements?
2. GAPS: What's missing or misaligned?
3. RECOMMENDATION: What should we do?
   - "proceed" if aligned
   - "revise_requirements" if requirements are too strict/wrong
   - "revise_data_understanding" if we need to look at data differently
   - "cannot_proceed" if fundamentally incompatible

Return JSON:
{
  "aligned": true/false,
  "gaps": ["gap1", "gap2", ...],
  "recommendation": "proceed/revise_requirements/revise_data_understanding/cannot_proceed",
  "reasoning": "..."
}"""

    user_prompt = f"""Requirements: {json.dumps(requirements)}
Data Profile: {json.dumps(data_profile)}

Check alignment between requirements and available data."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=400,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        return {
            "aligned": result.get("aligned", False),
            "gaps": result.get("gaps", []),
            "recommendation": result.get("recommendation", "proceed"),
            "reasoning": result.get("reasoning", "")
        }
    except Exception as e:
        return {
            "aligned": True,
            "gaps": [],
            "recommendation": "proceed",
            "reasoning": f"Error checking alignment: {str(e)}, proceeding anyway"
        }


def generate_analysis_code(question: str, requirements: dict, data_profile: dict, 
                           data_summary: str, error: str = None, 
                           remediation_guidance: str = None) -> str:
    """
    Node 4: Generate Python code to perform the analysis.
    
    Args:
        question: User's question
        requirements: Analysis requirements
        data_profile: Data context
        data_summary: Full data summary
        error: Previous error (if retrying)
        remediation_guidance: Guidance from Node 5a (if retrying)
    
    Returns:
        str: Python code to execute
    """
    system_prompt = """You are an expert data analyst writing Python code to answer this question.

CODE REQUIREMENTS:
- Access datasets using: datasets['dataset_id'] or df (for single dataset)
- Libraries pre-imported: pd, np, plt, px, go, make_subplots, sklearn, scipy, statsmodels
- For visualizations: Store figure in variable 'fig'
- For analysis: Store result in variable 'result'
- Use Plotly for visualizations (plotly_white template)
- Perform actual calculations, never hardcode results

CRITICAL: DATAFRAME OPERATIONS & VARIABLE SCOPE
- When you add a column to a DataFrame, that column only exists in that specific DataFrame object
- If you create subsets, those subsets are COPIES
- ALWAYS add all derived columns BEFORE splitting data into subsets

DEFENSIVE PROGRAMMING:
- Before using a column, verify it exists: if 'column_name' in df.columns
- Use meaningful variable names

Return ONLY the Python code, no explanations or markdown."""

    if error and remediation_guidance:
        user_prompt = f"""Fix the code that failed with this error.

Question: {question}
Requirements: {json.dumps(requirements)}
Data Profile: {json.dumps(data_profile)}
Error: {error}
Remediation Guidance: {remediation_guidance}

Generate CORRECTED code."""
    else:
        user_prompt = f"""Question: {question}
Requirements: {json.dumps(requirements)}
Data Profile: {json.dumps(data_profile)}
Dataset Summary: {data_summary}

Write clean, executable Python code to answer this question."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=2000,
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


def evaluate_results(question: str, requirements: dict, code: str, 
                     execution_result: dict, execution_success: bool, error: str = None) -> dict:
    """
    Node 5: Validate if results are correct and make sense.
    
    Args:
        question: User's question
        requirements: What we were trying to achieve
        code: Executed code
        execution_result: Code output
        execution_success: Whether code ran
        error: Error message (if failed)
    
    Returns:
        dict: {is_valid, issues_found, confidence, recommendation, reasoning}
    """
    system_prompt = """Evaluate the analysis results for correctness and sensibility.

Validate:
1. PLAUSIBILITY: Are numbers reasonable? Any impossible values (e.g., correlation > 1)?
2. METHODOLOGY: Was the approach appropriate for the question?
3. COMPLETENESS: Did this actually answer the question?
4. ISSUES: Any errors, red flags, or concerns?

Return JSON:
{
  "is_valid": true/false,
  "issues_found": ["issue1", "issue2", ...],
  "confidence": 0.0-1.0,
  "recommendation": "accept/code_error/wrong_approach/data_issue",
  "reasoning": "..."
}"""

    result_str = ""
    if execution_result:
        result_str = execution_result.get("result_str", str(execution_result))
    
    user_prompt = f"""Question: {question}
Requirements: {json.dumps(requirements)}
Code: {code}
Execution Success: {execution_success}
Results: {result_str[:2000]}
Error: {error if error else 'None'}

Evaluate these results."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=500,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        return {
            "is_valid": result.get("is_valid", True),
            "issues_found": result.get("issues_found", []),
            "confidence": result.get("confidence", 0.8),
            "recommendation": result.get("recommendation", "accept"),
            "reasoning": result.get("reasoning", "")
        }
    except Exception as e:
        return {
            "is_valid": True,
            "issues_found": [],
            "confidence": 0.5,
            "recommendation": "accept",
            "reasoning": f"Error evaluating: {str(e)}"
        }


def plan_remediation(question: str, evaluation: dict, code: str, error: str,
                     requirements: dict, data_profile: dict) -> dict:
    """
    Node 5a: Determine root cause and which node to revisit.
    
    Args:
        question: User's question
        evaluation: Issues identified
        code: Current code
        error: Error message
        requirements: Current requirements
        data_profile: Current data understanding
    
    Returns:
        dict: {root_cause, action, guidance, reasoning}
    """
    system_prompt = """Determine the root cause of the issue and plan remediation.

Diagnose:
1. ROOT CAUSE: What's the fundamental problem?
2. ACTION: What should we do?
   - "rewrite_code": Code has bugs or wrong implementation
   - "revise_requirements": We're approaching the problem wrong
   - "reexamine_data": We misunderstood the data structure/quality

Return JSON:
{
  "root_cause": "description",
  "action": "rewrite_code/revise_requirements/reexamine_data",
  "guidance": "specific instructions for the target node",
  "reasoning": "..."
}"""

    user_prompt = f"""Question: {question}
Evaluation Issues: {json.dumps(evaluation)}
Code: {code}
Error: {error if error else 'None'}
Requirements: {json.dumps(requirements)}
Data Profile: {json.dumps(data_profile)}

Diagnose the issue and plan remediation."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=400,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        return {
            "root_cause": result.get("root_cause", "Unknown"),
            "action": result.get("action", "rewrite_code"),
            "guidance": result.get("guidance", ""),
            "reasoning": result.get("reasoning", "")
        }
    except Exception as e:
        return {
            "root_cause": f"Error: {str(e)}",
            "action": "rewrite_code",
            "guidance": "Try a simpler approach",
            "reasoning": f"Error planning remediation: {str(e)}"
        }


def explain_results(question: str, evaluation: dict, execution_result: dict,
                    code: str, requirements: dict, total_remediations: int = 0,
                    max_attempts_exceeded: bool = False) -> str:
    """
    Node 6: Communicate findings to user in plain language.
    
    Args:
        question: User's question
        evaluation: Analysis evaluation
        execution_result: Code output
        code: Executed code
        requirements: Analysis requirements
        total_remediations: Number of remediation attempts
        max_attempts_exceeded: Whether we gave up
    
    Returns:
        str: User-facing explanation
    """
    system_prompt = """Explain the analysis results to a business user.

Provide:
1. DIRECT ANSWER: Clear answer to the user's question (or explain what went wrong)
2. KEY FINDINGS: Main insights from the analysis (if successful)
3. CONTEXT: What the numbers mean in practical terms
4. CAVEATS: Any limitations or concerns (if evaluation flagged issues)

If max remediation attempts were exceeded:
- Clearly explain what error occurred
- Describe what we tried to fix it
- Suggest how the user might help resolve it

Use plain language suitable for non-technical audiences.
Be concise but thorough."""

    result_str = ""
    if execution_result:
        result_str = execution_result.get("result_str", str(execution_result))[:1500]

    user_prompt = f"""Question: {question}
Evaluation: {json.dumps(evaluation) if evaluation else 'N/A'}
Results: {result_str}
Remediation Attempts: {total_remediations}
Max Attempts Exceeded: {max_attempts_exceeded}

Explain the results to the user."""

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
        return f"Error generating explanation: {str(e)}"
