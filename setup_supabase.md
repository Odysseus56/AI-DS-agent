# Supabase Setup Guide for Persistent Logging

## Step 1: Create Free Supabase Account (5 minutes)

1. Go to https://supabase.com
2. Click "Start your project"
3. Sign up with GitHub (easiest) or email
4. Create a new project:
   - Project name: `ai-data-scientist-logs`
   - Database password: (generate a strong one)
   - Region: Choose closest to you
   - Click "Create new project"
5. Wait 2-3 minutes for database to provision

## Step 2: Create Database Table (2 minutes)

1. In your Supabase dashboard, go to **SQL Editor**
2. Click "New query"
3. Paste this SQL and click "Run":

```sql
CREATE TABLE interaction_logs (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    interaction_number INTEGER NOT NULL,
    interaction_type TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_question TEXT,
    generated_code TEXT,
    execution_result TEXT,
    llm_response TEXT,
    success BOOLEAN DEFAULT true,
    error TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for faster queries
CREATE INDEX idx_session_id ON interaction_logs(session_id);
CREATE INDEX idx_timestamp ON interaction_logs(timestamp DESC);
CREATE INDEX idx_interaction_type ON interaction_logs(interaction_type);

-- Enable Row Level Security (optional, for multi-user later)
ALTER TABLE interaction_logs ENABLE ROW LEVEL SECURITY;

-- Create policy to allow all operations (for now)
CREATE POLICY "Allow all operations" ON interaction_logs
    FOR ALL USING (true);
```

## Step 3: Get API Credentials (1 minute)

1. Go to **Settings** → **API**
2. Copy these two values:
   - **Project URL** (looks like: `https://xxxxx.supabase.co`)
   - **anon public** key (under "Project API keys")

## Step 4: Add to Streamlit Secrets

### For Local Development:
Create `.streamlit/secrets.toml`:
```toml
SUPABASE_URL = "https://xxxxx.supabase.co"
SUPABASE_KEY = "your-anon-key-here"
```

### For Streamlit Cloud:
1. Go to your app on share.streamlit.io
2. Click "Settings" → "Secrets"
3. Add:
```toml
SUPABASE_URL = "https://xxxxx.supabase.co"
SUPABASE_KEY = "your-anon-key-here"
```

## Step 5: Install Python Package

Add to `requirements.txt`:
```
supabase
```

## Step 6: Update Your App

Replace the logger in `app.py`:

```python
# OLD:
from code_executor import InteractionLogger

# NEW:
from supabase_logger import SupabaseLogger
```

```python
# OLD:
if 'logger' not in st.session_state:
    st.session_state.logger = InteractionLogger(session_timestamp=st.session_state.session_timestamp)

# NEW:
if 'logger' not in st.session_state:
    st.session_state.logger = SupabaseLogger(session_timestamp=st.session_state.session_timestamp)
```

## Step 7: View Logs

### Option A: Supabase Dashboard
1. Go to **Table Editor** → `interaction_logs`
2. See all logs in real-time
3. Filter, search, export to CSV

### Option B: Add Admin Page to Your App
See the admin page code in the next section.

## Done! 🎉

Your logs now persist forever and you can access them from anywhere.

---

## Viewing Logs from Supabase Dashboard

1. Go to https://supabase.com/dashboard
2. Select your project
3. Click **Table Editor** → `interaction_logs`
4. You'll see all interactions with:
   - Session ID
   - User questions
   - Generated code
   - Results
   - Errors
   - Full metadata

You can:
- Filter by session, date, success/failure
- Search for specific questions or errors
- Export to CSV for analysis
- Run custom SQL queries

## Cost

**Free tier includes:**
- 500 MB database storage
- 2 GB bandwidth/month
- Unlimited API requests

For a logging app, this is **more than enough** for thousands of interactions per month.
