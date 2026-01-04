"""Log page for AI Data Scientist Agent."""
import re
import streamlit as st
from code_executor import get_log_content


def render_log_page(session_timestamp: str):
    """Render the Log page with session logs and download options.
    
    Args:
        session_timestamp: Current session timestamp for log filtering
    """
    st.markdown("## 📋 Session Logs")
    
    # Download buttons at top
    col_session, col_global = st.columns(2)
    with col_session:
        st.markdown("**Current Session Log:**")
        st.download_button(
            label="📥 Download Session Markdown",
            data=get_log_content(session_timestamp=session_timestamp),
            file_name=f"log_{session_timestamp}.md",
            mime="text/markdown",
            width="stretch"
        )
    with col_global:
        st.markdown("**All Sessions Log:**")
        st.download_button(
            label="📥 Download Global Markdown",
            data=get_log_content(session_timestamp=None),
            file_name="log_global.md",
            mime="text/markdown",
            width="stretch"
        )
    
    st.divider()
    
    # Parse and display log with collapsible sections
    # Split log into interactions
    interactions = re.split(r'(?=## Interaction #)', get_log_content(session_timestamp=session_timestamp))
    
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
