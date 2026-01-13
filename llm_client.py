import os
import json
from openai import OpenAI
import streamlit as st
from config import (
    MODEL_NODE_0_UNDERSTAND,
    MODEL_NODE_1B_REQUIREMENTS,
    MODEL_NODE_2_PROFILE,
    MODEL_NODE_3_ALIGNMENT,
    MODEL_NODE_4_CODE_GENERATION,
    MODEL_NODE_4_CODE_FIXING,
    MODEL_NODE_5_EVALUATION,
    MODEL_NODE_5A_REMEDIATION,
    MODEL_NODE_6_EXPLANATION,
    MODEL_FAST
)

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
            model=MODEL_NODE_0_UNDERSTAND,
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
            model=MODEL_FAST,
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
        dict: {variables_needed, constraints, intent, success_criteria, reasoning}
              intent contains: {primary_goal, output_format, methodology, confidence}
    """
    system_prompt = """You are a data scientist planning an analysis. Define requirements to answer the question.

IMPORTANT: If multiple datasets are available, consider whether the question requires merging/joining them.

Specify:
1. VARIABLES NEEDED: Which columns/features are required? For merge operations, include the join key(s).
2. DATA CONSTRAINTS: What data quality is needed? (e.g., no missing values in X, Y must be numeric)
3. INTENT: Capture the user's intent across multiple dimensions (see schema below).
4. SUCCESS CRITERIA: What output would answer the question?

INTENT SCHEMA (captures user intent flexibly):
{
  "primary_goal": One of:
    - "compare_groups" - Compare metrics between groups (t-test, ANOVA, chi-square)
    - "find_relationship" - Find correlation/association between variables
    - "predict_outcome" - Build predictive model (regression, classification)
    - "describe_data" - Summarize, aggregate, or explore data
    - "identify_patterns" - Clustering, segmentation, anomaly detection
    - "merge_data" - Combine multiple datasets
    - "track_trends" - Time series analysis, trend detection
  
  "output_format": One of:
    - "numeric" - Return numbers, statistics, p-values, coefficients
    - "visualization" - Return a chart/plot (ONLY if user explicitly asks to show/plot/visualize)
    - "table" - Return a dataframe or structured table
    - "text" - Return text explanation only
  
  "methodology": Specific technique to use (e.g., "t_test", "pearson_correlation", "linear_regression", "bar_chart", "kmeans_clustering")
  
  "confidence": 0.0-1.0 - How confident are you in this interpretation?
}

GUIDELINES FOR OUTPUT_FORMAT:
- Use "visualization" ONLY when user explicitly says: "show", "plot", "visualize", "chart", "graph", "display"
- Use "numeric" for statistical tests, correlations, regression coefficients, p-values
- Use "table" for data summaries, aggregations, merged datasets
- When ambiguous, prefer "numeric" or "table" over "visualization"

Return JSON:
{
  "variables_needed": ["col1", "col2", ...],
  "constraints": ["constraint1", "constraint2", ...],
  "intent": {
    "primary_goal": "...",
    "output_format": "...",
    "methodology": "...",
    "confidence": 0.0-1.0
  },
  "success_criteria": "what the output should contain",
  "reasoning": "why this approach"
}"""

    user_prompt = f"""Question: {question}
Available Data: {data_summary}
{f'Remediation Guidance: {remediation_guidance}' if remediation_guidance else ''}

