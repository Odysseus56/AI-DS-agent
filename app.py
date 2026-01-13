# ==== IMPORTS ====
import streamlit as st  # Web UI framework
import pandas as pd  # Data manipulation library
import re  # Regular expressions for log parsing
import os  # For file path operations
from datetime import datetime, timezone, timedelta  # For timestamping sessions and chat timestamps
from data_analyzer import generate_data_summary, get_basic_stats  # Our data analysis module
from llm_client import get_data_summary_from_llm  # Our LLM integration
from code_executor import InteractionLogger, get_log_content, convert_log_to_pdf, execute_unified_code  # Code execution
from supabase_logger import SupabaseLogger, utc_to_pst, utc_to_user_timezone  # Persistent cloud logging and timezone conversion
from dual_logger import DualLogger  # Unified logger for both Supabase and local files
from admin_page import render_admin_page  # Admin panel for viewing logs
from page_modules.about_page import render_about_page  # About page
from page_modules.add_dataset_page import render_add_dataset_page  # Add Dataset page
from page_modules.dataset_page import render_dataset_page  # Dataset page
from page_modules.log_page import render_log_page  # Log page
from page_modules.scenarios_page import (
    render_scenarios_page,
    should_auto_submit_next_question,
    get_next_scenario_question,
    advance_scenario_progress
)  # Scenarios page
from question_processor_v2 import process_question  # V2 ReAct agent
from config import (
    MAX_FILE_SIZE_BYTES,
    MAX_DATASET_ROWS,
    MAX_CHAT_MESSAGES,
    PAGE_TITLE,
    PAGE_ICON,
    DEFAULT_TIMEZONE,
    ERROR_FILE_TOO_LARGE,
    ERROR_INVALID_CSV,
    ERROR_CSV_INFO,
    WARNING_DATASET_EXISTS,
    WARNING_DATASET_TRUNCATED,
    SUCCESS_FILE_UPLOADED,
    SUCCESS_SAMPLE_LOADED
)

# ==== PAGE CONFIGURATION ====
# Must be first Streamlit command - sets browser tab title, icon, and layout
st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==== CUSTOM STYLING ====
# Modern UI improvements without changing color scheme
st.markdown("""
<style>
    /* Buttons - rounded corners and smooth transitions */
    .stButton button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    
    .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    }
    
    /* Chat messages - better spacing and rounded corners */
    [data-testid="stChatMessage"] {
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 1rem;
    }
    
    /* Expanders - rounded corners and better styling */
    .streamlit-expanderHeader {
        border-radius: 8px;
        font-weight: 500;
    }
    
    /* Success messages - rounded corners */
    .stSuccess {
        border-radius: 8px;
    }
    
    /* Error messages - rounded corners */
    .stError {
        border-radius: 8px;
    }
    
    /* Warning messages - rounded corners */
    .stWarning {
        border-radius: 8px;
    }
    
    /* Info messages - rounded corners */
    .stInfo {
        border-radius: 8px;
    }
    
    /* File uploader - modern styling */
    [data-testid="stFileUploader"] {
        border-radius: 12px;
        padding: 2rem;
    }
    
    /* Download buttons - rounded corners */
    .stDownloadButton button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    
    .stDownloadButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    }
    
    /* Headers - better font weight */
    .main h1, .main h2 {
        font-weight: 600;
    }
    
    /* Code blocks - rounded corners */
    .stCodeBlock {
        border-radius: 8px;
    }
    
    /* Metrics - better font weight */
    [data-testid="stMetricValue"] {
        font-weight: 600;
    }
    
    /* Chat timestamps - positioned outside message bubble */
    .chat-timestamp {
        display: block;
        text-align: right;
        opacity: 0.6;
        font-size: 0.85em;
        font-weight: 400;
        color: #888;
        margin-top: -0.5rem;
        margin-bottom: 1rem;
        padding-right: 1rem;
    }
    
    /* Message container wrapper for timestamp positioning */
    .message-wrapper {
        position: relative;
    }
</style>
""", unsafe_allow_html=True)

# ==== TIMEZONE DETECTION ====
# Detect user's timezone and store in session state
if 'user_timezone' not in st.session_state:
    # Default to PST if detection fails
    st.session_state.user_timezone = DEFAULT_TIMEZONE

