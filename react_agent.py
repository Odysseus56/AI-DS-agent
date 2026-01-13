"""
ReAct Agent V2 - Tool-Based Data Scientist Agent

This module implements the V2 architecture as described in docs/AGENTIC_ARCHITECTURE_V2.md.
It replaces the rigid node-based graph with a flexible tool-based approach where a single
LLM dynamically decides which tools to use based on the task.

Key components:
- AgentState: Simple conversation-based state
- Tools: profile_data, write_code, execute_code, validate_results, explain_findings
- Agent Loop: ReAct-style reasoning (Observe -> Think -> Act -> repeat)
"""

import os
import json
from typing import Any, Optional, Literal
from dataclasses import dataclass, field
from datetime import datetime
from openai import OpenAI
import streamlit as st

from config import MODEL_SMART, MODEL_FAST
from code_executor import execute_unified_code
from data_analyzer import generate_data_summary, generate_compact_summary

# Initialize OpenAI client
try:
    api_key = st.secrets["OPENAI_API_KEY"]
except (KeyError, FileNotFoundError):
    api_key = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=api_key)


# =============================================================================
# STATE MANAGEMENT
# =============================================================================

@dataclass
class AgentState:
    """Simple conversation-based state for the ReAct agent."""
    
    # Current task
    question: str
    datasets: dict  # {name: {df, data_summary, ...}}
    
    # Conversation history (for LLM context)
    messages: list = field(default_factory=list)
    
    # Retrieved examples for this question
    retrieved_examples: list = field(default_factory=list)
    
    # Execution state
    current_code: Optional[str] = None
    current_results: Optional[dict] = None
    validation: Optional[dict] = None
    data_profile: Optional[dict] = None
    
    # Loop control
    iterations: int = 0
    max_iterations: int = 8
    
    # Tracking for safeguards
    failed_attempts: list = field(default_factory=list)
    tool_call_history: list = field(default_factory=list)


# =============================================================================
# EXECUTION LOG - Detailed tracking for debugging
# =============================================================================

