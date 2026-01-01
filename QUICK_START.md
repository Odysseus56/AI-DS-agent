# Quick Start: Persistent Logging Setup

## ✅ What You Get

With this setup, you'll have:

1. **Persistent logs** that survive app restarts
2. **Admin dashboard** to view all user interactions
3. **Complete transparency** - see all LLM reasoning, code, results, errors
4. **No AWS/GCP required** - uses free Supabase PostgreSQL
5. **Accessible from anywhere** - view logs from Supabase dashboard or your app

---

## 🚀 Setup (15 minutes)

### Step 1: Create Supabase Account (5 min)

1. Go to https://supabase.com
2. Sign up (free - no credit card required)
3. Create new project: `ai-data-scientist-logs`
4. Wait 2-3 minutes for provisioning

### Step 2: Create Database Table (2 min)

1. In Supabase dashboard → **SQL Editor**
2. Click "New query"
3. Paste and run:

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

CREATE INDEX idx_session_id ON interaction_logs(session_id);
CREATE INDEX idx_timestamp ON interaction_logs(timestamp DESC);
CREATE INDEX idx_interaction_type ON interaction_logs(interaction_type);

ALTER TABLE interaction_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all operations" ON interaction_logs
    FOR ALL USING (true);
```

### Step 3: Get API Credentials (1 min)

1. Go to **Settings** → **API**
2. Copy:
   - **Project URL** (e.g., `https://xxxxx.supabase.co`)
   - **anon public** key

### Step 4: Add to Streamlit Secrets

**For Local Development:**

Create `.streamlit/secrets.toml`:
```toml
OPENAI_API_KEY = "your-openai-key"
SUPABASE_URL = "https://xxxxx.supabase.co"
SUPABASE_KEY = "your-anon-key-here"
ADMIN_PASSWORD = "your-secure-password"
```

**For Streamlit Cloud:**

1. Go to your app on share.streamlit.io
2. Click **Settings** → **Secrets**
3. Add:
```toml
OPENAI_API_KEY = "your-openai-key"
SUPABASE_URL = "https://xxxxx.supabase.co"
SUPABASE_KEY = "your-anon-key-here"
ADMIN_PASSWORD = "your-secure-password"
```

### Step 5: Deploy

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
streamlit run app.py

# Or push to Streamlit Cloud
git add .
git commit -m "Add persistent logging with Supabase"
git push
```

---

## 📊 Viewing Logs

### Option 1: Admin Page in Your App

1. Click **🔧 Admin** in sidebar
2. Enter admin password
3. View all sessions, interactions, errors, and analytics

### Option 2: Supabase Dashboard

1. Go to https://supabase.com/dashboard
2. Select your project
3. Click **Table Editor** → `interaction_logs`
4. Filter, search, export to CSV

---

## 🎯 What Gets Logged

Every user interaction logs:

- **Session ID** - unique per user session
- **User question** - what they asked
- **Generated code** - Python code created by LLM
- **Execution result** - output from running the code
- **LLM response** - final answer to user
- **Success/failure** - whether it worked
- **Error messages** - if something failed
- **Metadata** - execution plan, evaluation, etc.

---

## 💡 Benefits

**Before (file-based logging):**
- ❌ Logs lost when app restarts
- ❌ Race conditions with multiple users
- ❌ Can't access logs remotely
- ❌ Hard to query/filter

**After (Supabase logging):**
- ✅ Logs persist forever
- ✅ No race conditions
- ✅ Access from anywhere
- ✅ Easy SQL queries
- ✅ Free tier: 500MB storage

---

## 🔍 Example Queries

View all failed interactions:
```sql
SELECT * FROM interaction_logs 
WHERE success = false 
ORDER BY timestamp DESC;
```

Count interactions by type:
```sql
SELECT interaction_type, COUNT(*) 
FROM interaction_logs 
GROUP BY interaction_type;
```

Find sessions with errors:
```sql
SELECT DISTINCT session_id 
FROM interaction_logs 
WHERE success = false;
```

---

## 🆘 Troubleshooting

**Logs not appearing?**
- Check Supabase credentials in secrets
- Verify table was created correctly
- Check app logs for connection errors

**Can't access admin page?**
- Verify ADMIN_PASSWORD is set in secrets
- Try default password: `admin123`

**Supabase connection failed?**
- App will fall back to file-based logging
- Check console for error messages

---

## 🎉 Done!

Your app now has enterprise-grade logging without the enterprise complexity!
