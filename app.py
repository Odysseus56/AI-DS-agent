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
    
    st.success(SUCCESS_SAMPLE_LOADED.format(name=filename))
    return True

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
    
    # Auto-generate summary
    with st.spinner("📊 Analyzing your dataset..."):
        data_summary = generate_data_summary(df)
    
    with st.spinner("🤖 Generating AI insights..."):
        llm_summary = get_data_summary_from_llm(data_summary)
        
        # Add dataset to collection
        st.session_state.datasets[dataset_id] = {
            'name': uploaded_file.name,
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
                "content": f"**Dataset '{uploaded_file.name}' loaded successfully!**\n\n{llm_summary}",
                "type": "summary",
                "metadata": {"dataset_id": dataset_id}
            })
        else:
            # For additional datasets, add a simpler message
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"**Dataset '{uploaded_file.name}' added!** You can now ask questions about it.\n\n{llm_summary}",
                "type": "summary",
                "metadata": {"dataset_id": dataset_id}
            })
        
        # Log the summary
        st.session_state.logger.log_summary_generation(f"Dataset: {uploaded_file.name}", llm_summary)
    
    st.success(SUCCESS_FILE_UPLOADED.format(name=uploaded_file.name))
    return True

# ==== MAIN CONTENT ROUTING ====