@dataclass
class ToolCallLog:
    """Log entry for a single tool call."""
    tool_name: str
    arguments: dict
    result: dict
    duration_ms: float
    success: bool
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass 
class IterationLog:
    """Log entry for a single agent iteration."""
    iteration_num: int
    llm_reasoning: Optional[str]  # What the LLM said before tool calls
    tool_calls: list = field(default_factory=list)  # List of ToolCallLog
    raw_response: Optional[str] = None  # Full LLM response content
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ExecutionLog:
    """Complete execution log for a ReAct agent run."""
    question: str
    start_time: str
    end_time: Optional[str] = None
    
    # Iteration details
    iterations: list = field(default_factory=list)  # List of IterationLog
    
    # Context used
    retrieved_examples: list = field(default_factory=list)
    system_prompt: Optional[str] = None
    
    # Final outcome
    final_output_type: Optional[str] = None
    final_confidence: Optional[float] = None
    total_tool_calls: int = 0
    
    # Errors and issues
    loop_detected: bool = False
    forced_divergence: bool = False
    max_iterations_reached: bool = False
    errors: list = field(default_factory=list)
    
    def add_iteration(self, iteration: IterationLog):
        self.iterations.append(iteration)
        self.total_tool_calls += len(iteration.tool_calls)
    
    def to_markdown(self) -> str:
        """Convert execution log to markdown format for file logging."""
        md = []
        md.append(f"## ReAct Agent Execution")
        md.append(f"**Question:** {self.question}")
        md.append(f"**Started:** {self.start_time}")
        if self.end_time:
            md.append(f"**Ended:** {self.end_time}")
        md.append("")
        
        # Retrieved examples
        if self.retrieved_examples:
            md.append("### Retrieved Examples")
            for ex in self.retrieved_examples:
                md.append(f"- {ex.get('question', 'N/A')} → {ex.get('approach', 'N/A')}")
            md.append("")
        
        # Iterations
        for iteration in self.iterations:
            md.append(f"### Iteration {iteration.iteration_num}")
            md.append(f"*{iteration.timestamp}*")
            md.append("")
            
            if iteration.llm_reasoning:
                md.append(f"**LLM Reasoning:**")
                md.append(f"> {iteration.llm_reasoning}")
                md.append("")
            
            for tc in iteration.tool_calls:
                status = "✓" if tc.success else "✗"
                md.append(f"**Tool Call:** `{tc.tool_name}` {status} ({tc.duration_ms:.0f}ms)")
                md.append("")
                
                # Format arguments as proper JSON block
                md.append("**Arguments:**")
                md.append("```json")
                md.append(json.dumps(tc.arguments, indent=2, default=str))
                md.append("```")
                md.append("")
                
                # Format result as proper JSON block
                md.append("**Result:**")
                md.append("```json")
                md.append(json.dumps(tc.result, indent=2, default=str))
                md.append("```")
                
                if tc.error:
                    md.append(f"**Error:** {tc.error}")
                md.append("")
        
        # Final summary
        md.append("### Execution Summary")
        md.append(f"- **Output Type:** {self.final_output_type or 'N/A'}")
        md.append(f"- **Confidence:** {self.final_confidence or 'N/A'}")
        md.append(f"- **Total Iterations:** {len(self.iterations)}")
        md.append(f"- **Total Tool Calls:** {self.total_tool_calls}")
        
        if self.loop_detected:
            md.append(f"- **⚠️ Loop Detected:** Yes")
        if self.forced_divergence:
            md.append(f"- **⚠️ Forced Divergence:** Yes")
        if self.max_iterations_reached:
            md.append(f"- **⚠️ Max Iterations Reached:** Yes")
        
        if self.errors:
            md.append("")
            md.append("### Errors")
            for err in self.errors:
                md.append(f"- {err}")
        
        md.append("")
        md.append("---")
        md.append("")
        
        return "\n".join(md)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "question": self.question,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "iterations": [
                {
                    "iteration_num": it.iteration_num,
                    "llm_reasoning": it.llm_reasoning,
                    "tool_calls": [
                        {
                            "tool_name": tc.tool_name,
                            "arguments": tc.arguments,
                            "result": tc.result,
                            "duration_ms": tc.duration_ms,
                            "success": tc.success,
                            "error": tc.error
                        }
                        for tc in it.tool_calls
                    ]
                }
                for it in self.iterations
            ],
            "retrieved_examples": self.retrieved_examples,
            "final_output_type": self.final_output_type,
            "final_confidence": self.final_confidence,
            "total_tool_calls": self.total_tool_calls,
            "loop_detected": self.loop_detected,
            "forced_divergence": self.forced_divergence,
            "max_iterations_reached": self.max_iterations_reached,
            "errors": self.errors
        }


@dataclass
class FinalOutput:
    """Structured final output from the agent."""
    
    # Required
    answer: str
    confidence: float
    output_type: Literal["analysis", "visualization", "explanation", "error"]
    
    # Optional
    result: Any = None
    figures: list = field(default_factory=list)
    code: Optional[str] = None
    
    # Always included
    caveats: list = field(default_factory=list)
    reasoning_trace: list = field(default_factory=list)
    
    # Detailed execution log for debugging
    execution_log: Optional[ExecutionLog] = None


# =============================================================================
# TOOL DEFINITIONS
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
    """
    profile = {
        "datasets": {},
        "columns_found": [],
        "columns_missing": [],
        "quality_issues": [],
        "can_proceed": True
    }
    
    for name, dataset_info in state.datasets.items():
        df = dataset_info['df']
        
        dataset_profile = {
            "shape": f"{df.shape[0]} rows x {df.shape[1]} columns",
            "columns": {}
        }
        
        # Profile each column
        cols_to_profile = columns if columns else df.columns.tolist()
        
        for col in cols_to_profile:
            if col in df.columns:
                profile["columns_found"].append(col)
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
            else:
                profile["columns_missing"].append(col)
        
        profile["datasets"][name] = dataset_profile
    
    # Check requirements if provided
    if check_requirements:
        for req in check_requirements:
            # Simple requirement checking - can be expanded
            profile["requirements_checked"] = check_requirements
    
    # Determine if we can proceed
    if profile["columns_missing"]:
        profile["can_proceed"] = False
        profile["blocking_issue"] = f"Required columns not found: {profile['columns_missing']}"
    
    return profile


def tool_write_code(state: AgentState, approach: str, output_var: str) -> dict:
    """
    Tool 2: Generate Python code to perform the analysis.
    
    Uses LLM to generate code based on the approach description.
    """
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
- Libraries available: pandas (pd), numpy (np), scipy.stats (stats), sklearn, plotly.express (px), plotly.graph_objects (go)
- For single dataset, you can also use: df = datasets['dataset_name']

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
    system_prompt = """You are a data science reviewer validating analysis results.