# JavaScript to detect user's timezone
timezone_js = """
<script>
    // Detect user's timezone
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    
    // Send timezone to Streamlit
    const parent = window.parent;
    if (parent && parent.postMessage) {
        parent.postMessage({
            type: 'streamlit:setComponentValue',
            key: 'timezone_detected',
            value: timezone
        }, '*');
    }
</script>
"""

# Display timezone detection script (hidden)
st.components.v1.html(timezone_js, height=0)

# Check if timezone was detected
if 'timezone_detected' in st.session_state and st.session_state.timezone_detected != st.session_state.user_timezone:
    st.session_state.user_timezone = st.session_state.timezone_detected

# ==== SESSION STATE INITIALIZATION ====
# Initialize all session state variables
if 'session_timestamp' not in st.session_state:
    st.session_state.session_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")

# Multi-dataset structure
if 'datasets' not in st.session_state:
    st.session_state.datasets = {}  # Dict of all loaded datasets

# Unified chat and logger (shared across all datasets)
if 'messages' not in st.session_state:
    st.session_state.messages = []  # Unified chat history

if 'logger' not in st.session_state:
    # Use DualLogger for both Supabase and local file logging
    st.session_state.logger = DualLogger(session_timestamp=st.session_state.session_timestamp)

# UI state
if 'active_dataset_id' not in st.session_state:
    st.session_state.active_dataset_id = None  # Currently viewed dataset

if 'current_page' not in st.session_state:
    st.session_state.current_page = 'add_dataset'  # Default to add dataset page

# Migrate legacy single-dataset state if it exists
if 'df' in st.session_state and st.session_state.df is not None:
    # Migrate old structure to new multi-dataset structure
    legacy_id = st.session_state.get('uploaded_file_name', 'dataset').replace('.csv', '').lower().replace(' ', '_')
    st.session_state.datasets[legacy_id] = {
        'name': st.session_state.get('uploaded_file_name', 'Dataset'),
        'df': st.session_state.df,
        'data_summary': st.session_state.get('data_summary', ''),
        'uploaded_at': st.session_state.session_timestamp
    }
    st.session_state.active_dataset_id = legacy_id
    st.session_state.current_page = 'chat'
    # Clean up old keys
    del st.session_state.df
    if 'uploaded_file_name' in st.session_state:
        del st.session_state.uploaded_file_name
    if 'data_summary' in st.session_state:
        del st.session_state.data_summary

# ==== PAGE HEADER ====
st.title("🤖 AI Data Scientist Assistant")
st.markdown("Your AI-Powered Data Science Partner")

# ==== SIDEBAR NAVIGATION ====
with st.sidebar:
    st.title("📊 Navigation")
    
    # MAIN SECTION
    st.markdown("### 🏠 Main")
    if st.button("💬 Chat", width="stretch", type="primary" if st.session_state.current_page == 'chat' else "secondary"):
        st.session_state.current_page = 'chat'
        st.rerun()
    
    if st.button("📋 Log", width="stretch", type="primary" if st.session_state.current_page == 'log' else "secondary"):
        st.session_state.current_page = 'log'
        st.rerun()
    
    st.divider()
    
    # DATA SECTION
    dataset_count = len(st.session_state.datasets)
    if dataset_count > 0:
        st.markdown(f"### 📊 Data ({dataset_count})")
    else:
        st.markdown("### 📊 Data")
    
    # Show all loaded datasets
    if st.session_state.datasets:
        for ds_id, ds_info in st.session_state.datasets.items():
            is_active = (st.session_state.current_page == 'dataset' and st.session_state.active_dataset_id == ds_id)
            if st.button(f"📄 {ds_info['name']}", width="stretch", type="primary" if is_active else "secondary", key=f"dataset_{ds_id}"):
                st.session_state.active_dataset_id = ds_id
                st.session_state.current_page = 'dataset'
                st.rerun()
    
    if st.button("➕ Add Dataset", width="stretch", type="primary" if st.session_state.current_page == 'add_dataset' else "secondary"):
        st.session_state.current_page = 'add_dataset'
        st.rerun()
    
    st.divider()
    
    # SYSTEM SECTION
    st.markdown("### ⚙️ System")
    if st.button("ℹ️ About", width="stretch", type="primary" if st.session_state.current_page == 'about' else "secondary"):
        st.session_state.current_page = 'about'
        st.rerun()
    
    if st.button("🎬 Scenarios", width="stretch", type="primary" if st.session_state.current_page == 'scenarios' else "secondary"):
        st.session_state.current_page = 'scenarios'
        st.rerun()
    
    if st.button("🔧 Admin", width="stretch", type="primary" if st.session_state.current_page == 'admin' else "secondary"):
        st.session_state.current_page = 'admin'
        st.rerun()

