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

# ==== PAGE HEADER ====
st.title("🤖 AI Data Scientist Assistant")
st.markdown("Upload a CSV file and start chatting with your data")

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

# ==== FILE UPLOAD SECTION ====
uploaded_file = st.file_uploader("📤 Upload your dataset (CSV)", type="csv", key="file_uploader")

# Handle file upload and auto-generate summary
if uploaded_file is not None:
    # Check if this is a new file
    if st.session_state.uploaded_file_name != uploaded_file.name:
        # Validate file size (100MB limit)
        if uploaded_file.size > 100_000_000:
            st.error("❌ File too large. Please upload a CSV file smaller than 100MB.")
            st.stop()
        
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
            st.stop()
        
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
        st.rerun()

# ==== MAIN APPLICATION LOGIC ====
if st.session_state.df is not None:
    df = st.session_state.df
    
    # ==== TAB LAYOUT ====
    tab1, tab2, tab3, tab4 = st.tabs(["💬 Chat", "📊 Data Explorer", "📈 Details", "📋 Logs"])
    
    # ==== TAB 1: CHAT INTERFACE ====
    with tab1:
        st.markdown("### Chat with your data")
        
        # Display chat history
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                if message.get("type") == "visualization" and message.get("figures"):
                    # Display visualization message
                    st.markdown(message["content"])
                    for fig in message["figures"]:
                        st.pyplot(fig)
                elif message.get("type") == "error":
                    st.error(message["content"])
                else:
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
                            st.markdown(explanation)
                            for fig in figures:
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
                            error_msg = f"Error creating visualization: {error}"
                            st.error(error_msg)
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": error_msg,
                                "type": "error"
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
                            # Code execution failed
                            error_msg = f"Error executing analysis: {error}\n\nTrying alternative approach..."
                            st.warning(error_msg)
                            
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
                        # Code generation failed
                        st.error("Could not generate analysis code. Providing conceptual answer...")
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
    
    # ==== TAB 2: DATA EXPLORER ====
    with tab2:
        st.markdown("### Explore Your Dataset")
        st.dataframe(df, use_container_width=True, height=600)
    
    # ==== TAB 3: DETAILS ====
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
    
    # ==== TAB 4: LOGS ====
    with tab4:
        st.markdown("### Session Logs")
        
        # Get session-specific log content
        log_content = get_log_content(session_timestamp=st.session_state.session_timestamp)
        
        # Display log preview
        st.markdown("**Log Preview:**")
        with st.container():
            preview_length = 3000
            if len(log_content) > preview_length:
                st.markdown(log_content[:preview_length] + "\n\n*...truncated for preview. Download full log below.*")
            else:
                st.markdown(log_content)
        
        st.divider()
        
        # Download buttons
        st.subheader("📥 Download Logs")
        col_md, col_pdf = st.columns(2)
        
        with col_md:
            st.download_button(
                label="📥 Download as Markdown",
                data=log_content,
                file_name=f"log_{st.session_state.session_timestamp}.md",
                mime="text/markdown",
                use_container_width=True
            )
        
        with col_pdf:
            try:
                pdf_data = convert_log_to_pdf(session_timestamp=st.session_state.session_timestamp)
                st.download_button(
                    label="📄 Download as PDF",
                    data=pdf_data,
                    file_name=f"log_{st.session_state.session_timestamp}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"PDF conversion unavailable: {str(e)}")

# ==== NO FILE UPLOADED STATE ====
else:
    st.info("👆 Upload a CSV file to start chatting with your data")
    
    # Show placeholder tabs when no file is uploaded
    tab1, tab2, tab3, tab4 = st.tabs(["💬 Chat", "📊 Data Explorer", "📈 Details", "📋 Logs"])
    
    with tab1:
        st.info("Upload a dataset to start chatting")
    with tab2:
        st.info("Upload a dataset to explore the data")
    with tab3:
        st.info("Upload a dataset to view details")
    with tab4:
        st.info("Upload a dataset to view logs")