Define the requirements to answer this question."""

    try:
        response = client.chat.completions.create(
            model=MODEL_NODE_1B_REQUIREMENTS,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=500,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        
        # Parse intent schema
        intent = result.get("intent", {})
        if not isinstance(intent, dict):
            intent = {}
        
        # Ensure intent has all required fields with defaults
        intent = {
            "primary_goal": intent.get("primary_goal", "describe_data"),
            "output_format": intent.get("output_format", "numeric"),
            "methodology": intent.get("methodology", "unknown"),
            "confidence": intent.get("confidence", 0.5)
        }
        
        # Backward compatibility: derive analysis_type from intent for downstream consumers
        # This allows gradual migration without breaking existing code
        output_format = intent["output_format"]
        primary_goal = intent["primary_goal"]
        
        if output_format == "visualization":
            analysis_type = "visualization"
        elif primary_goal == "compare_groups":
            analysis_type = "hypothesis_test"
        elif primary_goal == "find_relationship":
            analysis_type = "correlation"
        elif primary_goal == "predict_outcome":
            analysis_type = "regression"  # or classification, but regression is safer default
        elif primary_goal == "identify_patterns":
            analysis_type = "clustering"
        elif primary_goal == "merge_data":
            analysis_type = "data_merging"
        elif primary_goal == "track_trends":
            analysis_type = "time_series"
        else:
            analysis_type = "descriptive"
        
        return {
            "variables_needed": result.get("variables_needed", []),
            "constraints": result.get("constraints", []),
            "intent": intent,
            "analysis_type": analysis_type,  # Backward compatibility
            "success_criteria": result.get("success_criteria", ""),
            "reasoning": result.get("reasoning", "")
        }
    except Exception as e:
        return {
            "variables_needed": [],
            "constraints": [],
            "intent": {
                "primary_goal": "describe_data",
                "output_format": "numeric",
                "methodology": "unknown",
                "confidence": 0.0
            },
            "analysis_type": "unknown",
            "success_criteria": "",
            "reasoning": f"Error: {str(e)}"
        }


def select_columns_for_profiling(question: str, requirements: dict, compact_summary: str, max_columns: int = 40) -> list:
    """
    Node 2 Step 1: Analyze compact summary and select columns for detailed profiling.
    
    Args:
        question: User's question
        requirements: What we need (from Node 1B)
        compact_summary: Summary A (compact overview of all columns)
        max_columns: Maximum columns to select for detailed profiling
    
    Returns:
        list: Column names to profile in detail
    """
    system_prompt = f"""You are selecting which columns to profile in detail for this analysis.

You have a compact summary of ALL columns. Your task is to identify which columns are most relevant
for answering the user's question based on the requirements.

Select columns that are:
1. REQUIRED: Explicitly mentioned in requirements (variables_needed)
2. RELEVANT: Likely needed for the analysis type (e.g., numeric columns for correlation)
3. QUALITY-CRITICAL: Have missing data or potential issues that need investigation
4. JOIN KEYS: Columns that might be used to merge datasets (e.g., customer_id, order_id)

Do NOT select:
- Irrelevant metadata columns (internal_flag_*, system_id, etc.)
- Columns clearly unrelated to the question

Limit your selection to {max_columns} columns maximum.

Return JSON:
{{
  "selected_columns": ["col1", "col2", ...],
  "reasoning": "why these columns were selected"
}}"""

    user_prompt = f"""Question: {question}
Requirements: {json.dumps(requirements)}

{compact_summary}

Select the most relevant columns for detailed profiling."""

    try:
        response = client.chat.completions.create(
            model=MODEL_NODE_2_PROFILE,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=500,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        selected = result.get("selected_columns", [])
        
        # Ensure we don't exceed max_columns
        return {
            "selected_columns": selected[:max_columns],
            "reasoning": result.get("reasoning", "")
        }
    
    except Exception as e:
        print(f"Error in select_columns_for_profiling: {str(e)}")
        # Fallback: return columns mentioned in requirements
        fallback_columns = requirements.get("variables_needed", [])[:max_columns]
        return {
            "selected_columns": fallback_columns,
            "reasoning": "Fallback: Using columns from requirements due to selection error"
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
    system_prompt = """You are examining the dataset(s) to profile what's available for this analysis.

IMPORTANT: You may receive MULTIPLE datasets. Look across ALL datasets to find the required columns.

You may receive data summaries in two formats:
1. DETAILED PROFILE ONLY: For small datasets, you'll see detailed profiles with samples and statistics
2. COMPACT + DETAILED: For large datasets, you'll see:
   - COMPACT OVERVIEW: High-level summary of ALL columns
   - DETAILED PROFILE: In-depth analysis of selected relevant columns

Use the compact overview to understand the full dataset scope, and the detailed profile to assess data quality.

Profile the data:
1. AVAILABLE COLUMNS: Which required columns exist? Check ALL datasets provided.
   - For single datasets: list columns from that dataset
   - For multiple datasets: list columns from ANY dataset that has them
   - For merge operations: identify common columns that can be used as join keys
