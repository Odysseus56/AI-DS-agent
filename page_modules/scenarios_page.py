"""Scenarios page for AI Data Scientist Agent.

This module provides a UI for browsing and running test scenarios,
enabling live demonstrations and debugging of the agent's capabilities.
"""
import os
import json
import streamlit as st


# Scenario metadata with icons and categories
CATEGORY_METADATA = {
    'A_statistical_analysis': {
        'name': 'Statistical Analysis',
        'icon': '📊',
        'description': 'Hypothesis testing, inference, and statistical methods'
    },
    'B_data_quality': {
        'name': 'Data Quality',
        'icon': '🔧',
        'description': 'Handling missing data, outliers, and data type issues'
    },
    'C_multi_dataset': {
        'name': 'Multi-Dataset Operations',
        'icon': '🔗',
        'description': 'Complex joins and cross-dataset aggregations'
    },
    'D_natural_language': {
        'name': 'Natural Language',
        'icon': '💬',
        'description': 'Business language, compound and conceptual questions'
    },
    'E_visualization': {
        'name': 'Visualizations',
        'icon': '📈',
        'description': 'Complex charts and multi-panel dashboards'
    },
    'F_error_handling': {
        'name': 'Error Handling',
        'icon': '⚠️',
        'description': 'Forced errors and alignment failures'
    },
    'G_performance': {
        'name': 'Performance',
        'icon': '⚡',
        'description': 'Large datasets and complex computations'
    },
    'H_domain_specific': {
        'name': 'Domain Specific',
        'icon': '🎯',
        'description': 'Marketing analytics and A/B testing'
    },
    'other': {
        'name': 'Other',
        'icon': '📋',
        'description': 'Miscellaneous scenarios'
    }
}

DIFFICULTY_COLORS = {
    'easy': '🟢',
    'medium': '🟡',
    'hard': '🔴'
}


