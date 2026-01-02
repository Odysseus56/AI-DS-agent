from typing import TypedDict, Literal, Optional, Any
from langgraph.graph import StateGraph, END
from llm_client import (
    create_execution_plan,
    generate_unified_code,
    fix_code_with_error,
    evaluate_code_results,
    generate_final_explanation
)
from code_executor import execute_unified_code


class AgentState(TypedDict):
    question: str
    datasets: dict
    data_summary: str
    messages: list
    plan: Optional[dict]
    code: Optional[str]
    execution_result: Optional[dict]
    execution_success: bool
    error: Optional[str]
    attempts: int
    failed_attempts: list
    evaluation: Optional[str]
    explanation: Optional[str]
    final_output: Optional[dict]


def plan_node(state: AgentState) -> AgentState:
    plan = create_execution_plan(
        state["question"],
        state["data_summary"],
        state["messages"]
    )
    
    return {
        **state,
        "plan": plan
    }


def code_node(state: AgentState) -> AgentState:
    if state["attempts"] == 0:
        code = generate_unified_code(
            state["question"],
            state["data_summary"],
            state["messages"]
        )
    else:
        code = fix_code_with_error(
            state["question"],
            state["code"],
            state["error"],
            state["data_summary"],
            state["messages"]
        )
    
    success, output, error = execute_unified_code(code, state["datasets"])
    
    new_failed_attempts = state["failed_attempts"].copy()
    if not success:
        new_failed_attempts.append({
            'attempt': state["attempts"] + 1,
            'code': code,
            'error': error
        })
    
    return {
        **state,
        "code": code,
        "execution_result": output if success else None,
        "execution_success": success,
        "error": error if not success else None,
        "attempts": state["attempts"] + 1,
        "failed_attempts": new_failed_attempts
    }


def evaluate_node(state: AgentState) -> AgentState:
    evaluation = evaluate_code_results(
        state["question"],
        state["code"],
        state["execution_result"].get("result_str", ""),
        state["data_summary"],
        state["messages"]
    )
    
    return {
        **state,
        "evaluation": evaluation
    }


def explain_node(state: AgentState) -> AgentState:
    explanation = generate_final_explanation(
        state["question"],
        state.get("evaluation"),
        state["data_summary"],
        state["messages"]
    )
    
    output_type = None
    figures = None
    result_str = None
    
    if state.get("execution_result"):
        output_type = state["execution_result"].get("type")
        figures = state["execution_result"].get("figures", [])
        result_str = state["execution_result"].get("result_str", "")
    
    final_output = {
        "explanation": explanation,
        "evaluation": state.get("evaluation"),
        "code": state.get("code"),
        "plan": state.get("plan"),
        "output_type": output_type,
        "figures": figures,
        "result_str": result_str,
        "failed_attempts": state.get("failed_attempts", [])
    }
    
    return {
        **state,
        "explanation": explanation,
        "final_output": final_output
    }


def error_node(state: AgentState) -> AgentState:
    error_msg = f"Code execution failed after {state['attempts']} attempts. Final error: {state['error']}"
    
    final_output = {
        "explanation": error_msg,
        "evaluation": None,
        "code": state.get("code"),
        "plan": state.get("plan"),
        "output_type": "error",
        "figures": None,
        "result_str": None,
        "failed_attempts": state.get("failed_attempts", []),
        "error": state.get("error")
    }
    
    return {
        **state,
        "explanation": error_msg,
        "final_output": final_output
    }


def should_execute_code(state: AgentState) -> Literal["code", "explain"]:
    if state["plan"].get("needs_code", False):
        return "code"
    else:
        return "explain"


def should_retry_code(state: AgentState) -> Literal["evaluate", "retry", "error"]:
    if state["execution_success"]:
        return "evaluate"
    elif state["attempts"] < 3:
        return "retry"
    else:
        return "error"


def should_evaluate(state: AgentState) -> Literal["evaluate", "explain"]:
    if state["plan"].get("needs_evaluation", False):
        return "evaluate"
    else:
        return "explain"


def build_agent_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("plan", plan_node)
    workflow.add_node("code", code_node)
    workflow.add_node("evaluate", evaluate_node)
    workflow.add_node("explain", explain_node)
    workflow.add_node("error", error_node)
    
    workflow.set_entry_point("plan")
    
    workflow.add_conditional_edges(
        "plan",
        should_execute_code,
        {
            "code": "code",
            "explain": "explain"
        }
    )
    
    workflow.add_conditional_edges(
        "code",
        should_retry_code,
        {
            "evaluate": "evaluate",
            "retry": "code",
            "error": "error"
        }
    )
    
    workflow.add_conditional_edges(
        "evaluate",
        should_evaluate,
        {
            "evaluate": "explain",
            "explain": "explain"
        }
    )
    
    workflow.add_edge("explain", END)
    workflow.add_edge("error", END)
    
    return workflow.compile()


agent_app = build_agent_graph()
