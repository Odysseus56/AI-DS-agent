"""Add Dataset page for AI Data Scientist Agent."""
import os
import streamlit as st


# Dataset metadata with descriptions
DATASET_METADATA = {
    'customer_profiles.csv': {
        'name': 'Customer Profiles',
        'icon': '👥',
        'description': 'Bank customer demographics, account info, and product holdings. 5,000 customers with segments (Premium, Growth, New, Standard).',
        'size': '5K rows',
        'category': 'Base'
    },
    'campaign_results.csv': {
        'name': 'Campaign Results',
        'icon': '📈',
        'description': 'Marketing campaign data with treatment/control groups. Includes email engagement, card applications, and revenue metrics over 6 months.',
        'size': '35K rows',
        'category': 'Base'
    },
    'customer_profiles_missing.csv': {
        'name': 'Customer Profiles (Missing Data)',
        'icon': '❓',
        'description': 'Customer profiles with missing values (15-30% missing in age, income, balance). Good for testing data cleaning and imputation.',
        'size': '5K rows',
        'category': 'Test'
    },
    'customer_profiles_outliers.csv': {
        'name': 'Customer Profiles (Outliers)',
        'icon': '⚠️',
        'description': 'Customer profiles with extreme values, negative balances, and invalid ages. Tests outlier detection and data quality checks.',
        'size': '5K rows',
        'category': 'Test'
    },
    'campaign_results_messy.csv': {
        'name': 'Campaign Results (Messy)',
        'icon': '🔧',
        'description': 'Campaign data with mixed date formats, currency strings, Yes/No booleans, and N/A values. Tests data type handling and parsing.',
        'size': '35K rows',
        'category': 'Test'
    },
    'transactions.csv': {
        'name': 'Transactions',
        'icon': '💳',
        'description': 'Transaction history across merchant categories (groceries, restaurants, gas, etc.). 50K transactions for complex joins and aggregations.',
        'size': '50K rows',
        'category': 'Test'
    },
    'customer_profiles_large.csv': {
        'name': 'Customer Profiles (Large)',
        'icon': '📊',
        'description': 'Large-scale customer dataset for performance testing. Same structure as base customer profiles but with 100K customers.',
        'size': '100K rows',
        'category': 'Test'
    }
}


def render_add_dataset_page(handle_file_upload, load_sample_dataset, data_folder: str):
    """Render the Add Dataset page with file upload and sample dataset options.
    
    Args:
        handle_file_upload: Function to handle uploaded CSV files
        load_sample_dataset: Function to load sample datasets
        data_folder: Path to the folder containing sample datasets
    """
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
    
    if os.path.exists(data_folder):
        sample_files = [f for f in os.listdir(data_folder) if f.endswith('.csv')]
        
        if sample_files:
            # Group datasets by category
            base_datasets = []
            test_datasets = []
            
            for filename in sorted(sample_files):
                metadata = DATASET_METADATA.get(filename, {
                    'name': filename.replace('.csv', '').replace('_', ' ').title(),
                    'icon': '📊',
                    'description': 'Sample dataset for analysis.',
                    'size': 'Unknown',
                    'category': 'Other'
                })
                
                if metadata['category'] == 'Base':
                    base_datasets.append((filename, metadata))
                else:
                    test_datasets.append((filename, metadata))
            
            # Render base datasets
            if base_datasets:
                st.markdown("#### 🎯 Base Datasets")
                for filename, metadata in base_datasets:
                    render_dataset_card(filename, metadata, data_folder, load_sample_dataset)
            
            # Render test datasets
            if test_datasets:
                st.markdown("#### 🧪 Test Datasets")
                st.markdown("*Datasets with data quality issues for testing robustness*")
                for filename, metadata in test_datasets:
                    render_dataset_card(filename, metadata, data_folder, load_sample_dataset)
        else:
            st.info("No sample datasets available in the data/ folder.")
    else:
        st.info("Sample datasets folder not found. Upload your own CSV file above.")


def render_dataset_card(filename: str, metadata: dict, data_folder: str, load_sample_dataset):
    """Render a single dataset card with description.
    
    Args:
        filename: Name of the dataset file
        metadata: Dictionary containing dataset metadata
        data_folder: Path to the folder containing sample datasets
        load_sample_dataset: Function to load sample datasets
    """
    # Check if dataset is already loaded
    dataset_id = filename.replace('.csv', '').lower().replace(' ', '_').replace('-', '_')
    is_loaded = dataset_id in st.session_state.datasets
    
    with st.container():
        col1, col2 = st.columns([0.85, 0.15])
        
        with col1:
            st.markdown(f"**{metadata['icon']} {metadata['name']}** `{metadata['size']}`")
            st.markdown(f"<small>{metadata['description']}</small>", unsafe_allow_html=True)
        
        with col2:
            # Show different button state based on whether dataset is loaded
            if is_loaded:
                st.button("✓ Loaded", key=f"sample_{filename}", use_container_width=True, disabled=True)
            else:
                # Create a unique key for the loading state
                loading_key = f"loading_{filename}"
                if loading_key not in st.session_state:
                    st.session_state[loading_key] = False
                
                # Show loading button or normal button
                if st.session_state[loading_key]:
                    st.button("⏳ Loading...", key=f"sample_{filename}_loading", use_container_width=True, disabled=True)
                else:
                    if st.button("Load", key=f"sample_{filename}", use_container_width=True):
                        # Set loading state
                        st.session_state[loading_key] = True
                        st.rerun()
                
                # If loading state is active, actually load the dataset
                if st.session_state[loading_key] and not is_loaded:
                    file_path = os.path.join(data_folder, filename)
                    if load_sample_dataset(file_path, filename):
                        # Clear loading state and switch to chat
                        st.session_state[loading_key] = False
                        st.session_state.current_page = 'chat'
                        st.rerun()
                    else:
                        # Clear loading state on failure
                        st.session_state[loading_key] = False
                        st.rerun()
        
        st.markdown("---")
