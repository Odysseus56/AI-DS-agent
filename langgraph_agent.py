"""
MVP LangGraph Architecture - Robust Data Scientist Agent

This implements the architecture from PROPOSED_ARCHITECTURE.md with:
- Node 0: Question Understanding
- Node 1A: Provide Explanation (conceptual questions)
- Node 1B: Formulate Requirements (data work)
- Node 2: Data Summary & Profiling
- Node 3: Alignment Check
- Node 4: Generate & Execute Code
- Node 5: Evaluate Results
- Node 5a: Remediation Planning
- Node 6: Explain Results
"""

from typing import TypedDict, Literal, Optional, Any, Dict
from langgraph.graph import StateGraph, END
from llm_client import (
    understand_question,
    provide_explanation,
    formulate_requirements,
    profile_data,
    check_alignment,
    generate_analysis_code,
    evaluate_results,
    plan_remediation,
    explain_results
)
from code_executor import execute_unified_code
from data_analyzer import generate_concise_summary
from config import MAX_CODE_ATTEMPTS, MAX_ALIGNMENT_ITERATIONS, MAX_TOTAL_REMEDIATIONS


class MVPAgentState(TypedDict):
    # Input
    question: str
    datasets: dict
    data_summary: str
    messages: list
    
    # Node 0: Question Understanding
    needs_data_work: bool
    question_reasoning: str
    
    # Node 1B: Requirements
    requirements: Optional[dict]
    
    # Node 2: Data Profile
    data_profile: Optional[dict]
    
    # Node 3: Alignment
    alignment_check: Optional[dict]
    alignment_iterations: int
    
    # Node 4: Code Execution
    code: Optional[str]
    execution_result: Optional[dict]
    execution_success: bool
    error: Optional[str]
    code_attempts: int
    failed_attempts: list
    
    # Node 5: Evaluation
    evaluation: Optional[dict]
    
    # Node 5a: Remediation
    remediation_plan: Optional[dict]
    total_remediations: int
    
    # Node 6: Final Output
    explanation: str
    final_output: dict


# ==== NODE IMPLEMENTATIONS ====

def node_0_understand_question(state: MVPAgentState) -> dict:
    """Node 0: Determine if question needs explanation only or data work."""
    result = understand_question(
        state["question"],
        state["data_summary"]
    )
    
    return {
        "needs_data_work": result["needs_data_work"],
        "question_reasoning": result["reasoning"]
    }


def node_1a_explain(state: MVPAgentState) -> dict:
    """Node 1A: Provide explanation for conceptual questions or limitations."""
    alignment_issues = None
    if state.get("alignment_check"):
        gaps = state["alignment_check"].get("gaps", [])
        reasoning = state["alignment_check"].get("reasoning", "")
        if gaps or reasoning:
            alignment_issues = f"Gaps: {gaps}. {reasoning}"
    
    explanation = provide_explanation(
        state["question"],
        state["data_summary"],
        alignment_issues
    )
    
    final_output = {
        "explanation": explanation,
        "evaluation": None,
        "code": None,
        "requirements": state.get("requirements"),
        "output_type": "explanation",
        "figures": None,
        "result_str": None,
        "failed_attempts": state.get("failed_attempts", [])
    }
    
    return {
        "explanation": explanation,
        "final_output": final_output
    }


def node_1b_requirements(state: MVPAgentState) -> dict:
    """Node 1B: Formulate requirements for data analysis."""
    remediation_guidance = None
    if state.get("remediation_plan"):
        remediation_guidance = state["remediation_plan"].get("guidance")
    
    requirements = formulate_requirements(
        state["question"],
        state["data_summary"],
        remediation_guidance
    )
    
    return {
        "requirements": requirements
    }


def node_2_profile_data(state: MVPAgentState) -> dict:
    """Node 2: Profile the data to understand what's available."""
    remediation_guidance = None
    if state.get("remediation_plan"):
        remediation_guidance = state["remediation_plan"].get("guidance")
    
    # Build concise summary for profiling (avoid JSON parsing errors from verbose summaries)
    concise_summary = "Available datasets:\n\n"
    for ds_id, ds_info in state["datasets"].items():
        concise_summary += f"Dataset '{ds_id}' ({ds_info['name']}):\n"
        concise_summary += generate_concise_summary(ds_info['df'])
        concise_summary += "\n\n"
    
    data_profile = profile_data(
        state["question"],
        state["requirements"],
        concise_summary,
        remediation_guidance
    )
    
    return {
        "data_profile": data_profile
    }


