"""
Configuration constants for the AI Data Scientist Agent.

This module centralizes all magic numbers, strings, and configuration values
to make them easy to find and modify.
"""

# ==== FILE SIZE LIMITS ====
MAX_FILE_SIZE_BYTES = 100_000_000  # 100MB
MAX_DATASET_ROWS = 1_000_000  # 1 million rows

# ==== LLM CONFIGURATION ====
# Model Selection
MODEL_FAST = "gpt-4o-mini"  # Fast model for simple tasks
MODEL_SMART = "gpt-4o"  # Smart model for complex tasks (code generation, evaluation)

# Token Limits
MAX_TOKENS_SUMMARY = 2000  # For dataset summaries

# ==== REACT AGENT SETTINGS ====
# Iteration limits by complexity
MAX_ITERATIONS_SIMPLE = 5      # Simple lookup/aggregation
MAX_ITERATIONS_STANDARD = 8    # Hypothesis tests, correlations
MAX_ITERATIONS_COMPLEX = 10    # Multiple datasets, ML models
MAX_ITERATIONS_DEFAULT = 8     # Default if complexity unknown

# ==== CHAT HISTORY ====
MAX_CHAT_MESSAGES = 20  # Keep last N messages to prevent memory issues

# ==== DATA DISPLAY ====
SAMPLE_ROWS_COUNT = 5  # Number of rows to show in data summaries

# ==== ENVIRONMENT MODE ====
# Set this to control the operating environment
# Options: "local" or "streamlit"
# - local: CLI/headless mode - saves visualizations to logs, no Supabase
# - streamlit: Web UI mode - no viz in logs (causes issues), uses Supabase
# Override via environment variable: ENVIRONMENT_MODE=local or ENVIRONMENT_MODE=streamlit
DEFAULT_ENVIRONMENT_MODE = "local"  # Change to "local" for CLI/headless testing

# ==== LOGGING ====
LOG_DIRECTORY = "logs"
LOG_LOCAL_DIR = "logs/local"  # Streamlit app local logs
LOG_REMOTE_DIR = "logs/remote"  # Downloaded Supabase logs
LOG_CLI_DIR = "logs/cli"  # CLI test runner logs
SESSION_TIMESTAMP_FORMAT = "%Y-%m-%d_%H-%M-%S"
DISPLAY_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

# ==== UI CONFIGURATION ====
PAGE_TITLE = "AI Data Scientist"
PAGE_ICON = "📊"
DEFAULT_TIMEZONE = "America/Los_Angeles"  # PST fallback

# ==== ERROR MESSAGES ====
ERROR_FILE_TOO_LARGE = "❌ File too large. Please upload a CSV file smaller than 100MB."
ERROR_INVALID_CSV = "❌ Error reading CSV file: {error}"
ERROR_CSV_INFO = "Please ensure the file is a valid CSV format."
WARNING_DATASET_EXISTS = "⚠️ Dataset '{name}' is already loaded."
WARNING_DATASET_TRUNCATED = "⚠️ Dataset truncated to 1 million rows for performance."
SUCCESS_FILE_UPLOADED = "✅ File uploaded: {name}"
SUCCESS_SAMPLE_LOADED = "✅ Sample dataset loaded: {name}"

# ==== ENVIRONMENT VARIABLES ====
ENV_OPENAI_API_KEY = "OPENAI_API_KEY"
ENV_SUPABASE_URL = "SUPABASE_URL"
ENV_SUPABASE_KEY = "SUPABASE_KEY"
ENV_ADMIN_PASSWORD = "ADMIN_PASSWORD"
ENV_ENABLE_SUPABASE_LOGGING = "ENABLE_SUPABASE_LOGGING"
ENV_ENVIRONMENT_MODE = "ENVIRONMENT_MODE"  # Override environment mode
