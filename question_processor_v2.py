"""Question processor V2 for AI Data Scientist Agent.

This module implements the V2 ReAct-based question processing, replacing the
rigid node-based streaming with a simpler tool-based approach.

The V2 processor shows:
- Detailed execution log with iterations and tool calls
- Reasoning trace (what the agent is thinking)
- Tool calls as they happen
- Final results and visualizations
"""
import streamlit as st
from datetime import datetime, timezone
import plotly.io as pio
import io
import json

from react_agent import (
    process_question_v2, 
    process_question_v2_streaming,
    AgentState, 
    FinalOutput, 
    ExecutionLog,
    IterationLog,
    ToolCallLog
)
from config import MAX_CHAT_MESSAGES
from supabase_logger import utc_to_user_timezone


def display_iteration(iteration: IterationLog):
    """Display a single iteration in the UI."""
    tool_count = len(iteration.tool_calls)
    
    # Show LLM reasoning if present
    if iteration.llm_reasoning:
        st.markdown("**Agent Thinking:**")
        reasoning_text = iteration.llm_reasoning[:500]
        if len(iteration.llm_reasoning) > 500:
            reasoning_text += "..."
        st.markdown(f"> {reasoning_text}")
    
    # Show tool calls
    for tc in iteration.tool_calls:
        status_icon = "✅" if tc.success else "❌"
        st.markdown(f"**{status_icon} `{tc.tool_name}`** ({tc.duration_ms:.0f}ms)")
        
        # Show key info based on tool type
        if tc.tool_name == "write_code":
            approach = tc.arguments.get("approach", "")
            if approach:
                st.caption(f"Approach: {approach[:100]}")
        elif tc.tool_name == "execute_code":
            if tc.result.get("success"):
                st.caption(f"Result: {tc.result.get('result_str', '')[:100]}")
            else:
                st.caption(f"Error: {tc.result.get('error', '')[:100]}")
        elif tc.tool_name == "validate_results":
            is_valid = tc.result.get("is_valid", False)
            confidence = tc.result.get("confidence", 0)
            st.caption(f"Valid: {is_valid}, Confidence: {confidence:.0%}")
        
        if tc.error:
            st.error(f"Error: {tc.error}")


def display_execution_log(exec_log: ExecutionLog):
    """Display the execution log in a structured, readable format in Streamlit."""
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Iterations", len(exec_log.iterations))
    with col2:
        st.metric("Tool Calls", exec_log.total_tool_calls)
    with col3:
        st.metric("Output Type", exec_log.final_output_type or "N/A")
    with col4:
        confidence = exec_log.final_confidence
        st.metric("Confidence", f"{confidence:.0%}" if confidence else "N/A")
    
    # Warnings
    if exec_log.loop_detected:
        st.warning("⚠️ Loop detected during execution")
    if exec_log.max_iterations_reached:
        st.warning("⚠️ Max iterations reached")
    
    # Retrieved examples
    if exec_log.retrieved_examples:
        with st.expander("📚 Retrieved Examples", expanded=False):
            for ex in exec_log.retrieved_examples:
                st.markdown(f"- **Q:** {ex.get('question', 'N/A')}")
                st.markdown(f"  **Approach:** {ex.get('approach', 'N/A')}")
    
    # Iterations detail
    for iteration in exec_log.iterations:
        with st.expander(f"Iteration {iteration.iteration_num} ({len(iteration.tool_calls)} tool calls)", expanded=False):
            # LLM reasoning
            if iteration.llm_reasoning:
                st.markdown("**LLM Reasoning:**")
                reasoning_text = iteration.llm_reasoning[:800]
                if len(iteration.llm_reasoning) > 800:
                    reasoning_text += "..."
                st.markdown(f"> {reasoning_text}")
            
            # Tool calls
            for tc in iteration.tool_calls:
                status_icon = "✅" if tc.success else "❌"
                st.markdown(f"**{status_icon} Tool: `{tc.tool_name}`** ({tc.duration_ms:.0f}ms)")
                
                # Arguments
                args_str = json.dumps(tc.arguments, indent=2, default=str)
                if len(args_str) > 200:
                    args_str = args_str[:200] + "..."
                st.code(args_str, language="json")
                
                # Result summary
                if tc.error:
                    st.error(f"Error: {tc.error}")
                else:
                    result_str = json.dumps(tc.result, indent=2, default=str)
                    if len(result_str) > 500:
                        result_str = result_str[:500] + "..."
                    st.code(result_str, language="json")
    
    # Errors
    if exec_log.errors:
        st.error("**Errors:**")
        for err in exec_log.errors:
            st.markdown(f"- {err}")


