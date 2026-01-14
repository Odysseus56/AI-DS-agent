# ==== IMPORTS ====
import streamlit as st  # Web UI framework
import os  # For file path operations
from datetime import datetime  # For timestamping sessions

from dual_logger import DualLogger  # Unified logger for both Supabase and local files
from admin_page import render_admin_page  # Admin panel for viewing logs
from config import PAGE_TITLE, PAGE_ICON, DEFAULT_TIMEZONE

# Page modules - all page rendering functions
from page_modules import (
    render_about_page,
    render_add_dataset_page,
    render_dataset_page,
    render_log_page,
    render_scenarios_page,
    render_chat_page,
    render_quick_start_page,
    handle_file_upload,
    load_sample_dataset
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
    
    /* Info messages - rounded corners and consistent styling */
    .stInfo {
        border-radius: 8px;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
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
        margin-top: 0.1rem;
        margin-bottom: 0.5rem;
        padding-right: 1rem;
    }
    
    /* Message container wrapper for timestamp positioning */
    .message-wrapper {
        position: relative;
    }
    
    /* Reduce top padding in main content area */
    .block-container {
        padding-top: 2rem;
    }
    
    /* Left-align sidebar button text */
    section[data-testid="stSidebar"] .stButton button {
        text-align: left !important;
        justify-content: flex-start !important;
        padding-left: 1rem !important;
    }
    
    section[data-testid="stSidebar"] .stButton button p {
        text-align: left !important;
        width: 100%;
    }
    
    section[data-testid="stSidebar"] .stButton button div {
        text-align: left !important;
        justify-content: flex-start !important;
        width: 100%;
    }
    
    /* Improve tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 12px 24px;
        font-weight: 500;
    }
    
    /* Better spacing for file uploader */
    [data-testid="stFileUploader"] section {
        padding: 3rem 2rem;
    }
    
    /* Reduce excessive spacing in captions */
    .stCaption {
        margin-top: -0.5rem;
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
    st.session_state.current_page = 'quick_start'  # Default to quick start page

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

# ==== SIDEBAR NAVIGATION ====
with st.sidebar:
    # MAIN SECTION
    st.markdown("### 🏠 Main")
    if st.button("🚀 Quick Start", width="stretch", type="primary" if st.session_state.current_page == 'quick_start' else "secondary"):
        st.session_state.current_page = 'quick_start'
        st.rerun()
    
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

# ==== MAIN CONTENT ROUTING ====

# ==== PAGE: QUICK START ====
if st.session_state.current_page == 'quick_start':
    data_folder = os.path.join(os.path.dirname(__file__), 'data')
    scenarios_folder = os.path.join(os.path.dirname(__file__), 'tests', 'test_scenarios')
    render_quick_start_page(handle_file_upload, load_sample_dataset, data_folder, scenarios_folder)

# ==== PAGE: ADD DATASET ====
elif st.session_state.current_page == 'add_dataset':
    data_folder = os.path.join(os.path.dirname(__file__), 'data')
    render_add_dataset_page(handle_file_upload, load_sample_dataset, data_folder)

# ==== PAGE: CHAT ====
elif st.session_state.current_page == 'chat':
    render_chat_page()

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