def load_scenarios(scenarios_folder: str) -> dict:
    """Load all scenario JSON files from the scenarios folder.
    
    Args:
        scenarios_folder: Path to the folder containing scenario JSON files
        
    Returns:
        dict: Dictionary mapping scenario_id to scenario data
    """
    scenarios = {}
    
    if not os.path.exists(scenarios_folder):
        return scenarios
    
    for filename in os.listdir(scenarios_folder):
        if filename.endswith('.json'):
            filepath = os.path.join(scenarios_folder, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    scenario_data = json.load(f)
                    scenario_id = filename.replace('.json', '')
                    scenario_data['id'] = scenario_id
                    scenario_data['filepath'] = filepath
                    scenarios[scenario_id] = scenario_data
            except Exception as e:
                print(f"[WARNING] Failed to load scenario {filename}: {e}")
    
    return scenarios


def get_scenario_category(scenario: dict) -> str:
    """Extract category from scenario metadata."""
    category = scenario.get('metadata', {}).get('category', 'other')
    # Normalize category name
    if category and '_' in category:
        return category
    return 'other'


def get_scenario_difficulty(scenario: dict) -> str:
    """Extract difficulty from scenario metadata."""
    return scenario.get('metadata', {}).get('difficulty', 'medium')


def group_scenarios_by_category(scenarios: dict) -> dict:
    """Group scenarios by their category.
    
    Args:
        scenarios: Dictionary of all scenarios
        
    Returns:
        dict: Dictionary mapping category to list of scenarios
    """
    grouped = {}
    
    for scenario_id, scenario in scenarios.items():
        category = get_scenario_category(scenario)
        if category not in grouped:
            grouped[category] = []
        grouped[category].append(scenario)
    
    # Sort scenarios within each category by name
    for category in grouped:
        grouped[category].sort(key=lambda s: s.get('name', ''))
    
    return grouped


def start_scenario(scenario: dict, load_sample_dataset_func):
    """Start running a scenario by loading datasets and setting up scenario mode.
    
    Args:
        scenario: The scenario data to run
        load_sample_dataset_func: Function to load sample datasets
    """
    # Clear previous datasets and chat history for cleanliness
    st.session_state.datasets = {}
    st.session_state.messages = []
    st.session_state.active_dataset_id = None
    
    # Load required datasets
    datasets_loaded = []
    for ds in scenario.get('datasets', []):
        ds_path = ds.get('path', '')
        ds_id = ds.get('id', '')
        
        # Load the dataset
        if os.path.exists(ds_path):
            load_sample_dataset_func(ds_path, os.path.basename(ds_path))
            datasets_loaded.append(ds_id)
    
    # Set up scenario mode in session state
    st.session_state.scenario_mode = True
    st.session_state.scenario_status = 'running'  # running, paused, stopped
    st.session_state.scenario_data = scenario
    st.session_state.scenario_progress = {
        'current_index': 0,
        'total': len(scenario.get('questions', [])),
        'questions': scenario.get('questions', []),
        'completed': []
    }
    st.session_state.scenario_just_started = True  # Flag to skip first auto-submit
    
    # Switch to chat page and immediately rerun to prevent scenarios list from persisting
    st.session_state.current_page = 'chat'
    st.rerun()


def render_scenario_card(scenario: dict, load_sample_dataset_func):
    """Render a single scenario card with description and run button.
    
    Args:
        scenario: The scenario data to display
        load_sample_dataset_func: Function to load sample datasets
    """
    difficulty = get_scenario_difficulty(scenario)
    difficulty_icon = DIFFICULTY_COLORS.get(difficulty, '🟡')
    
    # Get dataset names
    dataset_names = [ds.get('id', 'unknown') for ds in scenario.get('datasets', [])]
    question_count = len(scenario.get('questions', []))
    tags = scenario.get('metadata', {}).get('tags', [])
    
    with st.container():
        col1, col2 = st.columns([0.85, 0.15])
        
        with col1:
            st.markdown(f"**{scenario.get('name', 'Unnamed Scenario')}** {difficulty_icon} `{difficulty}`")
            st.markdown(f"<small>{scenario.get('description', 'No description')}</small>", unsafe_allow_html=True)
            
            # Show metadata
            meta_parts = []
            if dataset_names:
                meta_parts.append(f"📊 {', '.join(dataset_names)}")
            meta_parts.append(f"❓ {question_count} questions")
            
            st.caption(" • ".join(meta_parts))
            
            # Show tags if present
            if tags:
                tag_str = " ".join([f"`{tag}`" for tag in tags[:5]])  # Limit to 5 tags
                st.markdown(f"<small>🏷️ {tag_str}</small>", unsafe_allow_html=True)
        
        with col2:
            # Check if scenario is currently running
            if (st.session_state.get('scenario_mode') and 
                st.session_state.get('scenario_data', {}).get('id') == scenario.get('id')):
                st.button("▶️ Running", key=f"scenario_{scenario['id']}", 
                         use_container_width=True, disabled=True)
            else:
                if st.button("▶️ Run", key=f"scenario_{scenario['id']}", use_container_width=True):
                    start_scenario(scenario, load_sample_dataset_func)
                    st.rerun()
        
        st.markdown("---")


def render_scenarios_page(load_sample_dataset_func, scenarios_folder: str):
    """Render the Scenarios page with browsable test scenarios.
    
    Args:
        load_sample_dataset_func: Function to load sample datasets
        scenarios_folder: Path to the folder containing scenario JSON files
    """
    st.markdown("## 🎬 Interactive Scenarios")
    st.markdown("Explore pre-built analysis scenarios to see the AI in action. "
                "Each scenario loads required datasets and runs a series of questions.")
    
    # Load all scenarios
    scenarios = load_scenarios(scenarios_folder)
    
    if not scenarios:
        st.warning("No scenarios found. Please check the scenarios folder.")
        st.info(f"Expected location: `{scenarios_folder}`")
        return
    
    # Show scenario count
    total_questions = sum(len(s.get('questions', [])) for s in scenarios.values())
    st.caption(f"📋 {len(scenarios)} scenarios • {total_questions} total questions")
    
    st.divider()
    
    # Group scenarios by category
    grouped = group_scenarios_by_category(scenarios)
    
    # Sort categories by their prefix (A, B, C, etc.)
    sorted_categories = sorted(grouped.keys())
    
    # Render each category
    for category in sorted_categories:
        category_meta = CATEGORY_METADATA.get(category, CATEGORY_METADATA['other'])
        scenario_list = grouped[category]
        
        # Category header
        st.markdown(f"### {category_meta['icon']} {category_meta['name']} ({len(scenario_list)})")
        st.markdown(f"*{category_meta['description']}*")
        
        # Render scenario cards
        for scenario in scenario_list:
            render_scenario_card(scenario, load_sample_dataset_func)
        
        st.markdown("")  # Add spacing between categories


def render_scenario_banner():
    """Render the scenario control banner at the top of the chat page.
    
    This banner shows progress and provides pause/stop controls.
    Should be called from the chat page when scenario_mode is active.
    """
    if not st.session_state.get('scenario_mode'):
        return
    
    # Don't check scenario_just_started here - we want to show the banner even on first render
    
    scenario = st.session_state.get('scenario_data', {})
    progress = st.session_state.get('scenario_progress', {})
    status = st.session_state.get('scenario_status', 'stopped')
    
    current_idx = progress.get('current_index', 0)
    total = progress.get('total', 0)
    scenario_name = scenario.get('name', 'Unknown Scenario')
    
    # Note: Streamlit doesn't support true position:fixed due to iframe architecture
    # Using sticky positioning which works within Streamlit's container
    
    # Status-specific styling
    if status == 'running':
        st.info(f"🎬 **Running Scenario:** {scenario_name} ({current_idx + 1}/{total})")
    elif status == 'paused':
        st.warning(f"⏸️ **Scenario Paused:** {scenario_name} ({current_idx + 1}/{total})")
    elif status == 'completed':
        st.success(f"✅ **Scenario Completed:** {scenario_name} ({total}/{total})")
    
    # Control buttons
    col1, col2, col3 = st.columns([1, 1, 4])
    
    with col1:
        if status == 'running':
            if st.button("⏸️ Pause", key="scenario_pause", use_container_width=True):
                st.session_state.scenario_status = 'paused'
                st.rerun()
        elif status == 'paused':
            if st.button("▶️ Resume", key="scenario_resume", use_container_width=True):
                st.session_state.scenario_status = 'running'
                st.rerun()
    
    with col2:
        if st.button("⏹️ Stop", key="scenario_stop", use_container_width=True):
            # Clear scenario mode
            st.session_state.scenario_mode = False
            st.session_state.scenario_status = 'stopped'
            st.session_state.scenario_data = None
            st.session_state.scenario_progress = None
            st.rerun()
    
    st.divider()


def should_auto_submit_next_question() -> bool:
    """Check if we should automatically submit the next scenario question.
    
    Returns:
        bool: True if we should auto-submit, False otherwise
    """
    if not st.session_state.get('scenario_mode'):
        return False
    
    # Skip first render after starting scenario to allow UI to fully switch
    # The start_scenario function already calls st.rerun() after setting this flag
    if st.session_state.get('scenario_just_started'):
        st.session_state.scenario_just_started = False
        return False
    
    if st.session_state.get('scenario_status') != 'running':
        return False
    
    progress = st.session_state.get('scenario_progress', {})
    current_idx = progress.get('current_index', 0)
    total = progress.get('total', 0)
    
    # Check if there are more questions
    return current_idx < total


def get_next_scenario_question() -> str:
    """Get the next question to submit in the current scenario.
    
    Returns:
        str: The next question, or None if no more questions
    """
    if not st.session_state.get('scenario_mode'):
        return None
    
    progress = st.session_state.get('scenario_progress', {})
    current_idx = progress.get('current_index', 0)
    questions = progress.get('questions', [])
    
    if current_idx < len(questions):
        return questions[current_idx]
    
    return None


def advance_scenario_progress():
    """Advance to the next question in the scenario."""
    if not st.session_state.get('scenario_mode'):
        return
    
    progress = st.session_state.get('scenario_progress', {})
    current_idx = progress.get('current_index', 0)
    total = progress.get('total', 0)
    
    # Advance index
    progress['current_index'] = current_idx + 1
    st.session_state.scenario_progress = progress
    
    # Check if scenario is complete
    if progress['current_index'] >= total:
        st.session_state.scenario_status = 'completed'
        st.session_state.scenario_mode = False
