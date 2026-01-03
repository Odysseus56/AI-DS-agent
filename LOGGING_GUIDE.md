# Logging Guide

## Overview

The AI Data Scientist now uses a **DualLogger** system that writes to both:
1. **Supabase** (cloud database) - for persistent storage and analytics
2. **Local .md files** (logs/ directory) - for quick debugging

## Features

### 1. Controllable Supabase Logging

You can enable/disable Supabase logging using an environment variable:

```bash
# Disable Supabase logging (only write to local files)
ENABLE_SUPABASE_LOGGING=false

# Enable Supabase logging (default)
ENABLE_SUPABASE_LOGGING=true
```

**Use cases:**
- Set to `false` when testing schema changes to avoid errors
- Set to `false` for local development without Supabase credentials
- Set to `true` for production deployments

### 2. Local File Logging

All interactions are **always** written to `.md` files in the `logs/` directory:

- **Session logs**: `logs/log_YYYY-MM-DD_HH-MM.md` - One file per session
- **Global log**: `logs/log_global.md` - All sessions combined

These files are human-readable markdown with:
- Execution plans
- Generated code
- Execution results
- Evaluations
- Final explanations
- Embedded visualizations (base64)

### 3. Incremental Node Logging

Logging now happens **after each LangGraph node completes**, not just at the end:

- `plan` node → Logs execution plan
- `code` node → Logs code generation and execution
- `evaluate` node → Logs critical evaluation
- `explain` node → Logs final explanation
- `error` node → Logs error details

This provides real-time visibility into the workflow progress.

## Implementation Details

### DualLogger Class

Located in `dual_logger.py`, this class:
- Wraps both `SupabaseLogger` and `InteractionLogger`
- Provides graceful fallback if Supabase is unavailable
- Catches and logs Supabase errors without breaking the app
- Always writes to local files regardless of Supabase status

### Key Methods

```python
# Log a complete workflow
logger.log_analysis_workflow(...)
logger.log_visualization_workflow(...)
logger.log_text_qa(...)

# Log node completion (incremental)
logger.log_node_completion(node_name, state)

# Log dataset upload
logger.log_summary_generation(...)
```

## Troubleshooting

### Supabase Errors

If you see warnings like:
```
⚠️ Failed to log to Supabase: [error message]
```

**Solution**: Set `ENABLE_SUPABASE_LOGGING=false` to disable Supabase logging temporarily.

### Missing Local Logs

If local logs aren't being created:
1. Check that the `logs/` directory exists (it's auto-created)
2. Verify file permissions on the `logs/` directory
3. Check console for file write errors

### Schema Changes

When modifying the Supabase schema:
1. Set `ENABLE_SUPABASE_LOGGING=false`
2. Test your changes locally with file logging only
3. Update the schema in Supabase
4. Re-enable with `ENABLE_SUPABASE_LOGGING=true`

## Example Usage

```python
# Initialize logger (done automatically in app.py)
from dual_logger import DualLogger
logger = DualLogger(session_timestamp="2026-01-02_18-00")

# Log a successful analysis
logger.log_analysis_workflow(
    user_question="What is the average age?",
    question_type="ANALYSIS",
    generated_code="result = df['age'].mean()",
    execution_result="35.5",
    final_answer="The average age is 35.5 years.",
    success=True,
    execution_plan={"reasoning": "Simple aggregation"},
    evaluation="Result looks correct"
)

# Log node completion (incremental)
logger.log_node_completion("plan", state)
```

## Benefits

✅ **Robust**: Graceful fallback when Supabase is unavailable  
✅ **Debuggable**: Always have local .md files for quick inspection  
✅ **Controllable**: Easy on/off switch for Supabase  
✅ **Incremental**: See progress as each node completes  
✅ **Production-ready**: Handles errors without breaking the app
