# ==== IMPORTS ====
import streamlit as st  # Web UI framework
import pandas as pd  # Data manipulation library
import uuid  # For generating unique session IDs
from data_analyzer import generate_data_summary, get_basic_stats  # Our data analysis module
from llm_client import get_data_summary_from_llm, ask_question_about_data, generate_visualization_code  # Our LLM integration
from code_executor import execute_visualization_code, InteractionLogger, get_log_content, convert_log_to_pdf  # Code execution

# ==== PAGE CONFIGURATION ====
# Must be first Streamlit command - sets browser tab title, icon, and layout
st.set_page_config(page_title="AI Data Scientist", page_icon="📊", layout="wide")

# ==== PAGE HEADER ====
st.title("🤖 AI Data Scientist Assistant")
st.markdown("Upload a CSV file and let AI help you understand your data")

# ==== FILE UPLOAD WIDGET ====
# Returns None if no file uploaded, otherwise a file-like object
uploaded_file = st.file_uploader("Upload your dataset", type="csv")

# ==== MAIN APPLICATION LOGIC ====
# Only runs if a file has been uploaded
if uploaded_file:
    # Load CSV into pandas DataFrame
    df = pd.read_csv(uploaded_file)
    
    # ==== SESSION STATE MANAGEMENT ====
    # Streamlit reruns the entire script on every interaction
    # session_state persists data across reruns (like component state in React)
    # We store the summaries here so they don't get regenerated on every button click
    
    # Generate unique session ID (only once per user session)
    if 'session_id' not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())[:8]  # Short 8-character ID
    
    if 'data_summary' not in st.session_state:
        st.session_state.data_summary = None  # Technical summary (goes to LLM)
    if 'llm_summary' not in st.session_state:
        st.session_state.llm_summary = None  # Business-friendly summary (from LLM)
    if 'logger' not in st.session_state:
        # Pass session ID to logger for session-specific log files
        st.session_state.logger = InteractionLogger(session_id=st.session_state.session_id)
    
    # Show success message with filename
    st.success(f"✅ File uploaded: {uploaded_file.name}")
    
    # ==== TWO-COLUMN LAYOUT ====
    # Split screen: left column (1/3 width) for stats, right column (2/3 width) for AI analysis
    col1, col2 = st.columns([1, 2])
    
    # ==== LEFT COLUMN: Dataset Overview ====
    with col1:
        st.subheader("📋 Dataset Overview")
        
        # Get basic statistics from our data_analyzer module
        stats = get_basic_stats(df)
        
        # Display metrics using Streamlit's metric component (shows number with label)
        st.metric("Rows", f"{stats['rows']:,}")  # :, adds thousand separators
        st.metric("Columns", f"{stats['columns']}")
        st.metric("Missing Cells", f"{stats['missing_cells']:,}")
        st.metric("Duplicate Rows", f"{stats['duplicate_rows']:,}")
        st.metric("Memory Usage", f"{stats['memory_usage_mb']:.2f} MB")  # :.2f = 2 decimal places
        
        # Visual separator line
        st.divider()
        
        # ==== PRIMARY ACTION BUTTON ====
        # type="primary" makes it blue/prominent, use_container_width=True makes it full-width
        if st.button("🔍 Generate AI Summary", type="primary", use_container_width=True):
            # Spinner shows loading animation while code executes
            with st.spinner("Analyzing data..."):
                # Step 1: Generate technical summary of the data
                st.session_state.data_summary = generate_data_summary(df)
            
            with st.spinner("Getting AI insights..."):
                # Step 2: Send technical summary to LLM, get business-friendly version
                st.session_state.llm_summary = get_data_summary_from_llm(
                    st.session_state.data_summary
                )
                
                # Log the summary generation
                st.session_state.logger.log_summary_generation(
                    "Executive Summary",
                    st.session_state.llm_summary
                )
    
    # ==== RIGHT COLUMN: AI Analysis ====
    with col2:
        st.subheader("🤖 AI Analysis")
        
        # Only show AI analysis section if we have a summary
        # This creates a progressive disclosure UX (user must click button first)
        if st.session_state.llm_summary:
            # Display the business-friendly summary from the LLM
            st.markdown("### Executive Summary")
            st.info(st.session_state.llm_summary)  # info() creates a blue info box
            
            st.divider()
            
            # ==== INTERACTIVE Q&A SECTION ====
            st.markdown("### Ask Questions About Your Data")
            user_question = st.text_input(
                "What would you like to know?",
                placeholder="e.g., What are the main patterns in this data?"
            )
            
            # When user clicks "Ask", send their question to the LLM
            if st.button("Ask", use_container_width=True):
                if user_question:  # Validate that user entered something
                    
                    # ==== DETECT VISUALIZATION REQUESTS ====
                    # Check if user is asking for plots/charts/graphs
                    viz_keywords = ['plot', 'chart', 'graph', 'visuali', 'show', 'display', 'draw', 'histogram', 'scatter', 'correlation', 'heatmap', 'distribution']
                    is_visualization_request = any(keyword in user_question.lower() for keyword in viz_keywords)
                    
                    if is_visualization_request:
                        # ==== VISUALIZATION WORKFLOW ====
                        with st.spinner("Generating visualization code..."):
                            # Ask LLM to generate code
                            code, explanation = generate_visualization_code(
                                user_question,
                                st.session_state.data_summary
                            )
                        
                        if code:  # Code was successfully generated
                            with st.spinner("Executing code and creating visualizations..."):
                                # Execute the code
                                success, figures, error = execute_visualization_code(
                                    code,
                                    df,
                                    st.session_state.logger
                                )
                            
                            # Log the visualization interaction with embedded images
                            st.session_state.logger.log_visualization(
                                user_question,
                                code,
                                explanation,
                                success,
                                figures if success else None,
                                error if not success else ""
                            )
                            
                            if success:
                                # Show explanation first
                                st.markdown("#### Visualization:")
                                st.info(explanation)
                                
                                # Display all generated figures
                                for fig in figures:
                                    st.pyplot(fig)
                            else:
                                # Show error message
                                st.error(f"Error executing visualization code: {error}")
                                st.info("Try rephrasing your request or ask a different question.")
                        else:
                            # LLM failed to generate code
                            st.error("Could not generate visualization code. Try a different request.")
                    
                    else:
                        # ==== REGULAR TEXT Q&A WORKFLOW ====
                        with st.spinner("Thinking..."):
                            # Call LLM with user's question + data context
                            answer = ask_question_about_data(
                                user_question, 
                                st.session_state.data_summary  # Same context as initial summary
                            )
                        
                        # Log the Q&A interaction
                        st.session_state.logger.log_text_qa(user_question, answer)
                        
                        st.markdown("#### Answer:")
                        st.write(answer)
                else:
                    st.warning("Please enter a question first")
        else:
            # Placeholder message when no summary exists yet
            st.info("👈 Click 'Generate AI Summary' to get started")
    
    # ==== EXPANDABLE SECTIONS (COLLAPSED BY DEFAULT) ====
    # Expander creates a collapsible section to reduce visual clutter
    
    # Show raw data table (useful for spot-checking)
    with st.expander("📊 View Raw Data"):
        st.dataframe(df, use_container_width=True)  # Interactive table with sorting/filtering
    
    # Show technical summary (for advanced users or debugging)
    with st.expander("📈 View Technical Summary"):
        if st.session_state.data_summary:
            st.text(st.session_state.data_summary)  # Plain text display
        else:
            st.info("Generate AI summary first to see technical details")
    
    # ==== INTERACTION LOG (DOWNLOADABLE) ====
    # Show comprehensive interaction log with download button
    with st.expander("📋 View Interaction Log"):
        # Get session-specific log content
        log_content = get_log_content(session_id=st.session_state.session_id)
        
        # Display as markdown preview
        st.markdown("**Log Preview:**")
        with st.container():
            st.markdown(log_content[:2000] + "\n\n*...truncated for preview*" if len(log_content) > 2000 else log_content)
        
        # Download buttons for different formats
        col_md, col_pdf = st.columns(2)
        
        with col_md:
            st.download_button(
                label="📥 Download as Markdown",
                data=log_content,
                file_name=f"interaction_log_{st.session_state.session_id}.md",
                mime="text/markdown",
                use_container_width=True
            )
        
        with col_pdf:
            try:
                pdf_data = convert_log_to_pdf(session_id=st.session_state.session_id)
                st.download_button(
                    label="📄 Download as PDF",
                    data=pdf_data,
                    file_name=f"interaction_log_{st.session_state.session_id}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"PDF conversion unavailable: {str(e)}")

# ==== NO FILE UPLOADED STATE ====
# Show this message when user first loads the page
else:
    st.info("👆 Upload a CSV file to begin analysis")