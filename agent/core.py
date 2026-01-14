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
    """
    Handle max iterations reached with comprehensive context.
    
    Provides detailed feedback covering:
    - What was accomplished (if any results)
    - What failed (error history)
    - What's missing (validation, interpretation)
    - How to proceed (actionable recommendations)
    """
    
    # Determine output type and confidence based on what we have
    has_results = state.current_results and state.current_results.get("success")
    has_validation = state.validation and state.validation.get("is_valid")
    has_failures = len(state.failed_attempts) > 0
    
    exec_log.final_output_type = determine_output_type(state) if has_results else "error"
    exec_log.final_confidence = 0.3 if has_results else 0.1
    
    # Build comprehensive answer
    answer_parts = []
    
    # 1. Opening statement
    if has_results:
        answer_parts.append("I reached the iteration limit but was able to generate some results.")
    else:
        answer_parts.append("I reached the iteration limit and was unable to complete the analysis.")
    
    # 2. Show results if available
    if has_results:
        answer_parts.append(f"\n\n**Results:**\n{state.current_results.get('result_str', 'No results available')}")
    
    # 3. Show what's incomplete or missing
    if has_results and not has_validation:
        answer_parts.append("\n\n**⚠️ What's incomplete:**")
        answer_parts.append("\n- Results have not been validated for correctness")
        answer_parts.append("\n- No statistical significance testing was performed")
        answer_parts.append("\n- Results may need interpretation or additional context")
    
    # 4. Show error history if there were failures
    if has_failures:
        answer_parts.append(f"\n\n**Attempts made:** {len(state.failed_attempts)} iteration(s) encountered errors")
        answer_parts.append("\n\n**Errors encountered:**")
        for i, attempt in enumerate(state.failed_attempts[-3:], 1):  # Last 3
            error = attempt.get('error', 'Unknown error')
            error_preview = f"{error[:100]}..." if len(error) > 100 else error
            answer_parts.append(f"\n{i}. `{error_preview}`")
    
    # 5. Show code context
    if state.current_code:
        code_preview = state.current_code[:300]
        answer_parts.append(f"\n\n**Code {'used' if has_results else 'attempted'}:**")
        answer_parts.append(f"\n```python\n{code_preview}...")
        answer_parts.append("\n```")
    
    # 6. Provide actionable recommendations
    answer_parts.append("\n\n**💡 How to proceed:**")
    
    if has_results and not has_validation:
        answer_parts.append("\n- Review the results carefully - they haven't been validated")
        answer_parts.append("\n- Consider asking a follow-up question to validate or interpret these results")
    
    if has_failures:
        # Analyze error patterns and provide specific guidance
        errors = [a.get('error', '') for a in state.failed_attempts]
        if any('KeyError' in e or 'not in index' in e for e in errors):
            answer_parts.append("\n- **Data access issue**: Verify column names and group labels in your dataset")
            answer_parts.append("\n- Use `df.columns` or `df['column'].unique()` to check available values")
        elif any('ValueError' in e or 'dtype' in e for e in errors):
            answer_parts.append("\n- **Data type issue**: Check that numeric columns are properly formatted")
            answer_parts.append("\n- Try converting columns explicitly: `df['col'].astype(float)`")
        elif any('IndexError' in e or 'out of bounds' in e for e in errors):
            answer_parts.append("\n- **Filtering issue**: Verify your filtering conditions match the actual data")
            answer_parts.append("\n- Check group labels are spelled correctly (case-sensitive)")
        else:
            answer_parts.append("\n- The analysis may be too complex - try breaking it into smaller steps")
    
    if not has_results:
        answer_parts.append("\n- Simplify the question or provide more specific requirements")
        answer_parts.append("\n- Try asking about individual components of the analysis separately")
    
    return FinalOutput(
        answer=''.join(answer_parts),
        confidence=exec_log.final_confidence,
        output_type=exec_log.final_output_type,
        result=state.current_results.get("result") if has_results else None,
        figures=state.current_results.get("figures", []) if has_results else [],
        code=state.current_code,
        caveats=["Analysis incomplete due to iteration limit"],
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
                
                # Check if this was a successful validation - grant bonus iterations
                if tool_name == "validate_results" and not had_error:
                    if tool_result.get("is_valid", False):
                        state.max_iterations += 2
                        reasoning_trace.append("Validation successful - granted +2 bonus iterations")
                
                # Add tool result to conversation
                state.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result, default=str)[:4000]
                })
            
            # Add iteration to log and yield it
            exec_log.add_iteration(current_iteration)
            yield (current_iteration, exec_log, None)
            
            # Check if we're within 2 iterations of the limit after tool execution
            # If validation failed and we're close to limit, provide helpful summary
            if state.iterations >= state.max_iterations - 2:
                if state.failed_attempts and not (state.current_results and state.current_results.get("success")):
                    # We're close to limit with failures and no success - add helpful context
                    state.messages.append({
                        "role": "system",
                        "content": "You are approaching the iteration limit. If you cannot complete the analysis in the next iteration, please provide a summary of what you tried and why it failed."
                    })
        
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
                else:
                    # Validation successful - increase iteration limit by 2
                    state.max_iterations += 2
            
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
    exec_log.final_answer = final_output.answer  # Store detailed error message for logging
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
