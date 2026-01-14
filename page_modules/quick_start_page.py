"""Quick Start page for AI Data Scientist Agent.

This page provides three paths for users to begin:
1. Upload their own CSV data
2. Load a sample dataset
3. Run an interactive demo scenario

All paths lead to the Chat page with data loaded and ready.
"""
import os
import streamlit as st
from .add_dataset_page import DATASET_METADATA


def render_quick_start_page(handle_file_upload, load_sample_dataset, data_folder: str, scenarios_folder: str):
    """Render the Quick Start page with three tabs.
    
    Args:
        handle_file_upload: Function to handle uploaded CSV files
        load_sample_dataset: Function to load sample datasets
        data_folder: Path to the folder containing sample datasets
        scenarios_folder: Path to the folder containing scenario JSON files
    """
    st.markdown("## 🚀 Quick Start")
    
    # Create three tabs
    tab1, tab2, tab3 = st.tabs([
        "📤 Upload Your Data",
        "📊 Try Sample Data", 
        "🎬 Watch Demo"
    ])
    
    # TAB 1: Upload Your Data
    with tab1:
        _render_upload_tab(handle_file_upload)
    
    # TAB 2: Try Sample Data
    with tab2:
        _render_sample_data_tab(load_sample_dataset, data_folder)
    
    # TAB 3: Watch Demo
    with tab3:
        _render_demo_tab(load_sample_dataset, scenarios_folder, data_folder)


def _render_upload_tab(handle_file_upload):
    """Render the Upload Your Data tab."""
    st.markdown("")
    
    # File uploader with prominent styling
    uploaded_file = st.file_uploader(
        "Choose a CSV file",
        type="csv",
        key="quick_start_file_uploader",
        help="Upload a CSV file to begin analysis"
    )
    
    if uploaded_file is not None:
        if handle_file_upload(uploaded_file):
            # Switch to chat after successful upload
            st.session_state.current_page = 'chat'
            st.rerun()


def _render_sample_data_tab(load_sample_dataset, data_folder: str):
    """Render the Try Sample Data tab."""
    st.markdown("")
    
    if not os.path.exists(data_folder):
        st.warning("Sample datasets folder not found.")
        return
    
    sample_files = [f for f in os.listdir(data_folder) if f.endswith('.csv')]
    
    if not sample_files:
        st.warning("No sample datasets available.")
        return
    
    # Show all datasets
    all_datasets = []
    
    for filename in sorted(sample_files):
        metadata = DATASET_METADATA.get(filename, {
            'name': filename.replace('.csv', '').replace('_', ' ').title(),
            'icon': '📊',
            'description': 'Sample dataset for analysis.',
            'size': 'Unknown',
            'category': 'Other'
        })
        all_datasets.append((filename, metadata))
    
    # Render all datasets
    for filename, metadata in all_datasets:
        _render_sample_dataset_card(filename, metadata, data_folder, load_sample_dataset)


def _render_sample_dataset_card(filename: str, metadata: dict, data_folder: str, load_sample_dataset):
    """Render a sample dataset card in the Quick Start page.
    
    Args:
        filename: Name of the dataset file
        metadata: Dictionary containing dataset metadata
        data_folder: Path to the folder containing sample datasets
        load_sample_dataset: Function to load sample datasets
    """
    dataset_id = filename.replace('.csv', '').lower().replace(' ', '_').replace('-', '_')
    is_loaded = dataset_id in st.session_state.datasets
    
    col1, col2 = st.columns([0.8, 0.2])
    
    with col1:
        st.markdown(f"**{metadata['icon']} {metadata['name']}**")
        st.caption(f"{metadata['description']} • {metadata['size']}")
    
    with col2:
        if is_loaded:
            st.button("✓ Loaded", key=f"qs_sample_{filename}", use_container_width=True, disabled=True)
        else:
            loading_key = f"qs_loading_{filename}"
            if loading_key not in st.session_state:
                st.session_state[loading_key] = False
            
            if st.session_state[loading_key]:
                st.button("⏳ Loading...", key=f"qs_sample_{filename}_loading", use_container_width=True, disabled=True)
            else:
                if st.button("Load →", key=f"qs_sample_{filename}", use_container_width=True, type="primary"):
                    st.session_state[loading_key] = True
                    st.rerun()
            
            if st.session_state[loading_key] and not is_loaded:
                file_path = os.path.join(data_folder, filename)
                if load_sample_dataset(file_path, filename):
                    st.session_state[loading_key] = False
                    st.session_state.current_page = 'chat'
                    st.rerun()
                else:
                    st.session_state[loading_key] = False
                    st.rerun()
    
    st.markdown("---")