# ==== PAGE: ADD DATASET ====
if st.session_state.current_page == 'add_dataset':
    st.markdown("## 📤 Upload Dataset")
    st.markdown("Upload a CSV file to get started with AI-powered data analysis.")
    
    uploaded_file = st.file_uploader("Choose a CSV file", type="csv", key="file_uploader")
    
    if uploaded_file is not None:
        if handle_file_upload(uploaded_file):
            # Switch to chat after successful upload
            st.session_state.current_page = 'chat'
            st.rerun()
    
    st.divider()
    
    # Sample datasets section
    st.markdown("### 📚 Or Load a Sample Dataset")
    st.markdown("Try out the app with pre-loaded sample datasets.")
    
    # Get sample datasets from data/ folder
    # Use relative path that works both locally and on Streamlit Cloud
    data_folder = os.path.join(os.path.dirname(__file__), 'data')
    
    if os.path.exists(data_folder):
        sample_files = [f for f in os.listdir(data_folder) if f.endswith('.csv')]
        
        if sample_files:
            # Create columns for sample dataset buttons
            cols = st.columns(min(len(sample_files), 3))
            
            for idx, filename in enumerate(sorted(sample_files)):
                col_idx = idx % 3
                with cols[col_idx]:
                    # Create a nice display name
                    display_name = filename.replace('.csv', '').replace('_', ' ').title()
                    
                    if st.button(f"📊 {display_name}", key=f"sample_{filename}", width='stretch'):
                        file_path = os.path.join(data_folder, filename)
                        if load_sample_dataset(file_path, filename):
                            # Switch to chat after successful load
                            st.session_state.current_page = 'chat'
                            st.rerun()
        else:
            st.info("No sample datasets available in the data/ folder.")
    else:
        st.info("Sample datasets folder not found. Upload your own CSV file above.")

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
        for message in st.session_state.messages:
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
                            
                            # Prepare PNG export
                            png_buf = io.BytesIO()
                            try:
                                fig.write_image(png_buf, format='png', width=1200, height=800, scale=2)
                                png_buf.seek(0)
                                png_available = True
                            except Exception as e:
                                print(f"[WARNING] Could not export Plotly to PNG: {e}")
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
                                    key=f"history_plotly_html_{idx}_{message.get('content', '')[:20]}"
                                )
                            with col2:
                                if png_available:
                                    st.download_button(
                                        label="💾 Download PNG",
                                        data=png_buf,
                                        file_name=f"{title}.png",
                                        mime="image/png",
                                        help="Download high-resolution PNG image",
                                        key=f"history_plotly_png_{idx}_{message.get('content', '')[:20]}"
                                    )
                                else:
                                    st.button(
                                        label="💾 Download PNG",
                                        disabled=True,
                                        help="PNG export requires kaleido: pip install kaleido",
                                        key=f"history_plotly_png_disabled_{idx}_{message.get('content', '')[:20]}"
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
                                    key=f"history_matplotlib_{idx}_{message.get('content', '')[:20]}"
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
                            
                            # Prepare PNG export
                            png_buf = io.BytesIO()
                            try:
                                fig.write_image(png_buf, format='png', width=1200, height=800, scale=2)
                                png_buf.seek(0)
                                png_available = True
                            except Exception as e:
                                print(f"[WARNING] Could not export Plotly to PNG: {e}")
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
                                        help="PNG export requires kaleido: pip install kaleido",
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
    st.markdown("## 📋 Session Logs")
    
    # Download buttons at top
    col_session, col_global = st.columns(2)
    with col_session:
        st.markdown("**Current Session Log:**")
        st.download_button(
            label="📥 Download Session Markdown",
            data=get_log_content(session_timestamp=st.session_state.session_timestamp),
            file_name=f"log_{st.session_state.session_timestamp}.md",
            mime="text/markdown",
            width="stretch"
        )
    with col_global:
        st.markdown("**All Sessions Log:**")
        st.download_button(
            label="📥 Download Global Markdown",
            data=get_log_content(session_timestamp=None),
            file_name="log_global.md",
            mime="text/markdown",
            width="stretch"
        )
    
    st.divider()
    
    # Parse and display log with collapsible sections
    # Split log into interactions
    interactions = re.split(r'(?=## Interaction #)', get_log_content(session_timestamp=st.session_state.session_timestamp))
    
    # Skip header (first element before any interaction)
    for interaction in interactions[1:]:
        lines = interaction.split('\n')
        
        # Extract interaction number and type
        header_line = lines[0] if lines else ''
        match = re.match(r'## Interaction #(\d+) - (.+)', header_line)
        
        if match:
            interaction_num = match.group(1)
            interaction_type = match.group(2)
            
            # Extract timestamp from second line
            timestamp = ''
            if len(lines) > 1:
                timestamp_match = re.match(r'\*(.+?)\*', lines[1])
                if timestamp_match:
                    timestamp = timestamp_match.group(1).strip()
            
            # Determine success/failure from interaction type
            status_emoji = '✅' if '✅' in interaction_type else ('❌' if '❌' in interaction_type else '📝')
            
            # Extract user question/request or detect upload
            user_question = ''
            is_upload = 'Executive Summary' in interaction_type
            
            if is_upload:
                # For uploads, extract filename from session state or content
                user_question = "UPLOAD: New Dataset"
                # Try to extract filename from the interaction content
                content_str = '\n'.join(lines)
                # Look for patterns like "File uploaded: filename.csv"
                filename_match = re.search(r'(?:uploaded|file):\s*([^\n]+\.csv)', content_str, re.IGNORECASE)
                if filename_match:
                    user_question = f"UPLOAD: {filename_match.group(1).strip()}"
                elif st.session_state.uploaded_file_name:
                    user_question = f"UPLOAD: {st.session_state.uploaded_file_name}"
            else:
                # Extract user question/request
                for i, line in enumerate(lines):
                    if line.startswith('**User Question:**') or line.startswith('**User Request:**'):
                        # Get next non-empty line
                        for j in range(i+1, min(i+5, len(lines))):
                            if lines[j].strip() and not lines[j].startswith('*') and not lines[j].startswith('#'):
                                user_question = lines[j].strip()
                                break
                        break
            
            # Display interaction with expander - include timestamp and status emoji
            expander_title = f"{status_emoji} **#{interaction_num}** • {timestamp} • {user_question[:60]}{'...' if len(user_question) > 60 else ''}"
            with st.expander(expander_title, expanded=False):
                # Parse and structure the content
                content = '\n'.join(lines)
                
                # Extract sections
                user_section = ''
                plan_section = ''
                code_section = ''
                result_section = ''
                evaluation_section = ''
                answer_section = ''
                
                # Find user input
                user_match = re.search(r'\*\*User (Question|Request):\*\*\s*\n(.+?)(?=\n\n|\*\*)', content, re.DOTALL)
                if user_match:
                    user_section = user_match.group(2).strip()
                elif is_upload:
                    user_section = "New dataset uploaded and analyzed"
                
                # Find execution plan (Step 1)
                plan_match = re.search(r'\*\*Execution Plan:\*\*\s*\n(.+?)(?=\n\n\*\*|$)', content, re.DOTALL)
                if plan_match:
                    plan_section = plan_match.group(1).strip()
                
                # Find code
                code_match = re.search(r'\*\*Generated Code:\*\*\s*\n```python\n(.+?)\n```', content, re.DOTALL)
                if code_match:
                    code_section = code_match.group(1).strip()
                
                # Find execution result
                result_match = re.search(r'\*\*Execution Result:\*\*\s*\n```\n(.+?)\n```', content, re.DOTALL)
                if result_match:
                    result_section = result_match.group(1).strip()
                
                # Find error if any
                error_match = re.search(r'\*\*Error:\*\*\s*\n```\n(.+?)\n```', content, re.DOTALL)
                if error_match:
                    result_section = f"❌ Error:\n{error_match.group(1).strip()}"
                
                # Find evaluation (Step 3)
                evaluation_match = re.search(r'\*\*Evaluation:\*\*\s*\n(.+?)(?=\n\n\*\*|\n---|$)', content, re.DOTALL)
                if evaluation_match:
                    evaluation_section = evaluation_match.group(1).strip()
                
                # Find final answer or explanation
                answer_match = re.search(r'\*\*Final Answer:\*\*\s*\n(.+?)(?=\n---|$)', content, re.DOTALL)
                if answer_match:
                    answer_section = answer_match.group(1).strip()
                else:
                    # Try AI Response for text Q&A
                    answer_match = re.search(r'\*\*AI Response:\*\*\s*\n(.+?)(?=\n---|$)', content, re.DOTALL)
                    if answer_match:
                        answer_section = answer_match.group(1).strip()
                    else:
                        # Try Explanation for visualizations
                        answer_match = re.search(r'\*\*Explanation:\*\*\s*\n(.+?)(?=\n\*\*|\n---|$)', content, re.DOTALL)
                        if answer_match:
                            answer_section = answer_match.group(1).strip()
                        elif is_upload:
                            # For uploads, show the summary content
                            summary_match = re.search(r'\*[0-9\-: ]+\*\s*\n\n(.+?)(?=\n---|$)', content, re.DOTALL)
                            if summary_match:
                                answer_section = summary_match.group(1).strip()
                
                # Display structured sections - matching chat display with debug dropdowns
                
                # User Input (preserved in dropdown)
                if user_section:
                    with st.expander("📝 User Input", expanded=True):
                        st.markdown(user_section)
                
                # Debug Dropdowns (matching chat structure)
                
                # Step 1: Execution Planning
                if plan_section:
                    with st.expander("🧠 Step 1: Execution Planning", expanded=False):
                        st.markdown(plan_section)
                
                # Step 2: Code Generation
                if code_section:
                    with st.expander("💻 Step 2: Code Generation", expanded=False):
                        st.code(code_section, language="python")
                
                # Code Execution Output
                if result_section:
                    with st.expander("⚙️ Code Execution Output", expanded=False):
                        st.code(result_section)
                
                # Step 3: Critical Evaluation
                if evaluation_section:
                    with st.expander("🔍 Step 3: Critical Evaluation", expanded=False):
                        st.markdown(evaluation_section)
                
                # Final Answer (main content)
                if answer_section:
                    st.markdown(answer_section)
                
                # Show visualizations if present
                viz_matches = re.findall(r'!\[Visualization \d+\]\(data:image/png;base64,([^)]+)\)', content)
                if viz_matches:
                    st.divider()
                    st.markdown("### 📊 Visualizations")
                    for i, base64_img in enumerate(viz_matches, 1):
                        # Use columns to control max width
                        col1, col2, col3 = st.columns([1, 3, 1])
                        with col2:
                            st.image(f"data:image/png;base64,{base64_img}", caption=f"Visualization {i}", width="stretch")

# ==== PAGE: DATASET ====
elif st.session_state.current_page == 'dataset':
    if not st.session_state.datasets or st.session_state.active_dataset_id not in st.session_state.datasets:
        st.warning("No dataset loaded. Please upload a dataset first.")
        if st.button("Upload Dataset"):
            st.session_state.current_page = 'add_dataset'
            st.rerun()
    else:
        # Get active dataset
        active_ds = st.session_state.datasets[st.session_state.active_dataset_id]
        df = active_ds['df']
        dataset_name = active_ds['name']
        
        st.markdown(f"## 📊 {dataset_name}")
        
        # Create tabs for dataset views
        tab1, tab2, tab3, tab4 = st.tabs(["📄 Summary", "📊 Explorer", "📈 Details", "⚙️ Settings"])
        
        # TAB 1: SUMMARY (Executive Summary)
        with tab1:
            st.markdown("### Executive Summary")
            
            # Find and display the executive summary for this dataset
            summary_message = None
            for msg in st.session_state.messages:
                if (msg.get("type") == "summary" and 
                    msg.get("metadata", {}).get("dataset_id") == st.session_state.active_dataset_id):
                    summary_message = msg
                    break
            
            if summary_message:
                st.markdown(summary_message["content"])
            else:
                # Show data summary if no LLM summary found
                st.markdown(active_ds['data_summary'])
        
        # TAB 2: EXPLORER (Data Table)
        with tab2:
            st.markdown("### Data Explorer")
            st.dataframe(df, width="stretch", height=600)
        
        # TAB 3: DETAILS (Stats and Technical Info)
        with tab3:
            st.markdown("### Dataset Details")
            
            # Dataset Overview Stats
            st.subheader("📊 Overview")
            stats = get_basic_stats(df)
            
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("Rows", f"{stats['rows']:,}")
            with col2:
                st.metric("Columns", f"{stats['columns']}")
            with col3:
                st.metric("Missing Cells", f"{stats['missing_cells']:,}")
            with col4:
                st.metric("Duplicate Rows", f"{stats['duplicate_rows']:,}")
            with col5:
                st.metric("Memory Usage", f"{stats['memory_usage_mb']:.2f} MB")
            
            st.divider()
            
            # Technical Summary
            st.subheader("📈 Technical Summary")
            st.text(active_ds['data_summary'])
        
        # TAB 4: SETTINGS (Dataset Management)
        with tab4:
            st.markdown("### Dataset Settings")
            
            # Dataset metadata
            st.subheader("📋 Metadata")
            st.write(f"**Name:** {dataset_name}")
            st.write(f"**Dataset ID:** {st.session_state.active_dataset_id}")
            st.write(f"**Rows:** {len(df):,}")
            st.write(f"**Columns:** {len(df.columns)}")
            st.write(f"**Uploaded:** {active_ds['uploaded_at']}")
            
            st.divider()
            
            # Delete dataset
            st.subheader("⚠️ Danger Zone")
            if len(st.session_state.datasets) == 1:
                st.warning("Deleting this dataset will remove all data and chat history.")
            else:
                st.warning(f"Deleting this dataset will remove it from the collection. You have {len(st.session_state.datasets)} datasets loaded.")
            
            if st.button("🗑️ Delete Dataset", type="secondary"):
                # Remove dataset from collection
                del st.session_state.datasets[st.session_state.active_dataset_id]
                
                # If no datasets left, go to add dataset page
                if not st.session_state.datasets:
                    st.session_state.active_dataset_id = None
                    st.session_state.current_page = 'add_dataset'
                else:
                    # Switch to first available dataset
                    st.session_state.active_dataset_id = list(st.session_state.datasets.keys())[0]
                    st.session_state.current_page = 'dataset'

                st.rerun()

# ==== PAGE: ABOUT ====
elif st.session_state.current_page == 'about':
    st.markdown("""
    ### 🎯 Key Strengths

    **1. Writes Code to Analyze Datasets**  
    Generates Python code for statistical analysis, ML models, and data transformations.

    **2. Multi-Dataset Intelligence**  
    Analyze across multiple datasets in one conversation with automatic context management.

    **3. Complete Transparency**  
    4-stage workflow shows execution planning, code generation, evaluation, and final report.

    **4. Auto Error Recovery**  
    Self-debugging with up to 3 retry attempts - GPT-4 fixes errors automatically.

    ---
    
    ### 🛠️ Technical Stack

    - **LLM:** GPT-4o for code generation, GPT-4o-mini for planning
    - **Data:** pandas, numpy, scipy, statsmodels
    - **Viz:** Plotly, matplotlib, seaborn
    - **ML:** scikit-learn
    - **UI:** Streamlit

    ---
    
    ### 💡 Use Cases

    - **Business:** Customer segmentation, campaign analysis, revenue forecasting
    - **Research:** Hypothesis testing, experimental design, statistical modeling
    - **Operations:** Process optimization, anomaly detection, trend analysis
    - **Compliance:** Auditable workflows with full documentation

    ---
    
    ### 🚀 Getting Started

    1. Upload dataset(s) via "Add Dataset"
    2. Ask questions in natural language
    3. Expand debug dropdowns to see workflow
    4. Download logs for reproducibility
    """)

    st.divider()

    st.markdown("*Built with ❤️ for data-driven decision making*")

# ==== PAGE: ADMIN ====
elif st.session_state.current_page == 'admin':
    render_admin_page(st.session_state.logger)