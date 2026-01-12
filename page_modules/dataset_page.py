"""Dataset page for AI Data Scientist Agent."""
import streamlit as st
from data_analyzer import get_basic_stats


def render_dataset_page():
    """Render the Dataset page with summary, explorer, details, and settings tabs."""
    if not st.session_state.datasets or st.session_state.active_dataset_id not in st.session_state.datasets:
        st.warning("No dataset loaded. Please upload a dataset first.")
        if st.button("Upload Dataset"):
            st.session_state.current_page = 'add_dataset'
            st.rerun()
        return
    
    # Get active dataset
    active_ds = st.session_state.datasets[st.session_state.active_dataset_id]
    df = active_ds['df']
    dataset_name = active_ds['name']
    
    st.markdown(f"## 📊 {dataset_name}")
    
    # Create tabs for dataset views
    tab1, tab2, tab3 = st.tabs(["📄 Summary", "📊 Explorer", "⚙️ Settings"])
    
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
    
    # TAB 3: SETTINGS (Dataset Management)
    with tab3:
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