Check:
1. PLAUSIBILITY: Are the numbers reasonable? Any impossible values?
2. METHODOLOGY: Was the approach appropriate for the question?
3. COMPLETENESS: Does this actually answer the question?
4. ISSUES: Any red flags or concerns?

Return JSON:
{
    "is_valid": true/false,
    "confidence": 0.0-1.0,
    "issues": ["issue1", "issue2"],
    "suggestions": ["suggestion1"]
}"""

    user_prompt = f"""Question: {state.question}

Results: {results_summary}

Code used: {state.current_code[:500] if state.current_code else 'N/A'}...

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


# =============================================================================
# LOOP DETECTION & SAFEGUARDS
# =============================================================================

def detect_loop(state: AgentState) -> bool:
    """Check if agent is stuck in a loop."""
    if len(state.tool_call_history) < 4:
        return False
    
    # Check last 4 tool calls
    recent = state.tool_call_history[-4:]
    
    # If same tool called 3+ times in a row with errors
    if all(t["name"] == recent[0]["name"] for t in recent):
        error_count = sum(1 for t in recent if t.get("had_error", False))
        if error_count >= 2:
            return True
    
    return False


def get_divergence_message() -> str:
    """Message to inject when loop is detected."""
    return """LOOP DETECTED: You've tried the same approach multiple times without success.

You MUST try a DIFFERENT approach. Options:
1. Use a completely different statistical method
2. Simplify the analysis (fewer variables, simpler aggregation)
3. Explain why this analysis cannot be performed with available data

Do NOT repeat the same tool call."""


# =============================================================================
# CORE AGENT LOOP
# =============================================================================

def build_system_prompt(state: AgentState) -> str:
    """Build the system prompt with context."""
    
    # Get data summary
    data_summary = ""
    for name, dataset_info in state.datasets.items():
        data_summary += f"\nDataset '{name}':\n{dataset_info.get('data_summary', 'No summary available')[:1000]}\n"
    
    # Get examples (if any)
    examples_text = ""
    if state.retrieved_examples:
        examples_text = "\n\nSIMILAR EXAMPLES:\n"
        for ex in state.retrieved_examples[:2]:
            examples_text += f"- Question: {ex.get('question', '')}\n"
            examples_text += f"  Approach: {ex.get('approach', '')}\n"
    
    return f"""You are an expert data scientist assistant. Help the user analyze their data.

AVAILABLE DATA:
{data_summary}
{examples_text}

HOW TO WORK:
1. First, use profile_data to understand what columns are available
2. Then, use write_code to generate analysis code
3. Use execute_code to run the code
4. Use validate_results to check the results make sense
5. Finally, use explain_findings to prepare your response

IMPORTANT:
- Always profile data before writing code
- Always validate results before explaining
- If code fails, analyze the error and try a different approach
- Define 'result' for numeric/table output, 'fig' for visualizations
- Only use 'fig' if user explicitly asks to "show", "plot", or "visualize"

When you have validated results and are ready to respond, provide your final answer directly without calling more tools."""