def process_question(user_question: str) -> dict:
    """Process a user question through the V2 ReAct agent with streaming iterations.
    
    This function handles the complete question processing pipeline:
    1. Adds user message to chat history
    2. Executes the ReAct agent with streaming iterations
    3. Displays each iteration as it happens
    4. Logs the interaction
    5. Saves response to chat history
    
    Args:
        user_question: The user's question to process
        
    Returns:
        dict: The result from the agent containing all outputs
    """
    # Limit chat history to prevent memory issues
    if len(st.session_state.messages) > MAX_CHAT_MESSAGES:
        st.session_state.messages = st.session_state.messages[-MAX_CHAT_MESSAGES:]
    
    # Add user message to chat
    st.session_state.messages.append({"role": "user", "content": user_question})
    
    # Display user message
    current_time = utc_to_user_timezone(
        datetime.now(timezone.utc).isoformat(), 
        st.session_state.user_timezone
    )
    with st.chat_message("user"):
        st.markdown(user_question)
    
    st.markdown(f'<div class="chat-timestamp">{current_time}</div>', unsafe_allow_html=True)
    
    # Execute V2 ReAct agent with streaming
    with st.chat_message("assistant"):
        assistant_timestamp = utc_to_user_timezone(
            datetime.now(timezone.utc).isoformat(), 
            st.session_state.user_timezone
        )
        
        # Create container for streaming iterations
        iterations_container = st.container()
        code_placeholder = st.empty()
        result_placeholder = st.empty()
        explanation_placeholder = st.empty()
        
        # Track iterations for final display
        result = None
        exec_log = None
        
        # Stream iterations as they happen
        with iterations_container:
            st.markdown("**🤖 ReAct Agent V2**")
            
            for update in process_question_v2_streaming(user_question, st.session_state.datasets):
                if update["type"] == "iteration":
                    iteration = update["iteration"]
                    exec_log = update["exec_log"]
                    
                    # Display each iteration as an expander
                    tool_names = [tc.tool_name for tc in iteration.tool_calls]
                    tools_str = ", ".join(tool_names) if tool_names else "thinking..."
                    
                    with st.expander(f"Iteration {iteration.iteration_num}: {tools_str}", expanded=False):
                        display_iteration(iteration)
                
                elif update["type"] == "final":
                    result = update["result"]
                    exec_log = update["exec_log"]
            
            # Show final execution summary
            if exec_log:
                with st.expander("📊 Execution Summary", expanded=False):
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Iterations", len(exec_log.iterations))
                    with col2:
                        st.metric("Tool Calls", exec_log.total_tool_calls)
                    with col3:
                        st.metric("Output", exec_log.final_output_type or "N/A")
                    with col4:
                        conf = exec_log.final_confidence
                        st.metric("Confidence", f"{conf:.0%}" if conf else "N/A")
                    
                    if exec_log.loop_detected:
                        st.warning("⚠️ Loop detected during execution")
                    if exec_log.max_iterations_reached:
                        st.warning("⚠️ Max iterations reached")
        
        # Handle case where result is None (shouldn't happen but safety check)
        if result is None:
            st.error("Agent did not produce a result")
            return {"error": "No result produced"}
        
        # Display code if generated
        if result.get("code"):
            with code_placeholder.container():
                with st.expander("💻 Generated Code", expanded=False):
                    st.code(result["code"], language="python")
        
        # Display results based on output type
        output_type = result.get("output_type", "explanation")
        figures = result.get("figures", [])
        
        if output_type == "visualization" and figures:
            # Display visualizations
            for idx, fig in enumerate(figures):
                if hasattr(fig, 'write_image'):
                    # Plotly figure
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Download buttons
                    title = "chart"
                    if hasattr(fig, 'layout') and hasattr(fig.layout, 'title'):
                        if hasattr(fig.layout.title, 'text') and fig.layout.title.text:
                            title = str(fig.layout.title.text).replace(' ', '_').replace('/', '_')[:50]
                    
                    html_str = pio.to_html(fig, include_plotlyjs='cdn', full_html=True)
                    
                    col1, col2, col3 = st.columns([1, 1, 4])
                    with col1:
                        st.download_button(
                            label="Download HTML",
                            data=html_str,
                            file_name=f"{title}.html",
                            mime="text/html",
                            key=f"v2_html_{idx}_{len(st.session_state.messages)}"
                        )
                    with col2:
                        try:
                            img_bytes = fig.to_image(format="png", width=1200, height=800, scale=2)
                            st.download_button(
                                label="Download PNG",
                                data=img_bytes,
                                file_name=f"{title}.png",
                                mime="image/png",
                                key=f"v2_png_{idx}_{len(st.session_state.messages)}"
                            )
                        except Exception:
                            pass
                else:
                    # Matplotlib figure
                    st.pyplot(fig)
        
        elif output_type == "analysis" and result.get("result") is not None:
            # Display analysis results
            with result_placeholder.container():
                result_str = str(result.get("result", ""))
                if len(result_str) > 1000:
                    with st.expander("📊 Analysis Results", expanded=True):
                        st.text(result_str)
                else:
                    st.text(result_str)
        
        elif output_type == "error":
            st.error(result.get("answer", "An error occurred"))
        
        # Display explanation/answer
        if result.get("answer"):
            with explanation_placeholder.container():
                st.markdown(result["answer"])
        
        # Display caveats if any
        if result.get("caveats"):
            with st.expander("⚠️ Caveats & Limitations", expanded=False):
                for caveat in result["caveats"]:
                    st.markdown(f"- {caveat}")
        
        # Display confidence
        confidence = result.get("confidence", 0.5)
        if confidence < 0.5:
            st.warning(f"⚠️ Low confidence ({confidence:.0%}) - results may need verification")
        
        # Logging - use V2 execution log format
        code = result.get("code")
        answer = result.get("answer", "")
        exec_log = result.get("execution_log")
        
        # Log using the new V2 format if execution_log is available
        if exec_log and hasattr(st.session_state.logger, 'log_react_execution'):
            st.session_state.logger.log_react_execution(exec_log)
        else:
            # Fallback to old logging format
            if output_type == 'visualization' and figures:
                st.session_state.logger.log_visualization_workflow(
                    user_question, "VISUALIZATION_V2", code, answer,
                    True, figures, "", execution_plan={}, evaluation={}
                )
            elif output_type == 'error':
                st.session_state.logger.log_analysis_workflow(
                    user_question, "ERROR_V2", code, "", answer,
                    success=False, error=answer, execution_plan={}
                )
            elif code:
                result_str = str(result.get("result", ""))
                st.session_state.logger.log_analysis_workflow(
                    user_question, "ANALYSIS_V2", code, result_str, answer,
                    success=True, execution_plan={}, evaluation={}
                )
            else:
                st.session_state.logger.log_text_qa(user_question, answer)
        
        # Save to chat history - include iteration logs for consistent display
        # Convert iteration logs to serializable format
        iterations_data = []
        if exec_log and exec_log.iterations:
            for iteration in exec_log.iterations:
                iter_data = {
                    "iteration_num": iteration.iteration_num,
                    "llm_reasoning": iteration.llm_reasoning,
                    "tool_calls": [
                        {
                            "tool_name": tc.tool_name,
                            "arguments": tc.arguments,
                            "result": tc.result,
                            "duration_ms": tc.duration_ms,
                            "success": tc.success,
                            "error": tc.error
                        }
                        for tc in iteration.tool_calls
                    ]
                }
                iterations_data.append(iter_data)
        
        message_data = {
            "role": "assistant",
            "content": answer,
            "metadata": {
                "code": code,
                "output_type": output_type,
                "confidence": confidence,
                "reasoning_trace": result.get("reasoning_trace", []),
                "caveats": result.get("caveats", []),
                "architecture": "v2_react",
                "iterations": iterations_data,
                "total_tool_calls": exec_log.total_tool_calls if exec_log else 0,
                "loop_detected": exec_log.loop_detected if exec_log else False,
                "max_iterations_reached": exec_log.max_iterations_reached if exec_log else False
            }
        }
        
        if output_type == 'visualization' and figures:
            message_data["type"] = "visualization"
            message_data["figures"] = figures
        elif output_type == 'error':
            message_data["type"] = "error"
        
        st.session_state.messages.append(message_data)
        
        st.markdown(f'<div class="chat-timestamp">{assistant_timestamp}</div>', unsafe_allow_html=True)
    
    return result
