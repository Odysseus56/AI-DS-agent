"""
Agent Core - Main agent loop functions.

This module contains the core execution logic:
- _run_agent_core: The single source of truth generator for agent execution
- run_agent: Non-streaming wrapper that returns final output
- run_agent_streaming: Streaming wrapper that yields iterations
- Helper functions: determine_output_type, graceful_degradation
"""

import json
import time
from datetime import datetime

from config import MODEL_SMART

from .state import AgentState, ToolCallLog, IterationLog, ExecutionLog, FinalOutput
from .tools import TOOLS, execute_tool, tool_validate_results
from .prompts import build_system_prompt, retrieve_examples
from .loop_detection import detect_loop, get_divergence_message
from .llm_client import get_openai_client


def run_agent(question: str, datasets: dict, max_iterations: int = 8) -> FinalOutput:
    """
    Main agent loop - ReAct style reasoning.
    
    This is a convenience wrapper around _run_agent_core() that consumes
    all iterations and returns the final output.
    
    Args:
        question: User's question
        datasets: Available datasets {name: {df, data_summary, ...}}
        max_iterations: Maximum iterations before graceful degradation
    
    Returns:
        FinalOutput with answer, results, metadata, and detailed execution log
    """
    final_output = None
    for iteration, exec_log, output in _run_agent_core(question, datasets, max_iterations):
        if output is not None:
            final_output = output
    
    if final_output is None:
        return FinalOutput(
            answer="Agent failed to produce output",
            confidence=0.0,
            output_type="error",
            caveats=["Internal error: no output produced"],
            reasoning_trace=[]
        )
    
    return final_output


def run_agent_streaming(question: str, datasets: dict, max_iterations: int = 8):
    """
    Streaming version of run_agent that yields iterations as they happen.
    
    This is a thin wrapper around _run_agent_core() for backward compatibility.
    
    Args:
        question: User's question
        datasets: Available datasets {name: {df, data_summary, ...}}
        max_iterations: Maximum iterations before graceful degradation
    
    Yields:
        tuple: (iteration_log, exec_log, final_output_or_none)
        - During execution: (IterationLog, ExecutionLog, None)
        - On completion: (None, ExecutionLog, FinalOutput)
    """
    yield from _run_agent_core(question, datasets, max_iterations)


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
# CORE AGENT LOOP - Single source of truth for agent execution
# =============================================================================

def _run_agent_core(question: str, datasets: dict, max_iterations: int = 8):
    """
    Core agent loop implementation - ReAct style reasoning.
    
    This is the single source of truth for agent execution logic.
    Both run_agent() and run_agent_streaming() use this generator.
    
    Yields:
        tuple: (iteration_log, exec_log, final_output_or_none)
        - During execution: (IterationLog, ExecutionLog, None)
        - On completion: (None, ExecutionLog, FinalOutput)
    """
    client = get_openai_client()
    
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
        
        # Capture model and token usage from response
        current_iteration.model = response.model
        if response.usage:
            current_iteration.prompt_tokens = response.usage.prompt_tokens
            current_iteration.completion_tokens = response.usage.completion_tokens
            current_iteration.total_tokens = response.usage.total_tokens
        
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
# CONVENIENCE FUNCTIONS FOR INTEGRATION
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