def run_agent(question: str, datasets: dict, max_iterations: int = 8) -> FinalOutput:
    """
    Main agent loop - ReAct style reasoning.
    
    Args:
        question: User's question
        datasets: Available datasets {name: {df, data_summary, ...}}
        max_iterations: Maximum iterations before graceful degradation
    
    Returns:
        FinalOutput with answer, results, metadata, and detailed execution log
    """
    import time
    
    # Initialize state
    state = AgentState(
        question=question,
        datasets=datasets,
        max_iterations=max_iterations
    )
    
    # Initialize execution log
    exec_log = ExecutionLog(
        question=question,
        start_time=datetime.now().isoformat()
    )
    
    # Retrieve similar examples
    state.retrieved_examples = retrieve_examples(question)
    exec_log.retrieved_examples = state.retrieved_examples
    
    # Build initial system prompt
    system_prompt = build_system_prompt(state)
    exec_log.system_prompt = system_prompt
    
    # Initialize conversation
    state.messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]
    
    reasoning_trace = []
    
    while state.iterations < state.max_iterations:
        iteration_num = state.iterations + 1
        current_iteration = IterationLog(iteration_num=iteration_num, llm_reasoning=None)
        
        # Check for loops
        if detect_loop(state):
            state.messages.append({
                "role": "system",
                "content": get_divergence_message()
            })
            reasoning_trace.append("Loop detected - forcing divergence")
            exec_log.loop_detected = True
            exec_log.forced_divergence = True
        
        # Call LLM with tools
        llm_start = time.time()
        response = client.chat.completions.create(
            model=MODEL_SMART,
            messages=state.messages,
            tools=TOOLS,
            tool_choice="auto",
            max_tokens=2000,
            temperature=0.2
        )
        llm_duration_ms = (time.time() - llm_start) * 1000
        
        assistant_message = response.choices[0].message
        current_iteration.raw_response = assistant_message.content
        current_iteration.llm_reasoning = assistant_message.content
        
        # Check if LLM wants to call a tool
        if assistant_message.tool_calls:
            # Process tool calls
            state.messages.append({
                "role": "assistant",
                "content": assistant_message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in assistant_message.tool_calls
                ]
            })
            
            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    tool_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}
                
                reasoning_trace.append(f"Tool: {tool_name}")
                
                # Execute tool with timing
                tool_start = time.time()
                tool_result = execute_tool(state, tool_name, tool_args)
                tool_duration_ms = (time.time() - tool_start) * 1000
                
                # Determine if tool had error
                had_error = "error" in tool_result and tool_result["error"]
                error_msg = tool_result.get("error") if had_error else None
                
                # Log tool call
                tool_log = ToolCallLog(
                    tool_name=tool_name,
                    arguments=tool_args,
                    result=tool_result,
                    duration_ms=tool_duration_ms,
                    success=not had_error,
                    error=error_msg
                )
                current_iteration.tool_calls.append(tool_log)
                
                # Track tool call for loop detection
                state.tool_call_history.append({
                    "name": tool_name,
                    "had_error": had_error
                })
                
                # Add tool result to conversation
                state.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result, default=str)[:4000]
                })
            
            # Add iteration to log
            exec_log.add_iteration(current_iteration)
        
        else:
            # LLM provided final answer (no tool calls)
            final_answer = assistant_message.content
            reasoning_trace.append("Final answer provided")
            
            # Log final iteration (no tool calls)
            exec_log.add_iteration(current_iteration)
            
            # Enforce mandatory validation
            if state.current_results and not state.validation:
                # Force validation
                tool_start = time.time()
                validation = tool_validate_results(
                    state,
                    results_summary=state.current_results.get("result_str", "")
                )
                tool_duration_ms = (time.time() - tool_start) * 1000
                state.validation = validation
                
                # Log forced validation
                forced_validation_log = ToolCallLog(
                    tool_name="validate_results (forced)",
                    arguments={"results_summary": state.current_results.get("result_str", "")[:100]},
                    result=validation,
                    duration_ms=tool_duration_ms,
                    success=validation.get("is_valid", True)
                )
                current_iteration.tool_calls.append(forced_validation_log)
                
                if not validation.get("is_valid", True):
                    # Validation failed - continue loop
                    state.messages.append({
                        "role": "system",
                        "content": f"Validation failed: {validation.get('issues', [])}. Please address these issues."
                    })
                    state.iterations += 1
                    continue
            
            # Finalize execution log
            exec_log.end_time = datetime.now().isoformat()
            exec_log.final_output_type = determine_output_type(state)
            exec_log.final_confidence = state.validation.get("confidence", 0.7) if state.validation else 0.5
            
            # Build final output
            return FinalOutput(
                answer=final_answer,
                confidence=state.validation.get("confidence", 0.7) if state.validation else 0.5,
                output_type=determine_output_type(state),
                result=state.current_results.get("result") if state.current_results else None,
                figures=state.current_results.get("figures", []) if state.current_results else [],
                code=state.current_code,
                caveats=state.validation.get("issues", []) if state.validation else [],
                reasoning_trace=reasoning_trace,
                execution_log=exec_log
            )
        
        state.iterations += 1
    
    # Max iterations reached - graceful degradation
    exec_log.max_iterations_reached = True
    exec_log.end_time = datetime.now().isoformat()
    return graceful_degradation(state, reasoning_trace, exec_log)


