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
from langgraph_agent import agent_app  # LangGraph agent
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
from node_display import (
    display_all_nodes,
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
)  # Reusable node display functions

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
    
    # Main navigation buttons
    if st.button("💬 Chat", width="stretch", type="primary" if st.session_state.current_page == 'chat' else "secondary"):
        st.session_state.current_page = 'chat'
        st.rerun()
    
    if st.button("📋 Log", width="stretch", type="primary" if st.session_state.current_page == 'log' else "secondary"):
        st.session_state.current_page = 'log'
        st.rerun()
    
    if st.button("ℹ️ About", width="stretch", type="primary" if st.session_state.current_page == 'about' else "secondary"):
        st.session_state.current_page = 'about'
        st.rerun()
    
    if st.button("🔧 Admin", width="stretch", type="primary" if st.session_state.current_page == 'admin' else "secondary"):
        st.session_state.current_page = 'admin'
        st.rerun()
    
    st.divider()
    
    # Dataset section - show all loaded datasets
    if st.session_state.datasets:
        st.markdown("**📊 Datasets**")
        for ds_id, ds_info in st.session_state.datasets.items():
            is_active = (st.session_state.current_page == 'dataset' and st.session_state.active_dataset_id == ds_id)
            if st.button(f"📊 {ds_info['name']}", width="stretch", type="primary" if is_active else "secondary", key=f"dataset_{ds_id}"):
                st.session_state.active_dataset_id = ds_id
                st.session_state.current_page = 'dataset'
                st.rerun()
    
    if st.button("➕ Add Dataset", width="stretch", type="primary" if st.session_state.current_page == 'add_dataset' else "secondary"):
        st.session_state.current_page = 'add_dataset'
        st.rerun()
    
    st.divider()

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
    
    with st.spinner("🤖 Generating AI insights..."):
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
                
                # For assistant messages, use reusable display function
                metadata = message.get("metadata", {})
                display_all_nodes(metadata, expanded_final_report=True)

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

        # Chat input
        user_question = st.chat_input("Ask a question about your data...")

        if user_question:
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
                                    with explanation_placeholder.container():
                                        display_node_6_explanation(node_state["explanation"], expanded=True)
                
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
                    import plotly.io as pio
                    import io
                    
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