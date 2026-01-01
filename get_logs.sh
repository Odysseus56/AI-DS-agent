#!/bin/bash

# Quick log download script
# Usage: ./get_logs.sh [session_id] [failed_only]

# Set your Supabase credentials (or export as environment variables)
export SUPABASE_URL="https://eqllwrusaypisfdpuqzh.supabase.co"
export SUPABASE_KEY="sb_publishable_RSGgyyEC9FM1-VjPYcn9rg_IbVM1OVj"

# Parse arguments
SESSION_ID="$1"
FAILED_ONLY="$2"

# Download and format logs
if [ "$FAILED_ONLY" = "failed" ]; then
    python download_logs.py --session "$SESSION_ID" --failed-only --output "failed_logs_${SESSION_ID}.txt"
else
    python download_logs.py --session "$SESSION_ID" --output "session_${SESSION_ID}.txt"
fi

echo "✅ Logs downloaded successfully!"
echo "📁 Check the generated .txt file"