def determine_output_type(state: AgentState) -> str:
    """Determine the output type based on state."""
    if state.current_results:
        result_type = state.current_results.get("output_type", "analysis")
        if result_type == "visualization":
            return "visualization"
        return "analysis"
    return "explanation"


def graceful_degradation(state: AgentState, reasoning_trace: list, exec_log: ExecutionLog) -> FinalOutput:
    """Handle max iterations reached."""
    
    exec_log.final_output_type = "error"
    exec_log.final_confidence = 0.3 if state.current_results else 0.1
    
    # Try to provide best available answer
    if state.current_results and state.current_results.get("success"):
        exec_log.final_output_type = determine_output_type(state)
        return FinalOutput(
            answer=f"I was able to perform some analysis, but couldn't fully complete the task. Here's what I found:\n\n{state.current_results.get('result_str', 'No results available')}",
            confidence=0.3,
            output_type=determine_output_type(state),
            result=state.current_results.get("result"),
            figures=state.current_results.get("figures", []),
            code=state.current_code,
            caveats=["Analysis may be incomplete due to complexity"],
            reasoning_trace=reasoning_trace,
            execution_log=exec_log
        )
    
    return FinalOutput(
        answer="I apologize, but I wasn't able to complete this analysis. The question may require a different approach or the data may not support this type of analysis.",
        confidence=0.1,
        output_type="error",
        caveats=["Could not complete analysis within iteration limit"],
        reasoning_trace=reasoning_trace,
        execution_log=exec_log
    )


# =============================================================================
# STREAMING AGENT - Yields iterations as they happen
# =============================================================================

