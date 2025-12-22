# ==== IMPORTS ====
import streamlit as st  # Web UI framework
import pandas as pd  # Data manipulation library
import uuid  # For generating unique session IDs
from datetime import datetime  # For timestamping sessions
from data_analyzer import generate_data_summary, get_basic_stats  # Our data analysis module
from llm_client import get_data_summary_from_llm, ask_question_about_data, generate_visualization_code, classify_question_type, generate_analysis_code, format_code_result_as_answer  # Our LLM integration
from code_executor import execute_visualization_code, execute_analysis_code, InteractionLogger, get_log_content, convert_log_to_pdf  # Code execution

# ==== PAGE CONFIGURATION ====
# Must be first Streamlit command - sets browser tab title, icon, and layout
st.set_page_config(page_title="AI Data Scientist", page_icon="📊", layout="wide")

# ==== SESSION STATE INITIALIZATION ====
# Initialize all session state variables
if 'session_timestamp' not in st.session_state:
    st.session_state.session_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")

if 'data_summary' not in st.session_state:
    st.session_state.data_summary = None

if 'messages' not in st.session_state:
    st.session_state.messages = []  # Chat history

if 'df' not in st.session_state:
    st.session_state.df = None  # Store dataframe in session state

if 'uploaded_file_name' not in st.session_state:
    st.session_state.uploaded_file_name = None

if 'logger' not in st.session_state:
    st.session_state.logger = InteractionLogger(session_timestamp=st.session_state.session_timestamp)

if 'current_page' not in st.session_state:
    st.session_state.current_page = 'chat'  # Default page

# ==== PAGE HEADER ====
st.title("🤖 AI Data Scientist Assistant")
st.markdown("Your AI-Powered Data Science Partner")

# ==== SIDEBAR NAVIGATION ====
with st.sidebar:
    st.title("📊 Navigation")
    
    # Main navigation buttons
    if st.button("💬 Chat", use_container_width=True, type="primary" if st.session_state.current_page == 'chat' else "secondary"):
        st.session_state.current_page = 'chat'
        st.rerun()
    
    if st.button("📋 Log", use_container_width=True, type="primary" if st.session_state.current_page == 'log' else "secondary"):
        st.session_state.current_page = 'log'
        st.rerun()
    
    st.divider()
    
    # Dataset section
    if st.session_state.df is not None:
        dataset_name = st.session_state.uploaded_file_name or "Dataset"
        if st.button(f"📊 {dataset_name}", use_container_width=True, type="primary" if st.session_state.current_page == 'dataset' else "secondary"):
            st.session_state.current_page = 'dataset'
            st.rerun()
    
    if st.button("➕ Add Dataset", use_container_width=True, type="primary" if st.session_state.current_page == 'add_dataset' else "secondary"):
        st.session_state.current_page = 'add_dataset'
        st.rerun()

# ==== HELPER FUNCTION: FILE UPLOAD HANDLER ====
def handle_file_upload(uploaded_file):
    """Process uploaded CSV file and generate summary."""
    # Validate file size (100MB limit)
    if uploaded_file.size > 100_000_000:
        st.error("❌ File too large. Please upload a CSV file smaller than 100MB.")
        return False
    
    # New file uploaded - reset state and load data
    st.session_state.uploaded_file_name = uploaded_file.name
    
    try:
        # Load CSV with row limit to prevent memory issues
        st.session_state.df = pd.read_csv(uploaded_file, nrows=1_000_000)
        
        # Warn if file was truncated
        if len(st.session_state.df) == 1_000_000:
            st.warning("⚠️ Dataset truncated to 1 million rows for performance.")
    except Exception as e:
        st.error(f"❌ Error reading CSV file: {str(e)}")
        st.info("Please ensure the file is a valid CSV format.")
        return False
    
    st.session_state.messages = []  # Clear chat history for new file
    
    # Auto-generate summary
    with st.spinner("📊 Analyzing your dataset..."):
        st.session_state.data_summary = generate_data_summary(st.session_state.df)
    
    with st.spinner("🤖 Generating AI insights..."):
        llm_summary = get_data_summary_from_llm(st.session_state.data_summary)
        
        # Add summary as first message in chat
        st.session_state.messages.append({
            "role": "assistant",
            "content": llm_summary,
            "type": "summary"
        })
        
        # Log the summary
        st.session_state.logger.log_summary_generation("Executive Summary", llm_summary)
    
    st.success(f"✅ File uploaded: {uploaded_file.name}")
    return True

