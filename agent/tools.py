"""
Agent Tools - Tool definitions and implementations for the ReAct agent.

This module contains:
- TOOLS: OpenAI function calling definitions
- Tool implementations: profile_data, write_code, execute_code, validate_results, explain_findings
- execute_tool: Dispatcher for tool execution
"""

import json
from typing import Optional

from config import MODEL_SMART
from code_executor import execute_unified_code

from .state import AgentState
from .llm_client import get_openai_client


# =============================================================================
# TOOL DEFINITIONS (OpenAI Function Calling Format)
# =============================================================================

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "profile_data",
            "description": "Examine data to understand what columns are available and assess data quality. Use this FIRST to understand what data you have before writing code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific columns to profile in detail. If empty, profiles all columns at a high level."
                    },
                    "check_requirements": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific requirements to validate (e.g., 'age column must be numeric')"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_code",
            "description": "Generate Python code to perform the analysis. The code must define either 'result' (for numeric/table output) or 'fig' (for visualization).",
            "parameters": {
                "type": "object",
                "properties": {
                    "approach": {
                        "type": "string",
                        "description": "Description of the analysis approach to implement"
                    },
                    "output_var": {
                        "type": "string",
                        "enum": ["result", "fig"],
                        "description": "Which variable to define: 'result' for numeric/table output, 'fig' for Plotly visualization"
                    }
                },
                "required": ["approach", "output_var"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_code",
            "description": "Run the generated Python code and get results. Call this after write_code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "The Python code to execute"
                    }
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "validate_results",
            "description": "Check if the results are correct, sensible, and actually answer the question. Call this after successful code execution.",
            "parameters": {
                "type": "object",
                "properties": {
                    "results_summary": {
                        "type": "string",
                        "description": "Summary of the results to validate"
                    }
                },
                "required": ["results_summary"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "explain_findings",
            "description": "Generate a user-friendly explanation of the results. Call this as the final step before responding.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key_findings": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of key findings to explain"
                    },
                    "caveats": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Any limitations or caveats to mention"
                    }
                },
                "required": ["key_findings"]
            }
        }
    }
]


# =============================================================================
# TOOL IMPLEMENTATIONS
# =============================================================================

def tool_profile_data(state: AgentState, columns: list = None, check_requirements: list = None) -> dict:
    """
    Tool 1: Examine data to understand what's available and assess quality.
    
    Returns information about available columns, data types, missing values, etc.
    A column is considered "found" if it exists in ANY dataset.
    """
    profile = {
        "datasets": {},
        "columns_found": set(),  # Use set to avoid duplicates
        "columns_missing": set(),
        "quality_issues": [],
        "can_proceed": True
    }
    
    # Track which columns exist in which datasets
    columns_by_dataset = {}
    
    for name, dataset_info in state.datasets.items():
        df = dataset_info['df']
        columns_by_dataset[name] = set(df.columns.tolist())
        
        dataset_profile = {
            "shape": f"{df.shape[0]} rows x {df.shape[1]} columns",
            "columns": {}
        }
        
        # Profile each column
        cols_to_profile = columns if columns else df.columns.tolist()
        
        for col in cols_to_profile:
            if col in df.columns:
                profile["columns_found"].add(col)
                col_info = {
                    "dtype": str(df[col].dtype),
                    "missing": int(df[col].isnull().sum()),
                    "missing_pct": round(df[col].isnull().sum() / len(df) * 100, 1),
                    "unique": int(df[col].nunique())
                }
                
                # Add type-specific info
                if df[col].dtype in ['int64', 'float64']:
                    col_info["min"] = float(df[col].min()) if not df[col].isnull().all() else None
                    col_info["max"] = float(df[col].max()) if not df[col].isnull().all() else None
                    col_info["mean"] = float(df[col].mean()) if not df[col].isnull().all() else None
                else:
                    # Sample values for categorical
                    col_info["sample_values"] = df[col].dropna().head(5).tolist()
                
                dataset_profile["columns"][col] = col_info
                
                # Check for quality issues
                if col_info["missing_pct"] > 30:
                    profile["quality_issues"].append(f"{col}: {col_info['missing_pct']}% missing values")
        
        profile["datasets"][name] = dataset_profile
    
    # Determine truly missing columns (not found in ANY dataset)
    if columns:
        all_available_columns = set()
        for cols in columns_by_dataset.values():
            all_available_columns.update(cols)
        
        for col in columns:
            if col not in all_available_columns:
                profile["columns_missing"].add(col)
    
    # Check requirements if provided
    if check_requirements:
        profile["requirements_checked"] = check_requirements
    
    # Convert sets to lists for JSON serialization
    profile["columns_found"] = list(profile["columns_found"])
    profile["columns_missing"] = list(profile["columns_missing"])
    
    # Determine if we can proceed - only block if columns are truly missing from ALL datasets
    if profile["columns_missing"]:
        profile["can_proceed"] = False
        profile["blocking_issue"] = f"Required columns not found in any dataset: {profile['columns_missing']}"
    
    return profile


