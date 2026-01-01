#!/usr/bin/env python3
"""
Download logs from Supabase for debugging.
Usage: python download_logs.py [--session SESSION_ID] [--failed-only] [--hours HOURS]
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
import pandas as pd
from supabase import create_client, Client

def get_supabase_client() -> Client:
    """Get Supabase client using environment variables or secrets."""
    # Try environment variables first
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url:
        print("❌ SUPABASE_URL not found in environment variables")
        print("Set it with: export SUPABASE_URL='https://your-project.supabase.co'")
        sys.exit(1)
    
    if not supabase_key:
        print("❌ SUPABASE_KEY not found in environment variables")
        print("Set it with: export SUPABASE_KEY='your-anon-key'")
        sys.exit(1)
    
    return create_client(supabase_url, supabase_key)

def download_logs(client: Client, session_id: str = None, failed_only: bool = False, hours: int = None) -> pd.DataFrame:
    """Download logs from Supabase with optional filtering."""
    
    # Build query
    query = client.table("interaction_logs").select("*")
    
    # Apply filters
    if session_id:
        query = query.eq("session_id", session_id)
    
    if failed_only:
        query = query.eq("success", False)
    
    if hours:
        cutoff_time = datetime.now() - timedelta(hours=hours)
        query = query.gte("timestamp", cutoff_time.isoformat())
    
    # Execute query
    response = query.order("timestamp", desc=True).execute()
    
    if not response.data:
        print("📭 No logs found matching your criteria")
        return pd.DataFrame()
    
    df = pd.DataFrame(response.data)
    print(f"📊 Downloaded {len(df)} log entries")
    return df

def format_logs_for_display(df: pd.DataFrame) -> str:
    """Format logs in a readable format for debugging."""
    if df.empty:
        return "No logs to display"
    
    output = []
    output.append("=" * 80)
    output.append(f"AI DATA SCIENTIST LOGS - {len(df)} entries")
    output.append("=" * 80)
    output.append("")
    
    # Group by session
    for session_id in df['session_id'].unique():
        session_logs = df[df['session_id'] == session_id].sort_values('interaction_number')
        
        output.append(f"🔍 SESSION: {session_id}")
        output.append("-" * 50)
        
        for _, log in session_logs.iterrows():
            timestamp = log.get('timestamp', '')
            interaction_type = log.get('interaction_type', 'unknown')
            interaction_num = log.get('interaction_number', 0)
            success = log.get('success', True)
            
            status = "✅" if success else "❌"
            output.append(f"\n{status} #{interaction_num} - {interaction_type} - {timestamp}")
            
            if log.get('user_question'):
                output.append(f"📝 Question: {log['user_question']}")
            
            if log.get('generated_code'):
                output.append("💻 Generated Code:")
                output.append("```python")
                output.append(log['generated_code'])
                output.append("```")
            
            if log.get('execution_result'):
                output.append("⚙️ Execution Result:")
                output.append("```")
                output.append(log['execution_result'])
                output.append("```")
            
            if not success and log.get('error'):
                output.append(f"🚨 Error: {log['error']}")
            
            if log.get('llm_response'):
                output.append(f"🤖 LLM Response: {log['llm_response']}")
            
            output.append("-" * 30)
        
        output.append("\n" + "=" * 80 + "\n")
    
    return "\n".join(output)

def main():
    parser = argparse.ArgumentParser(description="Download logs from Supabase")
    parser.add_argument("--session", help="Filter by specific session ID")
    parser.add_argument("--failed-only", action="store_true", help="Only download failed interactions")
    parser.add_argument("--hours", type=int, help="Only logs from last N hours")
    parser.add_argument("--output", default="logs_debug.txt", help="Output file name")
    parser.add_argument("--csv", action="store_true", help="Export as CSV instead of formatted text")
    parser.add_argument("--sessions", action="store_true", help="List all available sessions")
    
    args = parser.parse_args()
    
    # Get Supabase client
    client = get_supabase_client()
    
    # List sessions if requested
    if args.sessions:
        print("📋 Available Sessions:")
        response = client.table("interaction_logs").select("session_id").execute()
        sessions = list(set([log['session_id'] for log in response.data]))
        for session in sorted(sessions, reverse=True):
            print(f"  - {session}")
        return
    
    # Download logs
    df = download_logs(client, args.session, args.failed_only, args.hours)
    
    if df.empty:
        return
    
    # Export
    if args.csv:
        # Export as CSV
        df.to_csv(args.output, index=False)
        print(f"📁 Logs exported to {args.output} (CSV format)")
    else:
        # Export as formatted text
        formatted_logs = format_logs_for_display(df)
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(formatted_logs)
        print(f"📁 Logs exported to {args.output} (formatted text)")
    
    # Show summary
    print(f"\n📊 Summary:")
    print(f"  Total entries: {len(df)}")
    print(f"  Sessions: {df['session_id'].nunique()}")
    print(f"  Success rate: {(df['success'].sum() / len(df) * 100):.1f}%")
    if not df['success'].all():
        print(f"  Failed: {len(df) - df['success'].sum()}")

if __name__ == "__main__":
    main()
