"""
Chat Page - Main conversation interface with the AI agent.

This module handles:
- Displaying chat history with proper formatting
- Rendering V2 ReAct agent iterations and tool calls
- Visualization display with download options
- Scenario mode controls
- Chat input handling
"""

import io
import streamlit as st
from datetime import datetime, timezone

from supabase_logger import utc_to_user_timezone
from question_processor_v2 import (
    process_question,
    TOOL_EMOJI_MAP,
    extract_reasoning_snippet,
    build_dynamic_title,
    render_tool_call
)
from page_modules.scenarios_page import (
    should_auto_submit_next_question,
    get_next_scenario_question,
    advance_scenario_progress
)


def _render_visualization_message(message: dict, msg_idx: int):
    """Render a visualization message with figures and download buttons.
    
    Args:
        message: The message dict containing figures
        msg_idx: Index of the message for unique keys
    """
    import plotly.io as pio
    
    for idx, fig in enumerate(message.get("figures", [])):
        # Check if it's a Plotly figure or matplotlib figure
        if hasattr(fig, 'write_image'):
            # Plotly figure - display with interactive features
            st.plotly_chart(fig, use_container_width=True)
            
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
                    key=f"history_plotly_html_{msg_idx}_{idx}"
                )
            with col2:
                if png_available:
                    st.download_button(
                        label="💾 Download PNG",
                        data=png_buf,
                        file_name=f"{title}.png",
                        mime="image/png",
                        help="Download high-resolution PNG image",
                        key=f"history_plotly_png_{msg_idx}_{idx}"
                    )
                else:
                    st.button(
                        label="💾 Download PNG",
                        disabled=True,
                        help="PNG export not available - try installing plotly-kaleido",
                        key=f"history_plotly_png_disabled_{msg_idx}_{idx}"
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
                    key=f"history_matplotlib_{msg_idx}_{idx}"
                )


def _render_v2_react_message(metadata: dict):
    """Render V2 ReAct agent iterations and tool calls.
    
    Args:
        metadata: Message metadata containing iterations info
    """
    st.markdown("**🤖 ReAct Agent V2**")
    
    # Display each iteration as an expander
    iterations = metadata.get("iterations", [])
    for iteration in iterations:
        tool_calls = iteration.get("tool_calls", [])
        tool_names = [tc.get("tool_name", "") for tc in tool_calls]
        
        # Use shared utilities for emoji and title
        primary_emoji = TOOL_EMOJI_MAP.get(tool_names[0], "🔄") if tool_names else "🔄"
        llm_reasoning = iteration.get("llm_reasoning", "")
        reasoning_snippet = extract_reasoning_snippet(llm_reasoning, tool_calls)
        dynamic_title = build_dynamic_title(tool_names, reasoning_snippet)
        
        with st.expander(f"{primary_emoji} Iteration {iteration.get('iteration_num', '?')}: {dynamic_title}", expanded=False):
            # Show LLM reasoning if present
            if llm_reasoning:
                with st.expander("💭 Agent Reasoning", expanded=True):
                    st.markdown(llm_reasoning)
            
            # Show tool calls using shared renderer
            for tc in tool_calls:
                render_tool_call(tc)
    
    # Show warnings if any
    if metadata.get("loop_detected"):
        st.warning("⚠️ Loop detected during execution")
    if metadata.get("max_iterations_reached"):
        st.warning("⚠️ Max iterations reached")
    
    # Show caveats if any
    caveats = metadata.get("caveats", [])
    if caveats:
        with st.expander("⚠️ Caveats", expanded=False):
            for caveat in caveats:
                st.markdown(f"- {caveat}")