# ==== HELPER FUNCTION: SHARED DATASET PROCESSING ====
def _process_dataset(df: pd.DataFrame, dataset_id: str, filename: str) -> bool:
    """Shared logic for processing and storing a dataset.
    
    Args:
        df: Loaded pandas DataFrame
        dataset_id: Unique identifier for the dataset
        filename: Display name for the dataset
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Auto-generate summary
    with st.spinner("📊 Analyzing your dataset..."):
        data_summary = generate_data_summary(df)
        llm_summary = get_data_summary_from_llm(data_summary)
        
        # Add dataset to collection
        st.session_state.datasets[dataset_id] = {
            'name': filename,
            'df': df,
            'data_summary': data_summary,
            'uploaded_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Set as active dataset
        st.session_state.active_dataset_id = dataset_id
        
        # Add summary to unified chat if this is the first dataset
        if len(st.session_state.datasets) == 1:
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"**Dataset '{filename}' loaded successfully!**\n\n{llm_summary}",
                "type": "summary",
                "metadata": {"dataset_id": dataset_id}
            })
        else:
            # For additional datasets, add a simpler message
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"**Dataset '{filename}' added!** You can now ask questions about it.\n\n{llm_summary}",
                "type": "summary",
                "metadata": {"dataset_id": dataset_id}
            })
        
        # Log the summary
        st.session_state.logger.log_summary_generation(f"Dataset: {filename}", llm_summary)
    
    return True


# ==== HELPER FUNCTION: LOAD SAMPLE DATASET ====
def load_sample_dataset(file_path, filename):
    """Load a sample dataset from the data/ folder."""
    # Generate dataset ID from filename
    dataset_id = filename.replace('.csv', '').lower().replace(' ', '_').replace('-', '_')
    
    # Check if dataset already exists
    if dataset_id in st.session_state.datasets:
        st.warning(f"⚠️ Dataset '{filename}' is already loaded.")
        st.session_state.active_dataset_id = dataset_id
        return True
    
    try:
        # Load CSV with row limit to prevent memory issues
        df = pd.read_csv(file_path, nrows=MAX_DATASET_ROWS)
        
        # Warn if file was truncated
        if len(df) == MAX_DATASET_ROWS:
            st.warning(WARNING_DATASET_TRUNCATED)
    except Exception as e:
        st.error(f"❌ Error reading CSV file: {str(e)}")
        st.info("Please ensure the file is a valid CSV format.")
        return False
    
    # Process the dataset using shared logic
    success = _process_dataset(df, dataset_id, filename)
    
    if success:
        st.success(SUCCESS_SAMPLE_LOADED.format(name=filename))
    
    return success


# ==== HELPER FUNCTION: FILE UPLOAD HANDLER ====
def handle_file_upload(uploaded_file):
    """Process uploaded CSV file and add to datasets."""
    # Validate file size (100MB limit)
    if uploaded_file.size > MAX_FILE_SIZE_BYTES:
        st.error(ERROR_FILE_TOO_LARGE)
        return False
    
    # Generate dataset ID from filename
    dataset_id = uploaded_file.name.replace('.csv', '').lower().replace(' ', '_').replace('-', '_')
    
    # Check if dataset already exists
    if dataset_id in st.session_state.datasets:
        st.warning(WARNING_DATASET_EXISTS.format(name=uploaded_file.name))
        st.session_state.active_dataset_id = dataset_id
        return True
    
    try:
        # Load CSV with row limit to prevent memory issues
        df = pd.read_csv(uploaded_file, nrows=MAX_DATASET_ROWS)
        
        # Warn if file was truncated
        if len(df) == MAX_DATASET_ROWS:
            st.warning(WARNING_DATASET_TRUNCATED)
    except Exception as e:
        st.error(ERROR_INVALID_CSV.format(error=str(e)))
        st.info(ERROR_CSV_INFO)
        return False
    
    # Process the dataset using shared logic
    success = _process_dataset(df, dataset_id, uploaded_file.name)
    
    if success:
        st.success(SUCCESS_FILE_UPLOADED.format(name=uploaded_file.name))
    
    return success

# ==== MAIN CONTENT ROUTING ====

# ==== PAGE: ADD DATASET ====
if st.session_state.current_page == 'add_dataset':
    data_folder = os.path.join(os.path.dirname(__file__), 'data')
    render_add_dataset_page(handle_file_upload, load_sample_dataset, data_folder)

# ==== PAGE: CHAT ====
elif st.session_state.current_page == 'chat':
    if not st.session_state.datasets:
        st.info("👆 Please upload a dataset to start chatting")
        if st.button("Upload Dataset"):
            st.session_state.current_page = 'add_dataset'
            st.rerun()
    else:
        st.markdown("## 💬 Chat with your data")
        
        # Show loaded datasets info
        dataset_names = [ds['name'] for ds in st.session_state.datasets.values()]
        if len(dataset_names) == 1:
            st.caption(f"📊 Working with: {dataset_names[0]}")
        else:
            st.caption(f"📊 Working with {len(dataset_names)} datasets: {', '.join(dataset_names)}")
        
        # Display chat history
        for msg_idx, message in enumerate(st.session_state.messages):
            # Generate timestamp for display in user's timezone
            current_time = utc_to_user_timezone(datetime.now(timezone.utc).isoformat(), st.session_state.user_timezone)
            
            with st.chat_message(message["role"]):
                # For user messages, show content only
                if message["role"] == "user":
                    st.markdown(message["content"])
                    continue  # Skip the rest for user messages
                
                # For assistant messages, check architecture version
                metadata = message.get("metadata", {})
                
                # V2 ReAct agent messages - display iterations exactly as during streaming phase
                if metadata.get("architecture") == "v2_react":
                    st.markdown("**🤖 ReAct Agent V2**")
                    
                    # Display each iteration as an expander (same as streaming phase)
                    iterations = metadata.get("iterations", [])
                    for iteration in iterations:
                        tool_calls = iteration.get("tool_calls", [])
                        tool_names = [tc.get("tool_name", "") for tc in tool_calls]
                        tools_str = ", ".join(tool_names) if tool_names else "thinking..."
                        
                        # Get tool-specific emoji and dynamic title
                        tool_emoji_map = {
                            "profile_data": "🔍",
                            "write_code": "✍️",
                            "execute_code": "▶️",
                            "validate_results": "✓",
                            "explain_findings": "💬"
                        }
                        primary_emoji = tool_emoji_map.get(tool_names[0], "🔄") if tool_names else "🔄"
                        
                        # Get dynamic title combining action with reasoning
                        tool_action_map = {
                            "profile_data": "Profiling data",
                            "write_code": "Writing code",
                            "execute_code": "Executing code",
                            "validate_results": "Validating results",
                            "explain_findings": "Explaining findings"
                        }
                        
                        # Get action prefix - show all tools if multiple
                        if tool_names and len(tool_names) > 0:
                            actions = [tool_action_map.get(tn, tn) for tn in tool_names]
                            action = ", ".join(actions)
                        else:
                            action = "Thinking"
                        
                        # Extract reasoning snippet - always include if available
                        llm_reasoning = iteration.get("llm_reasoning", "")
                        reasoning_snippet = ""
                        if llm_reasoning:
                            lines = llm_reasoning.split('\n')
                            for line in lines:
                                line = line.strip()
                                if len(line) > 20:
                                    reasoning_snippet = line
                                    break
                            if not reasoning_snippet and llm_reasoning:
                                reasoning_snippet = llm_reasoning.strip()
                        
                        # If no LLM reasoning, try to extract from tool arguments (e.g., approach in write_code)
                        if not reasoning_snippet and tool_calls:
                            for tc in tool_calls:
                                tc_name = tc.get("tool_name", "")
                                tc_args = tc.get("arguments", {})
                                if tc_name == "write_code" and "approach" in tc_args:
                                    reasoning_snippet = tc_args["approach"]
                                    break
                                elif tc_name == "explain_findings" and "context" in tc_args:
                                    reasoning_snippet = tc_args["context"]
                                    break
                        
                        # Always combine action with reasoning snippet if available
                        if reasoning_snippet:
                            if len(reasoning_snippet) > 50:
                                reasoning_snippet = reasoning_snippet[:50] + "..."
                            dynamic_title = f"{action} - {reasoning_snippet}"
                        else:
                            dynamic_title = action
                        
                        with st.expander(f"{primary_emoji} Iteration {iteration.get('iteration_num', '?')}: {dynamic_title}", expanded=False):
                            # Show LLM reasoning if present
                            if llm_reasoning:
                                with st.expander("💭 Agent Reasoning", expanded=True):
                                    st.markdown(llm_reasoning)
                            
                            # Show tool calls
                            for tc in tool_calls:
                                status_icon = "✅" if tc.get("success", True) else "❌"
                                duration = tc.get("duration_ms", 0)
                                duration_color = "🔴" if duration > 5000 else "🟡" if duration > 2000 else "🟢"
                                st.markdown(f"**{status_icon} `{tc.get('tool_name', 'unknown')}`** {duration_color} ({duration:.0f}ms)")
                                
                                # Show key info based on tool type
                                tool_name = tc.get("tool_name", "")
                                if tool_name == "write_code":
                                    approach = tc.get("arguments", {}).get("approach", "")
                                    if approach:
                                        st.caption(f"**Approach:** {approach}")
                                    # Show the actual generated code
                                    code = tc.get("result", {}).get("code", "")
                                    if code:
                                        with st.expander("📝 Generated Code", expanded=False):
                                            st.code(code, language="python")
                                elif tool_name == "execute_code":
                                    result = tc.get("result", {})
                                    if result.get("success"):
                                        result_str = result.get('result_str', '')
                                        output_type = result.get('output_type', 'unknown')
                                        
                                        # Format based on output type
                                        if output_type == 'dataframe' or 'DataFrame' in result_str:
                                            with st.expander("📊 Execution Result", expanded=False):
                                                st.code(result_str, language="python")
                                        elif len(result_str) > 200:
                                            with st.expander("📊 Execution Result", expanded=False):
                                                st.code(result_str, language="python")
                                        else:
                                            st.caption(f"**Result:** `{result_str}`")
                                    else:
                                        error_msg = result.get('error', '')
                                        with st.expander("⚠️ Execution Error", expanded=True):
                                            st.error(error_msg)
                                elif tool_name == "validate_results":
                                    result = tc.get("result", {})
                                    is_valid = result.get("is_valid", False)
                                    conf = result.get("confidence", 0)
                                    validation_icon = "✅" if is_valid else "⚠️"
                                    st.caption(f"**{validation_icon} Valid:** {is_valid} | **Confidence:** {conf:.0%}")
                                    
                                    # Show issues if any
                                    issues = result.get("issues", [])
                                    if issues:
                                        with st.expander("⚠️ Validation Issues", expanded=True):
                                            for issue in issues:
                                                st.markdown(f"- {issue}")
                                    
                                    # Show suggestions if any
                                    suggestions = result.get("suggestions", [])
                                    if suggestions:
                                        with st.expander("💡 Suggestions", expanded=False):
                                            for suggestion in suggestions:
                                                st.markdown(f"- {suggestion}")
                                elif tool_name == "profile_data":
                                    # Show detailed data profile
                                    result = tc.get("result", {})
                                    datasets = result.get("datasets", {})
                                    if datasets:
                                        with st.expander(f"📋 Data Profile ({len(datasets)} dataset(s))", expanded=False):
                                            for ds_name, ds_info in datasets.items():
                                                st.markdown(f"**{ds_name}:** {ds_info.get('shape', 'N/A')}")
                                                columns = ds_info.get('columns', {})
                                                if columns:
                                                    st.caption(f"Columns: {', '.join(list(columns.keys())[:5])}{'...' if len(columns) > 5 else ''}")
                                elif tool_name == "explain_findings":
                                    result = tc.get("result", {})
                                    explanation = result.get("explanation", "")
                                    if explanation:
                                        with st.expander("💬 Explanation", expanded=False):
                                            st.markdown(explanation)
                                
                                if tc.get("error"):
                                    st.error(f"**Error:** {tc.get('error')}")
                    
                    # Show warnings if any (removed redundant summary and code sections)
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

                # Display main content
                if message.get("type") == "visualization" and message.get("figures"):
                    # Display figures only (explanation is in Final Report dropdown)
                    import plotly.io as pio
                    import io
                    
                    for idx, fig in enumerate(message["figures"]):
                        # Check if it's a Plotly figure or matplotlib figure
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

                elif message.get("type") == "error":
                    st.error(message["content"])
                elif not metadata.get("explanation"):
                    # Only show content if there's no explanation (to avoid duplication)
                    st.markdown(message["content"])

            # Show timestamp outside message bubble for all messages
            st.markdown(f'<div class="chat-timestamp">{current_time}</div>', unsafe_allow_html=True)

        # Bottom controls area - either scenario controls or chat input
        if st.session_state.get('scenario_mode'):
            # Scenario controls in the bottom area (hijacking the sticky input area)
            scenario = st.session_state.get('scenario_data', {})
            progress = st.session_state.get('scenario_progress', {})
            status = st.session_state.get('scenario_status', 'stopped')
            current_idx = progress.get('current_index', 0)
            total = progress.get('total', 0)
            scenario_name = scenario.get('name', 'Unknown Scenario')

            # Use columns for status + controls in bottom bar
            status_col, pause_col, stop_col = st.columns([4, 1, 1])

            with status_col:
                if status == 'running':
                    st.info(f"🎬 **Running:** {scenario_name} ({current_idx + 1}/{total})")
                elif status == 'paused':
                    st.warning(f"⏸️ **Paused:** {scenario_name} ({current_idx + 1}/{total})")
                elif status == 'completed':
                    st.success(f"✅ **Completed:** {scenario_name} ({total}/{total})")

            with pause_col:
                if status == 'running':
                    if st.button("⏸️ Pause", key="scenario_pause_bottom", use_container_width=True):
                        st.session_state.scenario_status = 'paused'
                        st.rerun()
                elif status == 'paused':
                    if st.button("▶️ Resume", key="scenario_resume_bottom", use_container_width=True):
                        st.session_state.scenario_status = 'running'
                        st.rerun()
                elif status == 'completed':
                    if st.button("🔄 New", key="scenario_new_bottom", use_container_width=True):
                        st.session_state.scenario_mode = False
                        st.session_state.scenario_status = 'stopped'
                        st.session_state.scenario_data = None
                        st.session_state.scenario_progress = None
                        st.session_state.current_page = 'scenarios'
                        st.rerun()

            with stop_col:
                if status in ['running', 'paused']:
                    if st.button("⏹️ Stop", key="scenario_stop_bottom", use_container_width=True):
                        st.session_state.scenario_mode = False
                        st.session_state.scenario_status = 'stopped'
                        st.session_state.scenario_data = None
                        st.session_state.scenario_progress = None
                        st.rerun()
                elif status == 'completed':
                    if st.button("💬 Chat", key="scenario_chat_bottom", use_container_width=True):
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
        else:
            # Normal chat input
            user_question = st.chat_input("Ask a question about your data...")

            if user_question:
                process_question(user_question)
                st.rerun()

# ==== PAGE: LOG ====
elif st.session_state.current_page == 'log':
    render_log_page(st.session_state.session_timestamp)

# ==== PAGE: DATASET ====
elif st.session_state.current_page == 'dataset':
    render_dataset_page()

# ==== PAGE: ABOUT ====
elif st.session_state.current_page == 'about':
    render_about_page()

# ==== PAGE: ADMIN ====
elif st.session_state.current_page == 'admin':
    render_admin_page(st.session_state.logger)

# ==== PAGE: SCENARIOS ====
elif st.session_state.current_page == 'scenarios':
    scenarios_folder = os.path.join(os.path.dirname(__file__), 'tests', 'test_scenarios')
    render_scenarios_page(load_sample_dataset, scenarios_folder)