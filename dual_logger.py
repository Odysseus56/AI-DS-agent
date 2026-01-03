"""
Dual Logger: Writes to both Supabase (cloud) and local .md files (debugging).
Provides graceful fallback and controllable Supabase logging.
"""
import os
from datetime import datetime
from supabase_logger import SupabaseLogger
from code_executor import InteractionLogger


class DualLogger:
    """
    Unified logger that writes to both Supabase and local files.
    - Supabase: Controllable via ENABLE_SUPABASE_LOGGING env var (default: True)
    - Local files: Always writes to logs/ directory for quick debugging
    """
    
    def __init__(self, session_timestamp=None):
        self.session_timestamp = session_timestamp or datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        
        # Always initialize file logger for local debugging
        self.file_logger = InteractionLogger(session_timestamp=self.session_timestamp)
        
        # Initialize Supabase logger only if enabled
        self.supabase_enabled = os.getenv("ENABLE_SUPABASE_LOGGING", "true").lower() in ("true", "1", "yes")
        
        if self.supabase_enabled:
            self.supabase_logger = SupabaseLogger(session_timestamp=self.session_timestamp)
            if not self.supabase_logger.enabled:
                print("⚠️ Supabase credentials not found. Only logging to local files.")
                self.supabase_enabled = False
        else:
            self.supabase_logger = None
            print("ℹ️ Supabase logging disabled via ENABLE_SUPABASE_LOGGING. Only logging to local files.")
    
    def log_interaction(self, interaction_type: str, user_question: str = None, 
                       generated_code: str = None, execution_result: str = None,
                       llm_response: str = None, success: bool = True, 
                       error: str = None, metadata: dict = None):
        """Log any interaction to both Supabase and local files."""
        # Always log to file
        # (InteractionLogger doesn't have a generic log_interaction method, so we skip it here)
        
        # Log to Supabase if enabled
        if self.supabase_enabled and self.supabase_logger:
            try:
                self.supabase_logger.log_interaction(
                    interaction_type=interaction_type,
                    user_question=user_question,
                    generated_code=generated_code,
                    execution_result=execution_result,
                    llm_response=llm_response,
                    success=success,
                    error=error,
                    metadata=metadata
                )
            except Exception as e:
                print(f"⚠️ Failed to log to Supabase: {str(e)}")
    
    def log_text_qa(self, user_question: str, llm_response: str):
        """Log a simple text-based Q&A interaction."""
        # Log to file
        self.file_logger.log_text_qa(user_question, llm_response)
        
        # Log to Supabase if enabled
        if self.supabase_enabled and self.supabase_logger:
            try:
                self.supabase_logger.log_text_qa(user_question, llm_response)
            except Exception as e:
                print(f"⚠️ Failed to log to Supabase: {str(e)}")
    
    def log_analysis_workflow(self, user_question: str, question_type: str, 
                             generated_code: str, execution_result: str, 
                             final_answer: str, success: bool, error: str = "",
                             execution_plan: dict = None, evaluation: str = None):
        """Log a detailed analysis workflow."""
        # Log to file
        self.file_logger.log_analysis_workflow(
            user_question, question_type, generated_code, execution_result,
            final_answer, success, error, execution_plan, evaluation
        )
        
        # Log to Supabase if enabled
        if self.supabase_enabled and self.supabase_logger:
            try:
                self.supabase_logger.log_analysis_workflow(
                    user_question, question_type, generated_code, execution_result,
                    final_answer, success, error, execution_plan, evaluation
                )
            except Exception as e:
                print(f"⚠️ Failed to log to Supabase: {str(e)}")
    
    def log_visualization_workflow(self, user_question: str, question_type: str,
                                   generated_code: str, explanation: str, 
                                   success: bool, figures: list = None, error: str = "",
                                   execution_plan: dict = None, evaluation: str = None):
        """Log a detailed visualization workflow."""
        # Log to file
        self.file_logger.log_visualization_workflow(
            user_question, question_type, generated_code, explanation,
            success, figures, error, execution_plan, evaluation
        )
        
        # Log to Supabase if enabled
        if self.supabase_enabled and self.supabase_logger:
            try:
                self.supabase_logger.log_visualization_workflow(
                    user_question, question_type, generated_code, explanation,
                    success, figures, error, execution_plan, evaluation
                )
            except Exception as e:
                print(f"⚠️ Failed to log to Supabase: {str(e)}")
    
    def log_summary_generation(self, summary_type: str, llm_response: str):
        """Log initial data summary generation."""
        # Log to file
        self.file_logger.log_summary_generation(summary_type, llm_response)
        
        # Log to Supabase if enabled
        if self.supabase_enabled and self.supabase_logger:
            try:
                self.supabase_logger.log_summary_generation(summary_type, llm_response)
            except Exception as e:
                print(f"⚠️ Failed to log to Supabase: {str(e)}")
    
    def log_node_completion(self, node_name: str, state: dict):
        """
        Log when a LangGraph node completes.
        This provides incremental logging during workflow execution.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Create a simple log entry for node completion
        error = state.get('error')
        failed_attempts = state.get('failed_attempts', [])
        log_entry = f"""### Node Completed: {node_name}
*{timestamp}*

**State Summary:**
- Attempts: {state.get('attempts', 0)}
- Success: {state.get('execution_success', 'N/A')}
- Has Plan: {state.get('plan') is not None}
- Has Code: {state.get('code') is not None}
- Has Evaluation: {state.get('evaluation') is not None}
- Has Explanation: {state.get('explanation') is not None}
- Error: {error if error else 'None'}

"""
        
        # If there are failed attempts, show them
        if failed_attempts:
            log_entry += f"**Failed Attempts ({len(failed_attempts)}):**\n"
            for i, attempt in enumerate(failed_attempts[-3:], 1):  # Show last 3 attempts
                log_entry += f"- Attempt {attempt.get('attempt', 'N/A')}: {attempt.get('error', 'No error details')[:100]}{'...' if len(attempt.get('error', '')) > 100 else ''}\n"
            log_entry += "\n"
        
        # If there's an error, add more details
        if error:
            log_entry += f"""**Error Details:**
```
{error}
```

"""
        
        # Write to file logger's session log
        try:
            with open(self.file_logger.session_log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except Exception as e:
            print(f"⚠️ Failed to log node completion to file: {str(e)}")
        
        # Optionally log to Supabase as metadata
        if self.supabase_enabled and self.supabase_logger:
            try:
                self.supabase_logger.log_interaction(
                    interaction_type="node_completion",
                    user_question=state.get('question'),
                    llm_response=f"Node '{node_name}' completed",
                    success=True,
                    metadata={
                        "node_name": node_name,
                        "attempts": state.get('attempts', 0),
                        "execution_success": state.get('execution_success', False)
                    }
                )
            except Exception as e:
                print(f"⚠️ Failed to log node completion to Supabase: {str(e)}")
    
    def get_session_logs(self, session_id: str = None):
        """Retrieve logs for a specific session (Supabase only)."""
        if self.supabase_enabled and self.supabase_logger:
            return self.supabase_logger.get_session_logs(session_id)
        return []
    
    def get_all_sessions(self):
        """Get list of all unique sessions (Supabase only)."""
        if self.supabase_enabled and self.supabase_logger:
            return self.supabase_logger.get_all_sessions()
        return []