def _render_scenario_controls():
    """Render scenario mode controls in the bottom area."""
    scenario = st.session_state.get('scenario_data', {})
    progress = st.session_state.get('scenario_progress', {})
    status = st.session_state.get('scenario_status', 'stopped')
    current_idx = progress.get('current_index', 0)
    total = progress.get('total', 0)
    scenario_name = scenario.get('name', 'Unknown Scenario')

    # Status banner with control button inside
    if status == 'ready':
        # Show red "Run simulation" button
        if st.button("🔴 Run simulation", key="scenario_start_bottom", use_container_width=True, type="primary"):
            st.session_state.scenario_status = 'running'
            st.rerun()
    elif status == 'running':
        # No controls shown during running - questions auto-submit
        pass
    elif status == 'completed':
        # Completion message is already added in advance_scenario_progress()
        # Just show the control area with button
        if st.button("💬 Continue chatting", key="scenario_chat_bottom", use_container_width=True):
            st.session_state.scenario_mode = False
            st.session_state.scenario_status = 'stopped'
            st.session_state.scenario_data = None
            st.session_state.scenario_progress = None
            st.rerun()

    # Auto-submit next scenario question AFTER page is fully rendered
    if should_auto_submit_next_question():
        next_question = get_next_scenario_question()
        if next_question:
            process_question(next_question)
            advance_scenario_progress()
            st.rerun()


def render_chat_page():
    """Render the main chat page."""
    st.markdown("## 💬 Chat with your data")
    
    # Show loaded datasets info or upload button
    if not st.session_state.datasets:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.caption("📊 No dataset loaded yet")
        with col2:
            if st.button("📤 Upload Dataset", use_container_width=True):
                st.session_state.current_page = 'quick_start'
                st.rerun()
    else:
        # Show loaded datasets info
        dataset_names = [ds['name'] for ds in st.session_state.datasets.values()]
        if len(dataset_names) == 1:
            st.caption(f"📊 Working with: {dataset_names[0]}")
        else:
            st.caption(f"📊 Working with {len(dataset_names)} datasets: {', '.join(dataset_names)}")
    
    # Display chat history
    for msg_idx, message in enumerate(st.session_state.messages):
        # Generate timestamp for display in user's timezone
        current_time = utc_to_user_timezone(
            datetime.now(timezone.utc).isoformat(), 
            st.session_state.user_timezone
        )
        
        with st.chat_message(message["role"]):
            # For user messages, show content only
            if message["role"] == "user":
                st.markdown(message["content"])
                continue  # Skip the rest for user messages
            
            # For assistant messages, check architecture version
            metadata = message.get("metadata", {})
            
            # V2 ReAct agent messages - display iterations using shared utilities
            if metadata.get("architecture") == "v2_react":
                _render_v2_react_message(metadata)

            # Display main content based on message type
            if message.get("type") == "visualization" and message.get("figures"):
                _render_visualization_message(message, msg_idx)
            elif message.get("type") == "error":
                st.error(message["content"])
            elif message.get("type") == "success_banner":
                st.success(message["content"])
            elif message.get("type") == "info_banner":
                st.info(message["content"])
            elif message.get("type") == "scenario_status_banner":
                # Render scenario status banner from history (without button)
                if message.get("status") == "running":
                    st.info(message["content"])
                elif message.get("status") == "completed":
                    st.success(message["content"])
            elif not metadata.get("explanation"):
                # Only show content if there's no explanation (to avoid duplication)
                st.markdown(message["content"])

        # Show timestamp outside message bubble for all messages
        st.markdown(f'<div class="chat-timestamp">{current_time}</div>', unsafe_allow_html=True)

    # Bottom controls area - either scenario controls or chat input
    if st.session_state.get('scenario_mode'):
        _render_scenario_controls()
    else:
        # Normal chat input - always show, even without dataset
        if st.session_state.datasets:
            user_question = st.chat_input("Ask a question about your data...")
        else:
            user_question = st.chat_input("Ask me anything...")

        if user_question:
            if not st.session_state.datasets:
                # If no dataset, show helpful message
                st.session_state.messages.append({
                    "role": "user",
                    "content": user_question
                })
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": "I'd be happy to help! However, I work best with data. Please upload a dataset using the button above, and I can analyze it for you.",
                    "type": "info"
                })
            else:
                process_question(user_question)
            st.rerun()