2. DATA QUALITY: Missing values, data types, value ranges, format issues for relevant columns
   - Use sample values to detect format inconsistencies (e.g., mixed date formats)
   - Use statistics to identify outliers or suspicious values
3. LIMITATIONS: What's missing or problematic?
4. SUITABILITY: Can this data support the required analysis?

MULTI-DATASET HANDLING:
- If the analysis requires merging datasets (e.g., "merge on customer_id"), check if the join key exists in ALL relevant datasets
- List the join key in available_columns if it exists across datasets
- For other columns, list them if they exist in ANY dataset

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
            model=MODEL_NODE_2_PROFILE,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=1000,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        response_content = response.choices[0].message.content
        
        # Try to parse JSON
        try:
            result = json.loads(response_content)
        except json.JSONDecodeError as json_err:
            # Log the actual response for debugging
            print(f"JSON Parse Error in profile_data: {json_err}")
            print(f"Response content (first 500 chars): {response_content[:500]}")
            raise
        
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
        dict: {aligned, gaps, caveats, recommendation, reasoning}
    """
    system_prompt = """Check if the available data can satisfy the analysis requirements.

Determine:
1. ALIGNMENT: Does data satisfy requirements?
2. GAPS: What's missing or misaligned?
3. CAVEATS: Issues that don't block analysis but should be noted (e.g., "20% missing values - using complete cases")
4. RECOMMENDATION: What should we do?
   - "proceed" if fully aligned with no issues
   - "proceed_with_caveats" if analysis is possible but has limitations (e.g., missing data <30%, 
     data type issues that can be fixed, minor quality concerns). USE THIS when a human data scientist 
     would proceed with appropriate warnings rather than refusing.
   - "revise_requirements" if requirements are too strict/wrong
   - "revise_data_understanding" if we need to look at data differently
   - "cannot_proceed" if fundamentally incompatible (e.g., required column doesn't exist, >50% missing)

IMPORTANT: Prefer "proceed_with_caveats" over "cannot_proceed" when:
- Missing data is <30% (can use complete cases or imputation)
- Date formats are inconsistent (can be parsed/standardized)
- Data types need conversion (strings to numbers, Yes/No to 1/0)
- There are outliers or anomalies (can be handled in code)

Return JSON:
{
  "aligned": true/false,
  "gaps": ["gap1", "gap2", ...],
  "caveats": ["caveat1", "caveat2", ...],
  "recommendation": "proceed/proceed_with_caveats/revise_requirements/revise_data_understanding/cannot_proceed",
  "reasoning": "..."
}"""

    user_prompt = f"""Requirements: {json.dumps(requirements)}
Data Profile: {json.dumps(data_profile)}

Check alignment between requirements and available data."""

    try:
        response = client.chat.completions.create(
            model=MODEL_NODE_3_ALIGNMENT,
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
            "caveats": result.get("caveats", []),
            "recommendation": result.get("recommendation", "proceed"),
            "reasoning": result.get("reasoning", "")
        }
    except Exception as e:
        return {
            "aligned": True,
            "gaps": [],
            "caveats": [],
            "recommendation": "proceed",
            "reasoning": f"Error checking alignment: {str(e)}, proceeding anyway"
        }


def generate_analysis_code(question: str, requirements: dict, data_profile: dict, 
                           data_summary: str, error: str = None, 
                           remediation_guidance: str = None, execution_context: dict = None) -> str:
    """
    Node 4: Generate Python code to perform the analysis.
    
    Args:
        question: User's question
        requirements: Analysis requirements
        data_profile: Data context
        data_summary: Full data summary
        error: Previous error (if retrying)
        remediation_guidance: Guidance from Node 5a (if retrying)
        execution_context: Structured execution environment context (datasets, versions, etc.)
    
    Returns:
        str: Python code to execute
    """
    # Build execution context section for prompt
    if execution_context:
        datasets_list = execution_context['datasets']['available']
        datasets_info = "\n".join(
            f"  - datasets['{name}']  # {execution_context['datasets']['metadata'][name]['shape'][0]} rows × {execution_context['datasets']['metadata'][name]['shape'][1]} cols"
            for name in datasets_list
        )
        
        context_section = f"""
EXECUTION ENVIRONMENT:

Available Datasets:
{datasets_info}

Pre-Defined Variables:
  - datasets: dict with keys {datasets_list}
  - pd: pandas module
  - np: numpy module
  - px: plotly.express module
  - go: plotly.graph_objects module
  - make_subplots: plotly.subplots.make_subplots function
  - sklearn, scipy, stats, sm, smf: Available if installed

Variables You MUST Define:
  - df: NOT pre-defined. You must create it: df = datasets['dataset_name']

Output Variables:
  - fig: Store Plotly figure here for visualizations
  - result: Store analysis result here (dict, DataFrame, or scalar)

Library Versions:
  - pandas: {execution_context['library_versions']['pandas']}
  - numpy: {execution_context['library_versions']['numpy']}
  - sklearn: {execution_context['library_versions']['sklearn']}

IMPORTANT API NOTES (pandas {execution_context['library_versions']['pandas']}):
  - value_counts().reset_index() creates columns ['original_col', 'count'], NOT ['index', 'count']
  - Example: df['income_bracket'].value_counts().reset_index() → columns are ['income_bracket', 'count']
  - For plotly: px.bar(df, x='income_bracket', y='count') - use actual column name, not 'index'
  - Categorical columns need encoding before ML: pd.get_dummies(df, columns=['col1', 'col2'])
"""
    else:
        context_section = """
EXECUTION ENVIRONMENT:
- Access datasets using: datasets['dataset_name']
- Libraries pre-imported: pd, np, plt, px, go, make_subplots, sklearn, scipy, statsmodels
"""
    
    # Determine expected output type from requirements using intent schema
    intent = requirements.get('intent', {}) if requirements else {}
    output_format = intent.get('output_format', 'numeric')
    primary_goal = intent.get('primary_goal', 'describe_data')
    methodology = intent.get('methodology', 'unknown')
    
    # Fallback to analysis_type for backward compatibility
    if not intent:
        analysis_type = requirements.get('analysis_type', 'unknown') if requirements else 'unknown'
        output_format = 'visualization' if analysis_type == 'visualization' else 'numeric'
    
    is_visualization = output_format == 'visualization'
    
    if is_visualization:
        output_instruction = """OUTPUT: Store your Plotly figure in variable 'fig'. Do NOT create a 'result' variable."""
    elif output_format == 'table':
        output_instruction = """OUTPUT: Store your result as a DataFrame in variable 'result'. 
Do NOT create a 'fig' variable or any visualizations."""
    else:  # numeric or text
        output_instruction = """OUTPUT: Store your analysis result in variable 'result' (dict, DataFrame, or scalar). 
Do NOT create a 'fig' variable or any visualizations - the user asked for numeric/statistical results only."""
    
    system_prompt = f"""You are an expert data analyst writing Python code to answer this question.
{context_section}
CODE REQUIREMENTS:
- Use EXACT dataset names from "Available Datasets" above
- NEVER use 'dataset_id' as a key - use the actual dataset names listed
- NEVER assume 'df' exists - you must define it first: df = datasets['actual_name']
- Use Plotly for visualizations (plotly_white template)
- Perform actual calculations, never hardcode results

{output_instruction}

CRITICAL: PRODUCE ONLY ONE OUTPUT TYPE
- If analysis_type is "visualization": Create 'fig' variable ONLY
- If analysis_type is anything else (hypothesis_test, correlation, regression, etc.): Create 'result' variable ONLY
- NEVER create both 'fig' and 'result' - choose ONE based on what was requested

CRITICAL: DATAFRAME OPERATIONS & VARIABLE SCOPE
- When you add a column to a DataFrame, that column only exists in that specific DataFrame object
- If you create subsets, those subsets are COPIES
- ALWAYS add all derived columns BEFORE splitting data into subsets

DEFENSIVE PROGRAMMING:
- Before using a column, verify it exists: if 'column_name' in df.columns
- Use meaningful variable names

IMPORTANT: DO NOT include fig.show() or figure.show() in your code
- Figures are automatically displayed by the system
- Including .show() will cause unwanted browser tabs to open

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
            model=MODEL_NODE_4_CODE_GENERATION,
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

The requirements include an INTENT schema with:
- primary_goal: What the user wants to achieve (compare_groups, find_relationship, predict_outcome, etc.)
- output_format: How results should be presented (numeric, visualization, table, text)
- methodology: Specific technique used
- confidence: How confident we were in interpreting the question

Validate:
1. PLAUSIBILITY: Are numbers reasonable? Any impossible values (e.g., correlation > 1)?
2. METHODOLOGY: Was the approach appropriate for the primary_goal?
3. COMPLETENESS: Did this actually answer the question?
4. OUTPUT FORMAT MATCH: Does the actual output match the requested output_format?
   - If output_format is "numeric": Output should be numbers, statistics, p-values, coefficients - NOT visualizations
   - If output_format is "visualization": Output should be a chart/plot
   - If output_format is "table": Output should be a DataFrame or structured data
   - If code produced BOTH a result AND a visualization when only one was needed, flag as issue
5. ISSUES: Any errors, red flags, or concerns?

CRITICAL: Output format must match what was requested in intent.output_format.
A statistical test (primary_goal="compare_groups") with output_format="numeric" that produces a visualization is INVALID.

Return JSON:
{
  "is_valid": true/false,
  "issues_found": ["issue1", "issue2", ...],
  "confidence": 0.0-1.0,
  "recommendation": "accept/code_error/wrong_approach/data_issue/wrong_output_format",
  "reasoning": "..."
}"""

    result_str = ""
    if execution_result:
        result_str = execution_result.get("result_str", str(execution_result))
    
    user_prompt = f"""Question: {question}
Requirements: {json.dumps(requirements)}
Code: {code}
Execution Success: {execution_success}
Results: {result_str}
Error: {error if error else 'None'}

Evaluate these results."""

    try:
        response = client.chat.completions.create(
            model=MODEL_NODE_5_EVALUATION,
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

The requirements include an INTENT schema with:
- primary_goal: What the user wants to achieve
- output_format: How results should be presented (numeric, visualization, table, text)
- methodology: Specific technique used

Diagnose:
1. ROOT CAUSE: What's the fundamental problem?
2. ACTION: What should we do?
   - "rewrite_code": Code has bugs, wrong implementation, or wrong output format
   - "revise_requirements": We misinterpreted the user's intent (wrong primary_goal or output_format)
   - "reexamine_data": We misunderstood the data structure/quality

IMPORTANT: If the issue is "wrong_output_format":
- If the CODE produced wrong format but intent was correct: action="rewrite_code"
  - Guidance: "Produce ONLY 'result' variable" or "Produce ONLY 'fig' variable" based on intent.output_format
- If the INTENT was misinterpreted (user wanted visualization but we said numeric): action="revise_requirements"
  - Guidance: "Re-evaluate user intent - they may have wanted output_format='visualization'"

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
            model=MODEL_NODE_5A_REMEDIATION,
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
                    max_attempts_exceeded: bool = False,
                    alignment_caveats: list = None) -> str:
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
        alignment_caveats: Data quality caveats from Node 3 alignment check
    
    Returns:
        str: User-facing explanation
    """
    # Build caveats section for prompt
    caveats_section = ""
    if alignment_caveats:
        caveats_section = f"\nData Quality Caveats (MUST be mentioned in your response):\n" + "\n".join(f"- {c}" for c in alignment_caveats)
    
    system_prompt = """Explain the analysis results to a business user.

Provide:
1. DIRECT ANSWER: Clear answer to the user's question (or explain what went wrong)
2. KEY FINDINGS: Main insights from the analysis (if successful)
3. CONTEXT: What the numbers mean in practical terms
4. CAVEATS: Any limitations or concerns - IMPORTANT: If Data Quality Caveats are provided, you MUST 
   include them prominently in your response so the user understands the limitations of the analysis.

If max remediation attempts were exceeded:
- Clearly explain what error occurred
- Describe what we tried to fix it
- Suggest how the user might help resolve it

Use plain language suitable for non-technical audiences.
Be concise but thorough."""

    result_str = ""
    if execution_result:
        result_str = execution_result.get("result_str", str(execution_result))

    user_prompt = f"""Question: {question}
Evaluation: {json.dumps(evaluation) if evaluation else 'N/A'}
Results: {result_str}
Remediation Attempts: {total_remediations}
Max Attempts Exceeded: {max_attempts_exceeded}{caveats_section}

Explain the results to the user."""

    try:
        response = client.chat.completions.create(
            model=MODEL_NODE_6_EXPLANATION,
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