def run_agent_streaming(question: str, datasets: dict, max_iterations: int = 8):
    """
    Streaming version of run_agent that yields iterations as they happen.
    
    Yields:
        tuple: (iteration_log, exec_log, final_output_or_none)
        - During execution: (IterationLog, ExecutionLog, None)
        - On completion: (None, ExecutionLog, FinalOutput)
    """
    import time
    
    # Initialize state
    state = AgentState(
        question=question,
        datasets=datasets,
        max_iterations=max_iterations
    )
    
    # Initialize execution log
    exec_log = ExecutionLog(
        question=question,
        start_time=datetime.now().isoformat()
    )
    
    # Retrieve similar examples
    state.retrieved_examples = retrieve_examples(question)
    exec_log.retrieved_examples = state.retrieved_examples
    
    # Build initial system prompt
    system_prompt = build_system_prompt(state)
    exec_log.system_prompt = system_prompt
    
    # Initialize conversation
    state.messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]
    
    reasoning_trace = []
    
    while state.iterations < state.max_iterations:
        iteration_num = state.iterations + 1
        current_iteration = IterationLog(iteration_num=iteration_num, llm_reasoning=None)
        
        # Check for loops
        if detect_loop(state):
            state.messages.append({
                "role": "system",
                "content": get_divergence_message()
            })
            reasoning_trace.append("Loop detected - forcing divergence")
            exec_log.loop_detected = True
            exec_log.forced_divergence = True
        
        # Call LLM with tools
        llm_start = time.time()
        response = client.chat.completions.create(
            model=MODEL_SMART,
            messages=state.messages,
            tools=TOOLS,
            tool_choice="auto",
            max_tokens=2000,
            temperature=0.2
        )
        llm_duration_ms = (time.time() - llm_start) * 1000
        
        assistant_message = response.choices[0].message
        current_iteration.raw_response = assistant_message.content
        current_iteration.llm_reasoning = assistant_message.content
        
        # Check if LLM wants to call a tool
        if assistant_message.tool_calls:
            # Process tool calls
            state.messages.append({
                "role": "assistant",
                "content": assistant_message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in assistant_message.tool_calls
                ]
            })
            
            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    tool_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}
                
                reasoning_trace.append(f"Tool: {tool_name}")
                
                # Execute tool with timing
                tool_start = time.time()
                tool_result = execute_tool(state, tool_name, tool_args)
                tool_duration_ms = (time.time() - tool_start) * 1000
                
                # Determine if tool had error
                had_error = "error" in tool_result and tool_result["error"]
                error_msg = tool_result.get("error") if had_error else None
                
                # Log tool call
                tool_log = ToolCallLog(
                    tool_name=tool_name,
                    arguments=tool_args,
                    result=tool_result,
                    duration_ms=tool_duration_ms,
                    success=not had_error,
                    error=error_msg
                )
                current_iteration.tool_calls.append(tool_log)
                
                # Track tool call for loop detection
                state.tool_call_history.append({
                    "name": tool_name,
                    "had_error": had_error
                })
                
                # Add tool result to conversation
                state.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result, default=str)[:4000]
                })
            
            # Add iteration to log and yield it
            exec_log.add_iteration(current_iteration)
            yield (current_iteration, exec_log, None)
        
        else:
            # LLM provided final answer (no tool calls)
            final_answer = assistant_message.content
            reasoning_trace.append("Final answer provided")
            
            # Log final iteration (no tool calls)
            exec_log.add_iteration(current_iteration)
            
            # Enforce mandatory validation
            if state.current_results and not state.validation:
                # Force validation
                tool_start = time.time()
                validation = tool_validate_results(
                    state,
                    results_summary=state.current_results.get("result_str", "")
                )
                tool_duration_ms = (time.time() - tool_start) * 1000
                state.validation = validation
                
                # Log forced validation
                forced_validation_log = ToolCallLog(
                    tool_name="validate_results (forced)",
                    arguments={"results_summary": state.current_results.get("result_str", "")[:100]},
                    result=validation,
                    duration_ms=tool_duration_ms,
                    success=validation.get("is_valid", True)
                )
                current_iteration.tool_calls.append(forced_validation_log)
                
                if not validation.get("is_valid", True):
                    # Validation failed - continue loop
                    state.messages.append({
                        "role": "system",
                        "content": f"Validation failed: {validation.get('issues', [])}. Please address these issues."
                    })
                    yield (current_iteration, exec_log, None)
                    state.iterations += 1
                    continue
            
            # Finalize execution log
            exec_log.end_time = datetime.now().isoformat()
            exec_log.final_output_type = determine_output_type(state)
            exec_log.final_confidence = state.validation.get("confidence", 0.7) if state.validation else 0.5
            
            # Build final output
            final_output = FinalOutput(
                answer=final_answer,
                confidence=state.validation.get("confidence", 0.7) if state.validation else 0.5,
                output_type=determine_output_type(state),
                result=state.current_results.get("result") if state.current_results else None,
                figures=state.current_results.get("figures", []) if state.current_results else [],
                code=state.current_code,
                caveats=state.validation.get("issues", []) if state.validation else [],
                reasoning_trace=reasoning_trace,
                execution_log=exec_log
            )
            yield (None, exec_log, final_output)
            return
        
        state.iterations += 1
    
    # Max iterations reached - graceful degradation
    exec_log.max_iterations_reached = True
    exec_log.end_time = datetime.now().isoformat()
    final_output = graceful_degradation(state, reasoning_trace, exec_log)
    yield (None, exec_log, final_output)


# =============================================================================
# EXAMPLE LIBRARY (Placeholder - will be expanded)
# =============================================================================