def tool_write_code(state: AgentState, approach: str, output_var: str) -> dict:
    """
    Tool 2: Generate Python code to perform the analysis.
    
    Uses LLM to generate code based on the approach description.
    """
    client = get_openai_client()
    
    # Build context about available data
    data_context = ""
    for name, dataset_info in state.datasets.items():
        df = dataset_info['df']
        data_context += f"\nDataset '{name}':\n"
        data_context += f"  Columns: {list(df.columns)}\n"
        data_context += f"  Shape: {df.shape}\n"
        if state.data_profile and name in state.data_profile.get("datasets", {}):
            data_context += f"  Profile: {json.dumps(state.data_profile['datasets'][name]['columns'], indent=2)}\n"
    
    # Build failed attempts context
    failed_context = ""
    if state.failed_attempts:
        failed_context = "\n\nPREVIOUS FAILED ATTEMPTS (do NOT repeat these):\n"
        for attempt in state.failed_attempts[-3:]:  # Last 3 failures
            failed_context += f"- Approach: {attempt.get('approach', 'unknown')}\n"
            failed_context += f"  Error: {attempt.get('error', 'unknown')}\n"
    
    system_prompt = f"""You are an expert data analyst writing Python code.

AVAILABLE DATA:
{data_context}

EXECUTION ENVIRONMENT:
- Access datasets using: datasets['dataset_name'] to get the DataFrame
- Libraries available: pandas (pd), numpy (np), scipy.stats (stats), sklearn, statsmodels, plotly.express (px), plotly.graph_objects (go)
- For single dataset, you can also use: df = datasets['dataset_name']

IMPORTANT API NOTES:
- sklearn OneHotEncoder: use sparse_output=False (not sparse=False, which is deprecated)
- For regression with p-values, use statsmodels.api.OLS, not sklearn LinearRegression
- When returning regression results, include coefficients, p-values, and confidence intervals

OUTPUT REQUIREMENT:
You MUST define a variable called '{output_var}':
- If output_var is 'result': Store numeric results, statistics, or DataFrame
- If output_var is 'fig': Store a Plotly figure

CODE STYLE:
- Use exact column names from the data profile
- Handle potential missing values appropriately
- Keep code concise and focused
{failed_context}

Return ONLY the Python code, no explanations."""

    user_prompt = f"""Write Python code to: {approach}

The code must define '{output_var}' as the output variable."""

    response = client.chat.completions.create(
        model=MODEL_SMART,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=1500,
        temperature=0.2
    )
    
    code = response.choices[0].message.content
    
    # Clean up code (remove markdown code blocks if present)
    if code.startswith("```python"):
        code = code[9:]
    if code.startswith("```"):
        code = code[3:]
    if code.endswith("```"):
        code = code[:-3]
    code = code.strip()
    
    return {
        "code": code,
        "approach": approach,
        "output_var": output_var
    }


def tool_execute_code(state: AgentState, code: str) -> dict:
    """
    Tool 3: Run the generated Python code in a sandboxed environment.
    
    Reuses the existing execute_unified_code function.
    """
    success, output, error = execute_unified_code(code, state.datasets)
    
    if success:
        return {
            "success": True,
            "output_type": output.get("type", "unknown"),
            "result_str": output.get("result_str", ""),
            "result": output.get("result"),
            "figures": output.get("figures", []),
            "error": None
        }
    else:
        return {
            "success": False,
            "output_type": "error",
            "result_str": "",
            "result": None,
            "figures": [],
            "error": error
        }


