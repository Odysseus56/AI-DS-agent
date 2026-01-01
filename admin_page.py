import streamlit as st
import pandas as pd
from datetime import datetime
import json

def render_admin_page(logger):
    """
    Admin page to view all interaction logs from Supabase.
    Password-protected for security.
    """
    st.markdown("## 🔧 Admin Panel - Interaction Logs")
    
    # Simple password protection
    admin_password = st.text_input("Enter admin password:", type="password", key="admin_password")
    
    # Get password from secrets or use default
    try:
        correct_password = st.secrets.get("ADMIN_PASSWORD", "admin123")
    except:
        correct_password = "admin123"
    
    if admin_password == correct_password:
        st.success("✅ Access granted")
        
        # Check if Supabase logger is enabled
        if not logger.enabled:
            st.error("❌ Supabase logging is not enabled. Please configure SUPABASE_URL and SUPABASE_KEY in secrets.")
            st.info("See setup_supabase.md for instructions.")
            return
        
        # Tabs for different views
        tab1, tab2, tab3 = st.tabs(["📊 All Sessions", "🔍 Session Details", "📈 Analytics"])
        
        with tab1:
            st.markdown("### All Sessions")
            
            # Get all sessions
            sessions = logger.get_all_sessions()
            
            if sessions:
                st.info(f"Found {len(sessions)} unique sessions")
                
                # Display sessions as a table
                for session_id in sessions:
                    with st.expander(f"📅 Session: {session_id}", expanded=False):
                        logs = logger.get_session_logs(session_id)
                        
                        if logs:
                            st.markdown(f"**Total Interactions:** {len(logs)}")
                            
                            # Show summary stats
                            success_count = sum(1 for log in logs if log.get('success'))
                            error_count = len(logs) - success_count
                            
                            col1, col2, col3 = st.columns(3)
                            col1.metric("Total", len(logs))
                            col2.metric("Success", success_count, delta=None)
                            col3.metric("Errors", error_count, delta=None)
                            
                            # Show each interaction
                            for i, log in enumerate(reversed(logs), 1):
                                status = "✅" if log.get('success') else "❌"
                                interaction_type = log.get('interaction_type', 'unknown')
                                timestamp = log.get('timestamp', '')
                                question = log.get('user_question', 'N/A')
                                
                                with st.expander(f"{status} #{i} - {interaction_type} - {timestamp[:19]}", expanded=False):
                                    if question and question != 'N/A':
                                        st.markdown(f"**User Question:**")
                                        st.info(question)
                                    
                                    if log.get('generated_code'):
                                        st.markdown("**Generated Code:**")
                                        st.code(log['generated_code'], language='python')
                                    
                                    if log.get('execution_result'):
                                        st.markdown("**Execution Result:**")
                                        st.code(log['execution_result'])
                                    
                                    if log.get('llm_response'):
                                        st.markdown("**LLM Response:**")
                                        st.markdown(log['llm_response'])
                                    
                                    if log.get('error'):
                                        st.markdown("**Error:**")
                                        st.error(log['error'])
                                    
                                    if log.get('metadata'):
                                        st.markdown("**Metadata:**")
                                        try:
                                            metadata = json.loads(log['metadata']) if isinstance(log['metadata'], str) else log['metadata']
                                            st.json(metadata)
                                        except:
                                            st.text(log['metadata'])
            else:
                st.warning("No sessions found. Start using the app to generate logs.")
        
        with tab2:
            st.markdown("### Session Details")
            
            # Get all sessions for dropdown
            sessions = logger.get_all_sessions()
            
            if sessions:
                selected_session = st.selectbox("Select a session:", sessions)
                
                if selected_session:
                    logs = logger.get_session_logs(selected_session)
                    
                    if logs:
                        # Convert to DataFrame for easier viewing
                        df = pd.DataFrame(logs)
                        
                        # Select columns to display
                        display_cols = ['interaction_number', 'interaction_type', 'timestamp', 'success', 'user_question']
                        available_cols = [col for col in display_cols if col in df.columns]
                        
                        st.dataframe(df[available_cols], use_container_width=True)
                        
                        # Download as CSV
                        csv = df.to_csv(index=False)
                        st.download_button(
                            label="📥 Download Session as CSV",
                            data=csv,
                            file_name=f"session_{selected_session}.csv",
                            mime="text/csv"
                        )
                        
                        # Download as JSON
                        json_str = json.dumps(logs, indent=2)
                        st.download_button(
                            label="📥 Download Session as JSON",
                            data=json_str,
                            file_name=f"session_{selected_session}.json",
                            mime="application/json"
                        )
            else:
                st.warning("No sessions found.")
        
        with tab3:
            st.markdown("### Analytics")
            
            # Get all logs
            all_logs = []
            sessions = logger.get_all_sessions()
            for session_id in sessions:
                all_logs.extend(logger.get_session_logs(session_id))
            
            if all_logs:
                df = pd.DataFrame(all_logs)
                
                # Overall stats
                st.markdown("#### Overall Statistics")
                col1, col2, col3, col4 = st.columns(4)
                
                total_interactions = len(df)
                success_rate = (df['success'].sum() / total_interactions * 100) if total_interactions > 0 else 0
                unique_sessions = df['session_id'].nunique()
                
                col1.metric("Total Interactions", total_interactions)
                col2.metric("Success Rate", f"{success_rate:.1f}%")
                col3.metric("Unique Sessions", unique_sessions)
                col4.metric("Avg per Session", f"{total_interactions/unique_sessions:.1f}" if unique_sessions > 0 else "0")
                
                # Interaction types breakdown
                st.markdown("#### Interaction Types")
                type_counts = df['interaction_type'].value_counts()
                st.bar_chart(type_counts)
                
                # Success/Failure breakdown
                st.markdown("#### Success vs Failure")
                success_counts = df['success'].value_counts()
                success_df = pd.DataFrame({
                    'Status': ['Success' if k else 'Failure' for k in success_counts.index],
                    'Count': success_counts.values
                })
                st.bar_chart(success_df.set_index('Status'))
                
                # Recent errors
                st.markdown("#### Recent Errors")
                errors = df[df['success'] == False].sort_values('timestamp', ascending=False).head(10)
                if len(errors) > 0:
                    for _, error in errors.iterrows():
                        with st.expander(f"❌ {error.get('timestamp', '')} - {error.get('interaction_type', '')}"):
                            st.markdown(f"**Question:** {error.get('user_question', 'N/A')}")
                            st.error(error.get('error', 'No error message'))
                            if error.get('generated_code'):
                                st.code(error['generated_code'], language='python')
                else:
                    st.success("No errors found! 🎉")
            else:
                st.warning("No logs available for analytics.")
    
    elif admin_password:
        st.error("❌ Invalid password")
        st.info("💡 Set ADMIN_PASSWORD in Streamlit secrets for production use.")