# ==== MAIN CONTENT ROUTING ====

# ==== PAGE: ADD DATASET ====
if st.session_state.current_page == 'add_dataset':
    st.markdown("## 📤 Upload Dataset")
    st.markdown("Upload a CSV file to get started with AI-powered data analysis.")
    
    uploaded_file = st.file_uploader("Choose a CSV file", type="csv", key="file_uploader")
    
    if uploaded_file is not None:
        # Check if this is a new file
        if st.session_state.uploaded_file_name != uploaded_file.name:
            if handle_file_upload(uploaded_file):
                # Switch to dataset view after successful upload
                st.session_state.current_page = 'dataset'
                st.rerun()

# ==== PAGE: CHAT ====
elif st.session_state.current_page == 'chat':
    if st.session_state.df is None:
        st.info("👆 Please upload a dataset to start chatting")
        if st.button("Upload Dataset"):
            st.session_state.current_page = 'add_dataset'
            st.rerun()
    else:
        df = st.session_state.df
        st.markdown("## 💬 Chat with your data")
        
        # Display chat history
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                if message.get("type") == "visualization" and message.get("figures"):
                    # Show code if available in metadata
                    if message.get("metadata") and message["metadata"].get("code"):
                        with st.expander("🔍 View Generated Code"):
                            st.code(message["metadata"]["code"], language="python")
                    
                    # Display visualization message
                    st.markdown(message["content"])
                    for fig in message["figures"]:
                        # Check if it's a Plotly figure or matplotlib figure
                        if hasattr(fig, 'write_image'):
                            # Plotly figure
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            # Matplotlib figure
                            st.pyplot(fig)
                
                elif message.get("type") == "error":
                    # Show attempted code if this was a failed visualization
                    if message.get("metadata") and message["metadata"].get("type") == "visualization_failed":
                        with st.expander("🔍 View Attempted Code"):
                            st.code(message["metadata"]["code"], language="python")
                    
                    st.error(message["content"])
                else:
                    # Show code and raw result for analysis messages
                    if message.get("metadata") and message["metadata"].get("type") == "analysis":
                        with st.expander("🔍 View Code & Raw Output"):
                            st.markdown("**Generated Code:**")
                            st.code(message["metadata"]["code"], language="python")
                            st.markdown("**Raw Result:**")
                            st.code(message["metadata"]["raw_result"])
                    st.markdown(message["content"])
                    
        # Chat input
        user_question = st.chat_input("Ask a question about your data...")
        
        if user_question:
            # Limit chat history to prevent memory issues (keep last 20 messages)
            if len(st.session_state.messages) > 20:
                st.session_state.messages = st.session_state.messages[-20:]
            
            # Add user message to chat
            st.session_state.messages.append({"role": "user", "content": user_question})
            
            # Display user message
            with st.chat_message("user"):
                st.markdown(user_question)
            
            # Classify question type using LLM
            with st.spinner("Analyzing question..."):
                question_type = classify_question_type(
                    user_question,
                    st.session_state.data_summary,
                    st.session_state.messages
                )
            
            if question_type == 'VISUALIZATION':
                # Generate and execute visualization
                with st.chat_message("assistant"):
                    with st.spinner("Generating visualization..."):
                        code, explanation = generate_visualization_code(
                            user_question,
                            st.session_state.data_summary,
                            st.session_state.messages
                        )
                    
                    if code:
                        with st.spinner("Creating visualization..."):
                            success, figures, error = execute_visualization_code(
                                code,
                                df,
                                st.session_state.logger
                            )
                        
                        # Log the visualization workflow with classification
                        st.session_state.logger.log_visualization_workflow(
                            user_question,
                            question_type,
                            code,
                            explanation,
                            success,
                            figures if success else None,
                            error if not success else ""
                        )
                        
                        if success:
                            with st.expander("🔍 View Generated Code"):
                                st.code(code, language="python")
                            st.markdown(explanation)
                            for fig in figures:
                                # Check if it's a Plotly figure or matplotlib figure
                                if hasattr(fig, 'write_image'):
                                    # Plotly figure
                                    st.plotly_chart(fig, use_container_width=True)
                                else:
                                    # Matplotlib figure
                                    st.pyplot(fig)
                            
                            # Add to chat history with metadata
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": explanation,
                                "type": "visualization",
                                "figures": figures,
                                "metadata": {
                                    "type": "visualization",
                                    "code": code
                                }
                            })
                        else:
                            # Show the attempted code even when it fails
                            with st.expander("🔍 View Attempted Code"):
                                st.code(code, language="python")
                            
                            error_msg = f"Error creating visualization: {error}"
                            st.error(error_msg)
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": error_msg,
                                "type": "error",
                                "metadata": {
                                    "type": "visualization_failed",
                                    "code": code,
                                    "error": error
                                }
                            })
                    else:
                        error_msg = "Could not generate visualization code. Try rephrasing your request."
                        st.error(error_msg)
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": error_msg,
                            "type": "error"
                        })
            elif question_type == 'ANALYSIS':
                # Analytical question - generate and execute code
                with st.chat_message("assistant"):
                    # Code-first approach: generate and execute code
                    with st.spinner("Generating analysis code..."):
                        code = generate_analysis_code(
                            user_question,
                            st.session_state.data_summary,
                            st.session_state.messages
                        )
                    
                    if code and not code.startswith("# Error"):
                        with st.spinner("Executing analysis..."):
                            success, result_str, error = execute_analysis_code(code, df)
                        
                        if success:
                            # Format the result as natural language answer
                            with st.spinner("Formatting answer..."):
                                answer = format_code_result_as_answer(
                                    user_question,
                                    code,
                                    result_str,
                                    st.session_state.data_summary,
                                    st.session_state.messages
                                )
                            
                            with st.expander("🔍 View Code & Raw Output"):
                                st.markdown("**Generated Code:**")
                                st.code(code, language="python")
                                st.markdown("**Raw Result:**")
                                st.code(result_str)
                            st.markdown(answer)
                            
                            # Log the analysis workflow with all steps
                            st.session_state.logger.log_analysis_workflow(
                                user_question,
                                question_type,
                                code,
                                result_str,
                                answer,
                                success=True
                            )
                            
                            # Add to chat history with metadata
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": answer,
                                "metadata": {
                                    "type": "analysis",
                                    "code": code,
                                    "raw_result": result_str
                                }
                            })
                        else:
                            # Code execution failed - log the error
                            error_msg = f"Error executing analysis: {error}\n\nTrying alternative approach..."
                            st.warning(error_msg)
                            
                            # Log the failed attempt
                            st.session_state.logger.log_analysis_workflow(
                                user_question,
                                question_type,
                                code,
                                "",
                                error_msg,
                                success=False,
                                error=error
                            )
                            
                            # Fallback to text-only answer
                            answer = ask_question_about_data(
                                user_question,
                                st.session_state.data_summary
                            )
                            st.markdown(answer)
                            
                            st.session_state.logger.log_text_qa(user_question, answer)
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": answer
                            })
                    else:
                        # Code generation failed - log it
                        error_msg = "Could not generate analysis code. Providing conceptual answer..."
                        st.error(error_msg)
                        
                        # Log the failure
                        st.session_state.logger.log_analysis_workflow(
                            user_question,
                            question_type,
                            code if code else "N/A",
                            "",
                            error_msg,
                            success=False,
                            error="Code generation failed"
                        )
                        
                        answer = ask_question_about_data(
                            user_question,
                            st.session_state.data_summary
                        )
                        st.markdown(answer)
                        
                        st.session_state.logger.log_text_qa(user_question, answer)
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": answer
                        })
            else:
                # CONCEPTUAL question - no code needed
                with st.chat_message("assistant"):
                    with st.spinner("Thinking..."):
                        answer = ask_question_about_data(
                            user_question,
                            st.session_state.data_summary
                        )
                    
                    st.markdown(answer)
                    
                    # Log the Q&A
                    st.session_state.logger.log_text_qa(user_question, answer)
                    
                    # Add to chat history
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer
                    })
            
            st.rerun()