def node_3_alignment(state: MVPAgentState) -> dict:
    """Node 3: Check alignment between requirements and data."""
    alignment = check_alignment(
        state["requirements"],
        state["data_profile"]
    )
    
    return {
        "alignment_check": alignment,
        "alignment_iterations": state.get("alignment_iterations", 0) + 1
    }


def node_4_code(state: MVPAgentState) -> dict:
    """Node 4: Generate and execute code."""
    from data_analyzer import build_execution_context
    
    # Build structured execution context with dataset names, library versions, etc.
    execution_context = build_execution_context(state["datasets"])
    
    error = state.get("error")
    remediation_guidance = None
    if state.get("remediation_plan"):
        remediation_guidance = state["remediation_plan"].get("guidance")
    
    code = generate_analysis_code(
        state["question"],
        state["requirements"],
        state["data_profile"],
        state["data_summary"],
        error,
        remediation_guidance,
        execution_context  # Pass structured context to LLM
    )
    
    success, output, exec_error = execute_unified_code(code, state["datasets"])
    
    new_failed_attempts = state.get("failed_attempts", []).copy()
    if not success:
        new_failed_attempts.append({
            'attempt': state.get("code_attempts", 0) + 1,
            'code': code,
            'error': exec_error
        })
    
    return {
        "code": code,
        "execution_result": output if success else None,
        "execution_success": success,
        "error": exec_error if not success else None,
        "code_attempts": state.get("code_attempts", 0) + 1,
        "failed_attempts": new_failed_attempts
    }


def node_5_evaluate(state: MVPAgentState) -> dict:
    """Node 5: Evaluate the results for correctness."""
    evaluation = evaluate_results(
        state["question"],
        state["requirements"],
        state["code"],
        state["execution_result"],
        state["execution_success"],
        state.get("error")
    )
    
    return {
        "evaluation": evaluation
    }


def node_5a_remediation(state: MVPAgentState) -> dict:
    """Node 5a: Plan remediation for failed results."""
    remediation = plan_remediation(
        state["question"],
        state["evaluation"],
        state["code"],
        state.get("error"),
        state["requirements"],
        state["data_profile"]
    )
    
    return {
        "remediation_plan": remediation,
        "total_remediations": state.get("total_remediations", 0) + 1
    }


def node_6_explain_results(state: MVPAgentState) -> dict:
    """Node 6: Generate final explanation for the user."""
    max_attempts_exceeded = state.get("total_remediations", 0) >= MAX_TOTAL_REMEDIATIONS
    
    explanation = explain_results(
        state["question"],
        state["evaluation"],
        state["execution_result"],
        state["code"],
        state["requirements"],
        state.get("total_remediations", 0),
        max_attempts_exceeded
    )
    
    output_type = None
    figures = None
    result_str = None
    
    if state.get("execution_result"):
        output_type = state["execution_result"].get("type")
        figures = state["execution_result"].get("figures", [])
        result_str = state["execution_result"].get("result_str", "")
    
    if not state.get("execution_success"):
        output_type = "error"
    
    final_output = {
        "explanation": explanation,
        "evaluation": state.get("evaluation"),
        "code": state.get("code"),
        "requirements": state.get("requirements"),
        "data_profile": state.get("data_profile"),
        "alignment_check": state.get("alignment_check"),
        "output_type": output_type,
        "figures": figures,
        "result_str": result_str,
        "failed_attempts": state.get("failed_attempts", []),
        "total_remediations": state.get("total_remediations", 0)
    }
    
    return {
        "explanation": explanation,
        "final_output": final_output
    }


# ==== ROUTING FUNCTIONS ====

def route_from_node_0(state: MVPAgentState) -> Literal["node_1a_explain", "node_1b_requirements"]:
    """Route from question understanding."""
    if not state.get("needs_data_work", True):
        return "node_1a_explain"
    else:
        return "node_1b_requirements"


