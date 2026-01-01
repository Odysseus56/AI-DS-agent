#!/usr/bin/env python3
"""
Simple script to download logs from Supabase and save as formatted markdown.
Uses secrets.toml for credentials (no hardcoded values).
"""

import os
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import streamlit as st
from supabase import create_client, Client
from supabase_logger import utc_to_pst

def get_supabase_client() -> Client:
    """Get Supabase client using secrets.toml (same as app.py)."""
    try:
        # Try Streamlit secrets first (for local development)
        supabase_url = st.secrets["SUPABASE_URL"]
        supabase_key = st.secrets["SUPABASE_KEY"]
    except (KeyError, FileNotFoundError):
        # Fallback to environment variables
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ Supabase credentials not found in secrets.toml or environment variables")
        return None
    
    return create_client(supabase_url, supabase_key)

def download_all_logs(client: Client) -> list:
    """Download all logs from Supabase."""
    try:
        response = client.table("interaction_logs").select("*").order("timestamp", desc=True).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"❌ Error downloading logs: {str(e)}")
        return []

def format_logs_as_markdown(logs: list) -> str:
    """Format logs as readable markdown."""
    if not logs:
        return "# No logs found\n\nNo interaction logs available in the database."
    
    # Group logs by session
    sessions = {}
    for log in logs:
        session_id = log.get('session_id', 'unknown')
        if session_id not in sessions:
            sessions[session_id] = []
        sessions[session_id].append(log)
    
    # Sort sessions by timestamp (newest first)
    sorted_sessions = sorted(sessions.items(), 
                            key=lambda x: max([log.get('timestamp', '') for log in x[1]]), 
                            reverse=True)
    
    # Build markdown
    md_lines = []
    md_lines.append("# AI Data Scientist - Remote Logs")
    md_lines.append(f"*Downloaded: {utc_to_pst(datetime.now(timezone.utc).isoformat())}*")
    md_lines.append(f"*Total Sessions: {len(sessions)}*")
    md_lines.append(f"*Total Interactions: {len(logs)}*")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")
    
    for session_id, session_logs in sorted_sessions:
        # Sort logs within session by interaction number
        session_logs.sort(key=lambda x: x.get('interaction_number', 0))
        
        md_lines.append(f"## 📅 Session: {session_id}")
        md_lines.append("")
        
        for log in session_logs:
            timestamp = log.get('timestamp', '')
            pst_timestamp = utc_to_pst(timestamp) if timestamp else 'Unknown'
            interaction_type = log.get('interaction_type', 'unknown')
            interaction_num = log.get('interaction_number', 0)
            success = log.get('success', True)
            
            status = "✅" if success else "❌"
            md_lines.append(f"### {status} Interaction #{interaction_num} - {interaction_type}")
            md_lines.append(f"*{pst_timestamp}*")
            md_lines.append("")
            
            # User question
            if log.get('user_question'):
                md_lines.append("**📝 User Question:**")
                md_lines.append(log['user_question'])
                md_lines.append("")
            
            # Generated code
            if log.get('generated_code'):
                md_lines.append("**💻 Generated Code:**")
                md_lines.append("```python")
                md_lines.append(log['generated_code'])
                md_lines.append("```")
                md_lines.append("")
            
            # Execution result
            if log.get('execution_result'):
                md_lines.append("**⚙️ Execution Result:**")
                md_lines.append("```")
                md_lines.append(log['execution_result'])
                md_lines.append("```")
                md_lines.append("")
            
            # Error (if failed)
            if not success and log.get('error'):
                md_lines.append("**🚨 Error:**")
                md_lines.append("```")
                md_lines.append(log['error'])
                md_lines.append("```")
                md_lines.append("")
            
            # LLM response
            if log.get('llm_response'):
                md_lines.append("**🤖 LLM Response:**")
                md_lines.append(log['llm_response'])
                md_lines.append("")
            
            # Metadata (if any)
            if log.get('metadata'):
                try:
                    metadata = json.loads(log['metadata']) if isinstance(log['metadata'], str) else log['metadata']
                    if metadata:
                        md_lines.append("**📋 Metadata:**")
                        md_lines.append("```json")
                        md_lines.append(json.dumps(metadata, indent=2))
                        md_lines.append("```")
                        md_lines.append("")
                except:
                    pass
            
            md_lines.append("---")
            md_lines.append("")
    
    return "\n".join(md_lines)

def main():
    """Main function to download and save logs."""
    print("📥 Downloading logs from Supabase...")
    
    # Get Supabase client
    client = get_supabase_client()
    if not client:
        return
    
    # Download logs
    logs = download_all_logs(client)
    if not logs:
        print("📭 No logs found")
        return
    
    # Format as markdown
    print("📝 Formatting logs...")
    markdown_content = format_logs_as_markdown(logs)
    
    # Create output directory
    output_dir = Path("logs/remote")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"remote_logs_{timestamp}.md"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    
    print(f"✅ Logs saved to: {output_file}")
    print(f"📊 {len(logs)} interactions from {len(set([log.get('session_id') for log in logs]))} sessions")

if __name__ == "__main__":
    main()