def _render_demo_tab(load_sample_dataset, scenarios_folder: str, data_folder: str):
    """Render the Watch Demo tab with curated scenarios."""
    st.markdown("")
    
    # Import scenario loading functions
    from .scenarios_page import load_scenarios, get_scenario_category, get_scenario_difficulty, CATEGORY_METADATA, DIFFICULTY_COLORS
    
    scenarios = load_scenarios(scenarios_folder)
    
    if not scenarios:
        st.warning("No demo scenarios available.")
        return
    
    # Show all scenarios grouped by category
    from .scenarios_page import group_scenarios_by_category, CATEGORY_METADATA
    
    grouped = group_scenarios_by_category(scenarios)
    sorted_categories = sorted(grouped.keys())
    
    for category in sorted_categories:
        category_meta = CATEGORY_METADATA.get(category, CATEGORY_METADATA['other'])
        scenario_list = grouped[category]
        
        # Category header
        st.markdown(f"#### {category_meta['icon']} {category_meta['name']}")
        
        # Render scenario cards
        for scenario in scenario_list:
            _render_demo_scenario_card(scenario, load_sample_dataset, data_folder)
        
        st.markdown("")  # Add spacing between categories


def _get_curated_scenarios(scenarios: dict) -> list:
    """Get a curated list of featured scenarios for Quick Start.
    
    Args:
        scenarios: Dictionary of all scenarios
        
    Returns:
        list: List of curated scenario objects
    """
    from .scenarios_page import get_scenario_category
    
    # Priority order for categories
    priority_categories = [
        'A_statistical_analysis',
        'H_domain_specific',
        'D_natural_language',
        'B_data_quality'
    ]
    
    curated = []
    seen_categories = set()
    
    # Pick 1-2 scenarios from priority categories
    for category in priority_categories:
        category_scenarios = [s for s in scenarios.values() if get_scenario_category(s) == category]
        
        if category_scenarios and category not in seen_categories:
            # Sort by name and take first one
            category_scenarios.sort(key=lambda s: s.get('name', ''))
            curated.append(category_scenarios[0])
            seen_categories.add(category)
            
            # Limit to 4-5 featured scenarios
            if len(curated) >= 4:
                break
    
    return curated


def _render_demo_scenario_card(scenario: dict, load_sample_dataset, data_folder: str):
    """Render a demo scenario card in the Quick Start page.
    
    Args:
        scenario: The scenario data to display
        load_sample_dataset: Function to load sample datasets
        data_folder: Path to the folder containing sample datasets
    """
    from .scenarios_page import get_scenario_difficulty, DIFFICULTY_COLORS, start_scenario
    
    difficulty = get_scenario_difficulty(scenario)
    difficulty_icon = DIFFICULTY_COLORS.get(difficulty, '🟡')
    
    dataset_names = [ds.get('id', 'unknown') for ds in scenario.get('datasets', [])]
    question_count = len(scenario.get('questions', []))
    
    col1, col2 = st.columns([0.8, 0.2])
    
    with col1:
        st.markdown(f"**{scenario.get('name', 'Unnamed Scenario')}** {difficulty_icon}")
        st.caption(f"{scenario.get('description', 'No description')}")
        st.caption(f"📊 {', '.join(dataset_names)} • ❓ {question_count} questions")
    
    with col2:
        if (st.session_state.get('scenario_mode') and 
            st.session_state.get('scenario_data', {}).get('id') == scenario.get('id')):
            st.button("▶️ Running", key=f"qs_scenario_{scenario['id']}", 
                     use_container_width=True, disabled=True)
        else:
            if st.button("Run →", key=f"qs_scenario_{scenario['id']}", 
                        use_container_width=True, type="primary"):
                # Clear chat and datasets for clean start
                st.session_state.messages = []
                st.session_state.datasets = {}
                st.session_state.active_dataset_id = None
                
                # Start the scenario
                start_scenario(scenario, load_sample_dataset)
                # Note: start_scenario already calls st.rerun()
    
    st.markdown("---")