def route_from_node_3(state: MVPAgentState) -> Literal["node_4_code", "node_1b_requirements", "node_2_profile", "node_1a_explain"]:
    """Route from alignment check."""
    alignment = state.get("alignment_check", {})
    iterations = state.get("alignment_iterations", 0)
    
    if alignment.get("aligned", False):
        return "node_4_code"
    
    if iterations >= MAX_ALIGNMENT_ITERATIONS or alignment.get("recommendation") == "cannot_proceed":
        return "node_1a_explain"
    
    if alignment.get("recommendation") == "revise_requirements":
        return "node_1b_requirements"
    
    return "node_2_profile"


def route_from_node_4(state: MVPAgentState) -> Literal["node_5_evaluate", "node_4_code"]:
    """Route from code execution."""
    if state.get("execution_success", False) or state.get("code_attempts", 0) >= MAX_CODE_ATTEMPTS:
        return "node_5_evaluate"
    else:
        return "node_4_code"


def route_from_node_5(state: MVPAgentState) -> Literal["node_6_explain", "node_5a_remediation"]:
    """Route from evaluation."""
    evaluation = state.get("evaluation", {})
    if evaluation.get("is_valid", True):
        return "node_6_explain"
    else:
        return "node_5a_remediation"


def route_from_node_5a(state: MVPAgentState) -> Literal["node_6_explain", "node_4_code", "node_1b_requirements", "node_2_profile"]:
    """Route from remediation planning."""
    if state.get("total_remediations", 0) >= MAX_TOTAL_REMEDIATIONS:
        return "node_6_explain"
    
    action = state.get("remediation_plan", {}).get("action", "rewrite_code")
    
    if action == "rewrite_code":
        return "node_4_code"
    elif action == "revise_requirements":
        return "node_1b_requirements"
    else:
        return "node_2_profile"


# ==== GRAPH BUILDER ====

def build_mvp_agent_graph():
    """Build the MVP agent graph with all nodes and routing."""
    workflow = StateGraph(MVPAgentState)
    
    # Add all nodes
    workflow.add_node("node_0_understand", node_0_understand_question)
    workflow.add_node("node_1a_explain", node_1a_explain)
    workflow.add_node("node_1b_requirements", node_1b_requirements)
    workflow.add_node("node_2_profile", node_2_profile_data)
    workflow.add_node("node_3_alignment", node_3_alignment)
    workflow.add_node("node_4_code", node_4_code)
    workflow.add_node("node_5_evaluate", node_5_evaluate)
    workflow.add_node("node_5a_remediation", node_5a_remediation)
    workflow.add_node("node_6_explain", node_6_explain_results)
    
    # Set entry point
    workflow.set_entry_point("node_0_understand")
    
    # Add conditional edges from Node 0
    workflow.add_conditional_edges(
        "node_0_understand",
        route_from_node_0,
        {
            "node_1a_explain": "node_1a_explain",
            "node_1b_requirements": "node_1b_requirements"
        }
    )
    
    # Node 1A goes to END
    workflow.add_edge("node_1a_explain", END)
    
    # Node 1B goes to Node 2
    workflow.add_edge("node_1b_requirements", "node_2_profile")
    
    # Node 2 goes to Node 3
    workflow.add_edge("node_2_profile", "node_3_alignment")
    
    # Add conditional edges from Node 3
    workflow.add_conditional_edges(
        "node_3_alignment",
        route_from_node_3,
        {
            "node_4_code": "node_4_code",
            "node_1b_requirements": "node_1b_requirements",
            "node_2_profile": "node_2_profile",
            "node_1a_explain": "node_1a_explain"
        }
    )
    
    # Add conditional edges from Node 4
    workflow.add_conditional_edges(
        "node_4_code",
        route_from_node_4,
        {
            "node_5_evaluate": "node_5_evaluate",
            "node_4_code": "node_4_code"
        }
    )
    
    # Add conditional edges from Node 5
    workflow.add_conditional_edges(
        "node_5_evaluate",
        route_from_node_5,
        {
            "node_6_explain": "node_6_explain",
            "node_5a_remediation": "node_5a_remediation"
        }
    )
    
    # Add conditional edges from Node 5a
    workflow.add_conditional_edges(
        "node_5a_remediation",
        route_from_node_5a,
        {
            "node_6_explain": "node_6_explain",
            "node_4_code": "node_4_code",
            "node_1b_requirements": "node_1b_requirements",
            "node_2_profile": "node_2_profile"
        }
    )
    
    # Node 6 goes to END
    workflow.add_edge("node_6_explain", END)
    
    return workflow.compile()


# Build the agent
agent_app = build_mvp_agent_graph()
