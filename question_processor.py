"""Question processor for AI Data Scientist Agent.

This module extracts the question processing logic from app.py to enable
reuse by both manual chat input and automated scenario execution.
"""
import streamlit as st
from datetime import datetime, timezone
from langgraph_agent import agent_app
from node_display import (
    display_node_0_understanding,
    display_node_1b_requirements,
    display_node_2_profile,
    display_node_3_alignment,
    display_failed_attempts,
    display_node_4_code,
    display_code_execution_output,
    display_node_5_evaluation,
    display_node_5a_remediation,
    display_node_6_explanation
)
from config import MAX_CHAT_MESSAGES
from supabase_logger import utc_to_user_timezone


def process_question(user_question: str) -> dict:
    """Process a user question through the LangGraph agent workflow.
    
    This function handles the complete question processing pipeline:
    1. Adds user message to chat history
    2. Builds initial state for LangGraph agent
    3. Executes the agent with streaming UI updates
    4. Displays visualizations and results
    5. Logs the interaction
    6. Saves response to chat history
    
    Args:
        user_question: The user's question to process
        
    Returns:
        dict: The final state from the agent containing all outputs
    """
    import plotly.io as pio
    import io
    
    # Limit chat history to prevent memory issues (keep last N messages)
    if len(st.session_state.messages) > MAX_CHAT_MESSAGES:
        st.session_state.messages = st.session_state.messages[-MAX_CHAT_MESSAGES:]
    
    # Add user message to chat
    st.session_state.messages.append({"role": "user", "content": user_question})
    
    # Display user message
    current_time = utc_to_user_timezone(datetime.now(timezone.utc).isoformat(), st.session_state.user_timezone)
    with st.chat_message("user"):
        st.markdown(user_question)
    
    # Show timestamp outside message bubble
    st.markdown(f'<div class="chat-timestamp">{current_time}</div>', unsafe_allow_html=True)
    
    # Build combined data summary for all datasets
    combined_summary = "Available datasets:\n\n"
    for ds_id, ds_info in st.session_state.datasets.items():
        combined_summary += f"Dataset '{ds_id}' ({ds_info['name']}):\n{ds_info['data_summary']}\n\n"
    
    # LANGGRAPH WORKFLOW
    with st.chat_message("assistant"):
        # Store timestamp for display at bottom
        assistant_timestamp = utc_to_user_timezone(datetime.now(timezone.utc).isoformat(), st.session_state.user_timezone)
        
        # Build initial state for LangGraph MVP agent
        initial_state = {
            "question": user_question,
            "datasets": st.session_state.datasets,
            "data_summary": combined_summary,
            "messages": st.session_state.messages,
            # Node 0
            "needs_data_work": True,
            "question_reasoning": "",
            # Node 1B
            "requirements": None,
            # Node 2
            "data_profile": None,
            # Node 3
            "alignment_check": None,
            "alignment_iterations": 0,
            # Node 4
            "code": None,
            "execution_result": None,
            "execution_success": False,
            "error": None,
            "code_attempts": 0,
            "failed_attempts": [],
            # Node 5
            "evaluation": None,
            # Node 5a
            "remediation_plan": None,
            "total_remediations": 0,
            # Node 6
            "explanation": "",
            "final_output": {}
        }
        
        # Execute LangGraph agent with streaming
        # Create placeholders for each step (MVP architecture)
        understanding_placeholder = st.empty()
        requirements_placeholder = st.empty()
        data_profile_placeholder = st.empty()
        alignment_placeholder = st.empty()
        failed_attempts_placeholder = st.empty()
        code_placeholder = st.empty()
        execution_placeholder = st.empty()
        evaluation_placeholder = st.empty()
        remediation_placeholder = st.empty()
        explanation_placeholder = st.empty()
        
        # Stream through the graph
        final_state = None
        last_state = None
        # Collect all node states for metadata
        all_node_states = {}
        with st.spinner("🤖 Processing your request..."):
            for event in agent_app.stream(initial_state):
                # event is a dict with node name as key
                for node_name, node_state in event.items():
                    last_state = node_state  # Track last state
                    all_node_states[node_name] = node_state  # Collect all states
                    
                    # Log node completion incrementally
                    st.session_state.logger.log_node_completion(node_name, node_state)
                    
                    # Update display based on which node completed - using reusable functions
                    if node_name == "node_0_understand":
                        with understanding_placeholder.container():
                            display_node_0_understanding({
                                "needs_data_work": node_state.get('needs_data_work'),
                                "question_reasoning": node_state.get('question_reasoning')
                            })
                    
                    elif node_name == "node_1b_requirements":
                        with requirements_placeholder.container():
                            display_node_1b_requirements(node_state.get("requirements"))
                    
                    elif node_name == "node_2_profile":
                        with data_profile_placeholder.container():
                            display_node_2_profile(node_state.get("data_profile"))
                    
                    elif node_name == "node_3_alignment":
                        with alignment_placeholder.container():
                            display_node_3_alignment(node_state.get("alignment_check"))
                    
                    elif node_name == "node_4_code":
                        # Show failed attempts
                        failed_attempts = node_state.get("failed_attempts", [])
                        if failed_attempts:
                            with failed_attempts_placeholder.container():
                                display_failed_attempts(failed_attempts)
                        
                        # Show successful code
                        if node_state.get("execution_success") and node_state.get("code"):
                            with code_placeholder.container():
                                display_node_4_code(node_state["code"], failed_attempts)
                            
                            # Show execution output
                            result_str = node_state.get("execution_result", {}).get("result_str")
                            if result_str:
                                with execution_placeholder.container():
                                    display_code_execution_output(result_str)
                    
                    elif node_name == "node_5_evaluate":
                        with evaluation_placeholder.container():
                            display_node_5_evaluation(node_state.get("evaluation"))
                    
                    elif node_name == "node_5a_remediation":
                        with remediation_placeholder.container():
                            display_node_5a_remediation(
                                node_state.get("remediation_plan"),
                                node_state.get("total_remediations")
                            )
                    
                    elif node_name in ["node_1a_explain", "node_6_explain"]:
                        final_state = node_state
                        if node_state.get("explanation"):
                            # Extract result_str from execution_result if available
                            result_str = None
                            if node_state.get("execution_result"):
                                result_str = node_state["execution_result"].get("result_str")
                            
                            with explanation_placeholder.container():
                                display_node_6_explanation(
                                    node_state["explanation"], 
                                    result_str,
                                    expanded=True
                                )
        
        # Extract final results
        if final_state is None:
            final_state = last_state  # Use last state if no explain/error node
        
        plan = final_state.get("plan", {})
        final_output = final_state.get("final_output", {})
        
        code = final_output.get("code")
        evaluation = final_output.get("evaluation")
        explanation = final_output.get("explanation")
        output_type = final_output.get("output_type")
        figures = final_output.get("figures")
        result_str = final_output.get("result_str")
        failed_attempts = final_output.get("failed_attempts", [])
        error = final_output.get("error")
        
        # Display visualizations with interactive buttons
        if output_type == 'visualization' and figures:
            for idx, fig in enumerate(figures):
                if hasattr(fig, 'write_image'):
                    # Plotly figure - display with interactive features
                    st.plotly_chart(fig, width='stretch')
                    
                    # Extract title from figure for filename
                    title = "chart"
                    if hasattr(fig, 'layout') and hasattr(fig.layout, 'title'):
                        if hasattr(fig.layout.title, 'text') and fig.layout.title.text:
                            title = str(fig.layout.title.text).replace(' ', '_').replace('/', '_')[:50]
                    
                    # Prepare HTML export
                    html_str = pio.to_html(fig, include_plotlyjs='cdn', full_html=True)
                    
                    # Prepare PNG export using Plotly's built-in method
                    png_buf = io.BytesIO()
                    try:
                        # Try Plotly's built-in to_image() method first (no kaleido required)
                        img_bytes = fig.to_image(format="png", width=1200, height=800, scale=2)
                        png_buf.write(img_bytes)
                        png_buf.seek(0)
                        png_available = True
                    except Exception as e:
                        print(f"[WARNING] Could not export Plotly to PNG with to_image(): {e}")
                        try:
                            # Fallback to kaleido if available
                            fig.write_image(png_buf, format='png', width=1200, height=800, scale=2)
                            png_buf.seek(0)
                            png_available = True
                        except Exception as e2:
                            print(f"[WARNING] Kaleido also failed: {e2}")
                            png_available = False
                    
                    # Show both download buttons
                    col1, col2, col3 = st.columns([1, 1, 4])
                    with col1:
                        st.download_button(
                            label="📊 Download HTML",
                            data=html_str,
                            file_name=f"{title}.html",
                            mime="text/html",
                            help="Download interactive HTML file",
                            key=f"plotly_html_{idx}_{len(st.session_state.messages)}"
                        )
                    with col2:
                        if png_available:
                            st.download_button(
                                label="💾 Download PNG",
                                data=png_buf,
                                file_name=f"{title}.png",
                                mime="image/png",
                                help="Download high-resolution PNG image",
                                key=f"plotly_png_{idx}_{len(st.session_state.messages)}"
                            )
                        else:
                            st.button(
                                label="💾 Download PNG",
                                disabled=True,
                                help="PNG export not available - try installing plotly-kaleido",
                                key=f"plotly_png_disabled_{idx}_{len(st.session_state.messages)}"
                            )
                else:
                    # Matplotlib figure - display and add download button
                    st.pyplot(fig)
                    
                    # Extract title if available
                    title = "chart"
                    if hasattr(fig, '_suptitle') and fig._suptitle:
                        title = str(fig._suptitle.get_text()).replace(' ', '_').replace('/', '_')[:50]
                    elif len(fig.axes) > 0 and fig.axes[0].get_title():
                        title = str(fig.axes[0].get_title()).replace(' ', '_').replace('/', '_')[:50]
                    
                    # Convert matplotlib figure to PNG bytes for download
                    buf = io.BytesIO()
                    fig.savefig(buf, format='png', dpi=300, bbox_inches='tight')
                    buf.seek(0)
                    
                    col1, col2 = st.columns([1, 5])
                    with col1:
                        st.download_button(
                            label="💾 Download PNG",
                            data=buf,
                            file_name=f"{title}.png",
                            mime="image/png",
                            help="Download high-resolution PNG image",
                            key=f"matplotlib_{idx}_{len(st.session_state.messages)}"
                        )
        
        # Display error if present
        if output_type == 'error':
            st.error(explanation)
        elif not explanation and not figures:
            st.markdown(explanation or "No response generated")
        
        # Logging
        if output_type == 'visualization' and figures:
            st.session_state.logger.log_visualization_workflow(
                user_question, "VISUALIZATION", code, explanation or "Visualization generated", 
                True, figures, "", execution_plan=plan, evaluation=evaluation
            )
        elif output_type == 'error':
            st.session_state.logger.log_analysis_workflow(
                user_question, "CODE_FAILED", code, "", explanation, 
                success=False, error=error, execution_plan=plan
            )
        elif code:
            st.session_state.logger.log_analysis_workflow(
                user_question, "ANALYSIS", code, result_str, explanation or evaluation or result_str, 
                success=True, execution_plan=plan, evaluation=evaluation
            )
        else:
            st.session_state.logger.log_text_qa(user_question, explanation)
        
        # Save to chat history with all MVP architecture metadata
        message_data = {
            "role": "assistant",
            "content": explanation or result_str or "No response",
            "metadata": {
                "code": code,
                "plan": plan,
                "output_type": output_type,
                "result_str": result_str,
                "evaluation": evaluation,
                "explanation": explanation,
                "failed_attempts": failed_attempts,
                # MVP architecture fields - use collected node states to ensure all nodes are captured
                "needs_data_work": all_node_states.get("node_0_understand", {}).get("needs_data_work"),
                "question_reasoning": all_node_states.get("node_0_understand", {}).get("question_reasoning"),
                "requirements": all_node_states.get("node_1b_requirements", {}).get("requirements"),
                "data_profile": all_node_states.get("node_2_profile", {}).get("data_profile"),
                "alignment_check": all_node_states.get("node_3_alignment", {}).get("alignment_check"),
                "remediation_plan": all_node_states.get("node_5a_remediation", {}).get("remediation_plan"),
                "total_remediations": all_node_states.get("node_5a_remediation", {}).get("total_remediations", 0)
            }
        }
        
        if output_type == 'visualization' and figures:
            message_data["type"] = "visualization"
            message_data["figures"] = figures
        elif output_type == 'error':
            message_data["type"] = "error"
        
        st.session_state.messages.append(message_data)
        
        # Show timestamp outside message bubble for new assistant message
        st.markdown(f'<div class="chat-timestamp">{assistant_timestamp}</div>', unsafe_allow_html=True)
    
    return final_state