EXAMPLE_LIBRARY = [
    {
        "id": "comparison_proportions_01",
        "question": "Is there a significant difference in conversion rates between A and B?",
        "approach": "Use chi-square test to compare proportions between two groups",
        "output_var": "result",
        "tags": ["comparison", "proportions", "chi-square"]
    },
    {
        "id": "comparison_continuous_01",
        "question": "Do customers in segment A have higher average spend than segment B?",
        "approach": "Use independent t-test to compare means between two groups",
        "output_var": "result",
        "tags": ["comparison", "continuous", "t-test"]
    },
    {
        "id": "visualization_distribution_01",
        "question": "Show me the distribution of customer ages",
        "approach": "Create a histogram using Plotly",
        "output_var": "fig",
        "tags": ["visualization", "distribution", "histogram"]
    },
    {
        "id": "correlation_01",
        "question": "What's the correlation between price and quantity?",
        "approach": "Calculate Pearson correlation coefficient",
        "output_var": "result",
        "tags": ["relationship", "correlation"]
    },
    {
        "id": "aggregation_01",
        "question": "What's the average revenue by region?",
        "approach": "Group by region and calculate mean revenue",
        "output_var": "result",
        "tags": ["description", "aggregation", "groupby"]
    }
]


def retrieve_examples(question: str, top_k: int = 2) -> list:
    """
    Retrieve relevant examples based on question similarity.
    
    For MVP, uses simple keyword matching. Will be upgraded to semantic search.
    """
    question_lower = question.lower()
    
    scored_examples = []
    for example in EXAMPLE_LIBRARY:
        score = 0
        
        # Check tags
        for tag in example.get("tags", []):
            if tag in question_lower:
                score += 2
        
        # Check question similarity (simple keyword overlap)
        example_words = set(example["question"].lower().split())
        question_words = set(question_lower.split())
        overlap = len(example_words & question_words)
        score += overlap
        
        # Boost visualization examples if user asks to "show" or "plot"
        if any(word in question_lower for word in ["show", "plot", "visualize", "chart", "graph"]):
            if example.get("output_var") == "fig":
                score += 3
        
        scored_examples.append((score, example))
    
    # Sort by score and return top_k
    scored_examples.sort(key=lambda x: x[0], reverse=True)
    return [ex for score, ex in scored_examples[:top_k] if score > 0]


# =============================================================================
# CONVENIENCE FUNCTION FOR INTEGRATION
# =============================================================================

def process_question_v2(question: str, datasets: dict) -> dict:
    """
    Process a question using the V2 ReAct agent (non-streaming).
    
    This is the main entry point for integration with the Streamlit UI.
    
    Args:
        question: User's question
        datasets: Available datasets {name: {df, data_summary, ...}}
    
    Returns:
        dict with keys: answer, output_type, result, figures, code, confidence, caveats, execution_log
    """
    output = run_agent(question, datasets)
    
    return {
        "answer": output.answer,
        "output_type": output.output_type,
        "result": output.result,
        "figures": output.figures,
        "code": output.code,
        "confidence": output.confidence,
        "caveats": output.caveats,
        "reasoning_trace": output.reasoning_trace,
        "execution_log": output.execution_log
    }


def process_question_v2_streaming(question: str, datasets: dict):
    """
    Streaming version that yields iterations as they happen.
    
    Yields:
        dict with keys depending on state:
        - During execution: {"type": "iteration", "iteration": IterationLog, "exec_log": ExecutionLog}
        - On completion: {"type": "final", "result": dict, "exec_log": ExecutionLog}
    """
    for iteration, exec_log, final_output in run_agent_streaming(question, datasets):
        if final_output is not None:
            # Final result
            yield {
                "type": "final",
                "result": {
                    "answer": final_output.answer,
                    "output_type": final_output.output_type,
                    "result": final_output.result,
                    "figures": final_output.figures,
                    "code": final_output.code,
                    "confidence": final_output.confidence,
                    "caveats": final_output.caveats,
                    "reasoning_trace": final_output.reasoning_trace,
                    "execution_log": final_output.execution_log
                },
                "exec_log": exec_log
            }
        else:
            # Intermediate iteration
            yield {
                "type": "iteration",
                "iteration": iteration,
                "exec_log": exec_log
            }
