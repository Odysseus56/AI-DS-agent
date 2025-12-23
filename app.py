# ==== IMPORTS ====
import streamlit as st  # Web UI framework
import pandas as pd  # Data manipulation library
import re  # Regular expressions for log parsing
from datetime import datetime  # For timestamping sessions
from data_analyzer import generate_data_summary, get_basic_stats  # Our data analysis module
from llm_client import get_data_summary_from_llm, create_execution_plan, generate_unified_code, evaluate_code_results, generate_final_explanation  # Our LLM integration
from code_executor import execute_unified_code, InteractionLogger, get_log_content, convert_log_to_pdf  # Code execution

# ==== PAGE CONFIGURATION ====
# Must be first Streamlit command - sets browser tab title, icon, and layout
st.set_page_config(page_title="AI Data Scientist", page_icon="📊", layout="wide")

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
    st.session_state.logger = InteractionLogger(session_timestamp=st.session_state.session_timestamp)

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

# ==== HELPER FUNCTION: FILE UPLOAD HANDLER ====
def handle_file_upload(uploaded_file):
    """Process uploaded CSV file and add to datasets."""
    # Validate file size (100MB limit)
    if uploaded_file.size > 100_000_000:
        st.error("❌ File too large. Please upload a CSV file smaller than 100MB.")
        return False
    
    # Generate dataset ID from filename
    dataset_id = uploaded_file.name.replace('.csv', '').lower().replace(' ', '_').replace('-', '_')
    
    # Check if dataset already exists
    if dataset_id in st.session_state.datasets:
        st.warning(f"⚠️ Dataset '{uploaded_file.name}' is already loaded.")
        st.session_state.active_dataset_id = dataset_id
        return True
    
    try:
        # Load CSV with row limit to prevent memory issues
        df = pd.read_csv(uploaded_file, nrows=1_000_000)
        
        # Warn if file was truncated
        if len(df) == 1_000_000:
            st.warning("⚠️ Dataset truncated to 1 million rows for performance.")
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
    
    st.success(f"✅ File uploaded: {uploaded_file.name}")
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
            with st.chat_message(message["role"]):
                # Show debug dropdowns if metadata exists
                metadata = message.get("metadata", {})
                
                # Step 1: Execution Planning
                if metadata.get("plan"):
                    plan = metadata["plan"]
                    with st.expander("🧠 Step 1: Execution Planning", expanded=False):
                        st.write(f"**Reasoning:** {plan.get('reasoning', 'N/A')}")
                        st.write(f"**Needs Code:** {plan.get('needs_code', False)}")
                        st.write(f"**Needs Evaluation:** {plan.get('needs_evaluation', False)}")
                        st.write(f"**Needs Explanation:** {plan.get('needs_explanation', False)}")
                
                # Step 2: Code Generation
                if metadata.get("code"):
                    with st.expander("💻 Step 2: Code Generation", expanded=False):
                        st.code(metadata["code"], language="python")
                
                # Code Execution Output
                if metadata.get("result_str"):
                    with st.expander("⚙️ Code Execution Output", expanded=False):
                        st.code(metadata.get('result_str', 'N/A'))
                
                # Step 3: Critical Evaluation
                if metadata.get("evaluation"):
                    with st.expander("🔍 Step 3: Critical Evaluation", expanded=False):
                        st.markdown(metadata["evaluation"])
                
                # Step 4: Final Report
                if metadata.get("explanation"):
                    with st.expander("✍️ Step 4: Final Report", expanded=True):
                        st.markdown(metadata["explanation"])
                
                # Display main content
                if message.get("type") == "visualization" and message.get("figures"):
                    # Display figures only (explanation is in Step 4 dropdown)
                    for fig in message["figures"]:
                        # Check if it's a Plotly figure or matplotlib figure
                        if hasattr(fig, 'write_image'):
                            # Plotly figure
                            st.plotly_chart(fig, width="stretch")
                        else:
                            # Matplotlib figure
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
            
            # Build combined data summary for all datasets
            combined_summary = "Available datasets:\n\n"
            for ds_id, ds_info in st.session_state.datasets.items():
                combined_summary += f"Dataset '{ds_id}' ({ds_info['name']}):\n{ds_info['data_summary']}\n\n"
            
            # NEW 4-STEP WORKFLOW
            with st.chat_message("assistant"):
                # STEP 1: Create execution plan
                with st.spinner("🤔 Planning approach..."):
                    plan = create_execution_plan(user_question, combined_summary, st.session_state.messages)
                
                # Show plan in debug expander
                with st.expander("🧠 Step 1: Execution Planning", expanded=False):
                    st.write(f"**Reasoning:** {plan['reasoning']}")
                    st.write(f"**Needs Code:** {plan['needs_code']}")
                    st.write(f"**Needs Evaluation:** {plan['needs_evaluation']}")
                    st.write(f"**Needs Explanation:** {plan['needs_explanation']}")
                
                code = None
                output = None
                evaluation = None
                explanation = None
            
                # STEP 2: Generate code (if needed)
                if plan['needs_code']:
                    with st.spinner("💻 Generating code..."):
                        code = generate_unified_code(user_question, combined_summary, st.session_state.messages)
                    
                    # Debug: Show generated code
                    with st.expander("💻 Step 2: Code Generation", expanded=False):
                        if code:
                            st.code(code, language="python")
                        else:
                            st.warning("No code generated")
                
                # STEP 3: Execute code (if needed)
                if code:
                    with st.spinner("⚙️ Executing code..."):
                        success, output, error = execute_unified_code(code, st.session_state.datasets)
                    
                    if success:
                        # Debug: Show execution output
                        with st.expander("⚙️ Code Execution Output", expanded=False):
                            st.code(output.get('result_str', 'N/A'))
                        
                        # STEP 3: Evaluate results (if needed)
                        if plan['needs_evaluation']:
                            with st.spinner("🔍 Evaluating results..."):
                                evaluation = evaluate_code_results(
                                    user_question,
                                    code,
                                    output['result_str'],
                                    combined_summary,
                                    st.session_state.messages
                                )
                            
                            # Debug: Show evaluation
                            with st.expander("🔍 Step 3: Critical Evaluation", expanded=False):
                                if evaluation:
                                    st.markdown(evaluation)
                                else:
                                    st.warning("No evaluation generated")
                    else:
                        # Code execution failed
                        error_msg = f"Code execution failed: {error}"
                        st.error(error_msg)
                        st.session_state.logger.log_analysis_workflow(
                            user_question, "CODE_FAILED", code, "", error_msg, success=False, error=error,
                            execution_plan=plan
                        )
                        st.session_state.messages.append({
                            "role": "assistant", "content": error_msg, "type": "error",
                            "metadata": {"code": code, "error": error}
                        })
                        st.rerun()
                
                # STEP 4: Generate explanation
                if plan['needs_explanation']:
                    with st.spinner("✍️ Generating explanation..."):
                        explanation = generate_final_explanation(user_question, evaluation, combined_summary, st.session_state.messages)
                    
                    # Debug: Show explanation
                    with st.expander("✍️ Step 4: Final Report", expanded=True):
                        if explanation:
                            st.markdown(explanation)
                        else:
                            st.warning("No explanation generated")
                
                # Save to chat history and log (unified for all code-based outputs)
                if output:
                    output_type = output.get('type')
                    figures = output.get('figures', [])
                    result_str = output.get('result_str', '')
                    
                    # Display figures if visualization
                    if output_type == 'visualization' and figures:
                        for fig in figures:
                            if hasattr(fig, 'write_image'):
                                st.plotly_chart(fig, width="stretch")
                    
                    # Unified logging
                    if output_type == 'visualization':
                        st.session_state.logger.log_visualization_workflow(
                            user_question, "VISUALIZATION", code, explanation or "Visualization generated", True, figures, "",
                            execution_plan=plan, evaluation=evaluation
                        )
                    else:
                        st.session_state.logger.log_analysis_workflow(
                            user_question, "ANALYSIS", code, result_str, explanation or evaluation or result_str, success=True,
                            execution_plan=plan, evaluation=evaluation
                        )
                    
                    # Unified message append
                    message_data = {
                        "role": "assistant",
                        "content": explanation or evaluation or result_str,
                        "metadata": {
                            "code": code,
                            "plan": plan,
                            "output_type": output_type,
                            "result_str": result_str,
                            "evaluation": evaluation,
                            "explanation": explanation
                        }
                    }
                    
                    # Add visualization-specific fields
                    if output_type == 'visualization' and figures:
                        message_data["type"] = "visualization"
                        message_data["figures"] = figures
                    
                    st.session_state.messages.append(message_data)
                
                else:
                    # Conceptual question (no code)
                    if explanation:
                        st.markdown(explanation)
                        st.session_state.logger.log_text_qa(user_question, explanation)
                        st.session_state.messages.append({
                            "role": "assistant", "content": explanation, 
                            "metadata": {
                                "plan": plan,
                                "explanation": explanation
                            }
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