def tool_validate_results(state: AgentState, results_summary: str) -> dict:
    """
    Tool 4: Check if results are correct, sensible, and answer the question.
    
    Uses LLM to evaluate the results.
    """
    client = get_openai_client()
    
    system_prompt = """You are a pragmatic data science reviewer validating analysis results.

VALIDATION CRITERIA (in order of importance):
1. CORRECTNESS: Are the numbers plausible? No impossible values (e.g., negative counts, percentages > 100)?
2. ANSWERS THE QUESTION: Does the result directly address what was asked?
3. APPROPRIATE METHOD: Is the statistical approach reasonable for this type of question?

VALIDATION GUIDELINES:
- Set is_valid=true if the analysis is fundamentally sound and answers the question
- Set is_valid=false ONLY for critical issues: wrong test, impossible values, or doesn't answer the question
- Put nice-to-haves (parallel trends, effect sizes, robustness checks) in "suggestions", NOT "issues"
- Confidence should reflect how well the analysis answers the question:
  - 0.9+: Solid analysis with clear answer
  - 0.7-0.9: Good analysis, minor improvements possible
  - 0.5-0.7: Acceptable but has notable gaps
  - <0.5: Significant problems

Return JSON:
{
    "is_valid": true/false,
    "confidence": 0.0-1.0,
    "issues": ["only critical blocking issues"],
    "suggestions": ["nice-to-have improvements"]
}"""

    user_prompt = f"""Question: {state.question}

Results: {results_summary}

Code used:
{state.current_code if state.current_code else 'N/A'}

Validate these results."""

    response = client.chat.completions.create(
        model=MODEL_SMART,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=500,
        temperature=0.2,
        response_format={"type": "json_object"}
    )
    
    try:
        validation = json.loads(response.choices[0].message.content)
    except json.JSONDecodeError:
        validation = {
            "is_valid": True,
            "confidence": 0.5,
            "issues": ["Could not parse validation response"],
            "suggestions": []
        }
    
    return validation


def tool_explain_findings(state: AgentState, key_findings: list, caveats: list = None) -> dict:
    """
    Tool 5: Generate a user-friendly explanation of the results.
    """
    client = get_openai_client()
    
    system_prompt = """You are a data scientist explaining analysis results to a business user.

Guidelines:
- Use clear, non-technical language
- Lead with the key insight that answers their question
- Mention any important caveats
- Be concise but complete"""

    findings_text = "\n".join(f"- {f}" for f in key_findings)
    caveats_text = "\n".join(f"- {c}" for c in (caveats or []))
    
    user_prompt = f"""Question: {state.question}

Key Findings:
{findings_text}

{f'Caveats:{chr(10)}{caveats_text}' if caveats else ''}

Write a clear explanation for the user."""

    response = client.chat.completions.create(
        model=MODEL_SMART,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=800,
        temperature=0.3
    )
    
    return {
        "explanation": response.choices[0].message.content,
        "key_findings": key_findings,
        "caveats": caveats or []
    }


# =============================================================================
# TOOL EXECUTION DISPATCHER
# =============================================================================

def execute_tool(state: AgentState, tool_name: str, tool_args: dict) -> dict:
    """Execute a tool and return the result."""
    
    if tool_name == "profile_data":
        result = tool_profile_data(
            state,
            columns=tool_args.get("columns"),
            check_requirements=tool_args.get("check_requirements")
        )
        state.data_profile = result
        return result
    
    elif tool_name == "write_code":
        result = tool_write_code(
            state,
            approach=tool_args["approach"],
            output_var=tool_args["output_var"]
        )
        state.current_code = result["code"]
        return result
    
    elif tool_name == "execute_code":
        result = tool_execute_code(state, code=tool_args["code"])
        if result["success"]:
            state.current_results = result
        else:
            # Track failed attempt
            state.failed_attempts.append({
                "approach": state.current_code[:200] if state.current_code else "unknown",
                "error": result["error"]
            })
        return result
    
    elif tool_name == "validate_results":
        result = tool_validate_results(
            state,
            results_summary=tool_args["results_summary"]
        )
        state.validation = result
        return result
    
    elif tool_name == "explain_findings":
        result = tool_explain_findings(
            state,
            key_findings=tool_args["key_findings"],
            caveats=tool_args.get("caveats")
        )
        return result
    
    else:
        return {"error": f"Unknown tool: {tool_name}"}
