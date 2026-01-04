"""Add Dataset page for AI Data Scientist Agent."""
import os
import streamlit as st


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