# ==== PAGE: LOG ====
elif st.session_state.current_page == 'log':
    st.markdown("## 📋 Session Logs")
    
    # Download buttons at top
    col_md, col_pdf = st.columns(2)
    with col_md:
        st.download_button(
            label="📥 Download Markdown",
            data=get_log_content(session_timestamp=st.session_state.session_timestamp),
            file_name=f"log_{st.session_state.session_timestamp}.md",
            mime="text/markdown",
            width="stretch"
        )
    with col_pdf:
        try:
            pdf_data = convert_log_to_pdf(session_timestamp=st.session_state.session_timestamp)
            st.download_button(
                label="📄 Download PDF",
                data=pdf_data,
                file_name=f"log_{st.session_state.session_timestamp}.pdf",
                mime="application/pdf",
                width="stretch"
            )
        except Exception as e:
            st.error(f"PDF conversion unavailable: {str(e)}")
    
    st.divider()
    
    # Parse and display log with collapsible sections
    import re
    
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
            
            # Display interaction with expander
            expander_title = f"**#{interaction_num}** - {user_question[:80]}{'...' if len(user_question) > 80 else ''}"
            with st.expander(expander_title, expanded=False):
                # Parse and structure the content
                content = '\n'.join(lines)
                
                # Extract sections
                user_section = ''
                code_section = ''
                result_section = ''
                answer_section = ''
                
                # Find user input
                user_match = re.search(r'\*\*User (Question|Request):\*\*\s*\n(.+?)(?=\n\n|\*\*)', content, re.DOTALL)
                if user_match:
                    user_section = user_match.group(2).strip()
                elif is_upload:
                    user_section = "New dataset uploaded and analyzed"
                
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
                
                # Display structured sections
                if user_section:
                    st.markdown("### 📝 User Input")
                    st.markdown(user_section)
                    st.divider()
                
                if code_section or result_section:
                    st.markdown("### ⚙️ Internal Processing")
                    if code_section:
                        with st.expander("View Generated Code", expanded=False):
                            st.code(code_section, language="python")
                    if result_section:
                        with st.expander("View Execution Result", expanded=False):
                            st.code(result_section)
                    st.divider()
                
                if answer_section:
                    st.markdown("### ✅ Final Answer")
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
    if st.session_state.df is None:
        st.warning("No dataset loaded. Please upload a dataset first.")
        if st.button("Upload Dataset"):
            st.session_state.current_page = 'add_dataset'
            st.rerun()
    else:
        df = st.session_state.df
        dataset_name = st.session_state.uploaded_file_name or "Dataset"
        
        st.markdown(f"## 📊 {dataset_name}")
        
        # Create tabs for dataset views
        tab1, tab2, tab3, tab4 = st.tabs(["📄 Summary", "📊 Explorer", "📈 Details", "⚙️ Settings"])
        
        # TAB 1: SUMMARY (Executive Summary)
        with tab1:
            st.markdown("### Executive Summary")
            
            # Find and display the executive summary from messages
            summary_message = None
            for msg in st.session_state.messages:
                if msg.get("type") == "summary":
                    summary_message = msg
                    break
            
            if summary_message:
                st.markdown(summary_message["content"])
            else:
                st.info("No executive summary available. Upload a new dataset to generate one.")
        
        # TAB 2: EXPLORER (Data Table)
        with tab2:
            st.markdown("### Data Explorer")
            st.dataframe(df, use_container_width=True, height=600)
        
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
            if st.session_state.data_summary:
                st.text(st.session_state.data_summary)
            else:
                st.info("Technical summary not available")
        
        # TAB 4: SETTINGS (Dataset Management)
        with tab4:
            st.markdown("### Dataset Settings")
            
            # Dataset metadata
            st.subheader("📋 Metadata")
            st.write(f"**Name:** {dataset_name}")
            st.write(f"**Rows:** {len(df):,}")
            st.write(f"**Columns:** {len(df.columns)}")
            
            st.divider()
            
            # Delete dataset
            st.subheader("⚠️ Danger Zone")
            st.warning("Deleting this dataset will remove all associated data and chat history.")
            
            if st.button("🗑️ Delete Dataset", type="secondary"):
                # Clear dataset
                st.session_state.df = None
                st.session_state.uploaded_file_name = None
                st.session_state.data_summary = None
                st.session_state.messages = []
                st.session_state.current_page = 'add_dataset'
                st.rerun()

# ==== NO FILE UPLOADED STATE ====
else:
    st.info("👆 Upload a CSV file to start chatting with your data")