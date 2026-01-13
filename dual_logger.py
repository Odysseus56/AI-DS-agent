"""
Dual Logger: Writes to both Supabase (cloud) and local .md files (debugging).
Provides graceful fallback and controllable Supabase logging.

Environment-aware:
- Local mode: Only file logging, no Supabase
- Streamlit mode: Dual logging (file + Supabase)
"""
import os
from typing import Optional, Dict, List, Any
from datetime import datetime
from supabase_logger import SupabaseLogger
from code_executor import InteractionLogger
from config import SESSION_TIMESTAMP_FORMAT
from environment import should_use_supabase, get_log_directory, get_environment_mode


class DualLogger:
    """
    Unified logger that writes to both Supabase and local files.
    
    Environment-aware behavior:
    - Local mode (CLI/headless): Only file logging to logs/cli/, no Supabase
    - Streamlit mode (web UI): Dual logging to logs/local/ + Supabase
    
    Can be overridden via ENABLE_SUPABASE_LOGGING environment variable.
    """
    
    def __init__(self, session_timestamp: Optional[str] = None):
        self.session_timestamp = session_timestamp or datetime.now().strftime(SESSION_TIMESTAMP_FORMAT)
        self.environment_mode = get_environment_mode()
        
        # Initialize file logger with environment-appropriate directory
        log_dir = get_log_directory()
        self.file_logger = InteractionLogger(session_timestamp=self.session_timestamp, log_dir=log_dir)
        
        # Initialize Supabase logger based on environment
        self.supabase_enabled = should_use_supabase()
        
        if self.supabase_enabled:
            self.supabase_logger = SupabaseLogger(session_timestamp=self.session_timestamp)
            if not self.supabase_logger.enabled:
                print("⚠️ Supabase credentials not found. Only logging to local files.")
                self.supabase_enabled = False
        else:
            self.supabase_logger = None
            if self.environment_mode == "local":
                print(f"ℹ️ Local environment mode: Logging to {log_dir}/ only (no Supabase)")
            else:
                print("ℹ️ Supabase logging disabled. Only logging to local files.")
    
    def log_interaction(self, interaction_type: str, user_question: Optional[str] = None, 
                       generated_code: Optional[str] = None, execution_result: Optional[str] = None,
                       llm_response: Optional[str] = None, success: bool = True, 
                       error: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> None:
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
    
    def log_text_qa(self, user_question: str, llm_response: str) -> None:
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
                             execution_plan: Optional[Dict[str, Any]] = None, evaluation: Optional[str] = None) -> None:
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
                                   success: bool, figures: Optional[List[Any]] = None, error: str = "",
                                   execution_plan: Optional[Dict[str, Any]] = None, evaluation: Optional[str] = None) -> None:
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
    
    def log_summary_generation(self, summary_type: str, llm_response: str) -> None:
        """Log initial data summary generation."""
        # Log to file
        self.file_logger.log_summary_generation(summary_type, llm_response)
        
        # Log to Supabase if enabled
        if self.supabase_enabled and self.supabase_logger:
            try:
                self.supabase_logger.log_summary_generation(summary_type, llm_response)
            except Exception as e:
                print(f"⚠️ Failed to log to Supabase: {str(e)}")
    
    def log_node_completion(self, node_name: str, state: Dict[str, Any]) -> None:
        """
        Log when a LangGraph node completes.
        This provides incremental logging during workflow execution.
        Supports both old and new MVP architecture state fields.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Create a simple log entry for node completion
        error = state.get('error')
        failed_attempts = state.get('failed_attempts', [])
        
        # Build state summary based on MVP architecture
        log_entry = f"""### Node Completed: {node_name}
*{timestamp}*

**State Summary:**
"""
        
        # Node-specific logging for MVP architecture
        if node_name == "node_0_understand":
            log_entry += f"- Needs Data Work: {state.get('needs_data_work', 'N/A')}\n"
            log_entry += f"- Reasoning: {state.get('question_reasoning', 'N/A')}\n"
        
        elif node_name == "node_1b_requirements":
            req = state.get('requirements', {})
            if req:
                log_entry += f"- Analysis Type: {req.get('analysis_type', 'N/A')}\n"
                log_entry += f"- Variables Needed: {req.get('variables_needed', [])}\n"
                log_entry += f"- Success Criteria: {req.get('success_criteria', 'N/A')}\n"
        
        elif node_name == "node_2_profile":
            profile = state.get('data_profile', {})
            if profile:
                log_entry += f"- Available Columns: {profile.get('available_columns', [])}\n"
                log_entry += f"- Missing Columns: {profile.get('missing_columns', [])}\n"
                log_entry += f"- Is Suitable: {profile.get('is_suitable', 'N/A')}\n"
        
        elif node_name == "node_3_alignment":
            alignment = state.get('alignment_check', {})
            if alignment:
                log_entry += f"- Aligned: {alignment.get('aligned', 'N/A')}\n"
                log_entry += f"- Gaps: {alignment.get('gaps', [])}\n"
                log_entry += f"- Recommendation: {alignment.get('recommendation', 'N/A')}\n"
            log_entry += f"- Alignment Iterations: {state.get('alignment_iterations', 0)}\n"
        
        elif node_name == "node_4_code":
            log_entry += f"- Code Attempts: {state.get('code_attempts', 0)}\n"
            log_entry += f"- Execution Success: {state.get('execution_success', 'N/A')}\n"
            log_entry += f"- Has Code: {state.get('code') is not None}\n"
            log_entry += f"- Error: {error if error else 'None'}\n"
        
        elif node_name == "node_5_evaluate":
            evaluation = state.get('evaluation', {})
            if evaluation:
                log_entry += f"- Is Valid: {evaluation.get('is_valid', 'N/A')}\n"
                log_entry += f"- Confidence: {evaluation.get('confidence', 'N/A')}\n"
                log_entry += f"- Issues Found: {evaluation.get('issues_found', [])}\n"
                log_entry += f"- Recommendation: {evaluation.get('recommendation', 'N/A')}\n"
        
        elif node_name == "node_5a_remediation":
            remediation = state.get('remediation_plan', {})
            if remediation:
                log_entry += f"- Root Cause: {remediation.get('root_cause', 'N/A')}\n"
                log_entry += f"- Action: {remediation.get('action', 'N/A')}\n"
                log_entry += f"- Guidance: {remediation.get('guidance', 'N/A')}\n"
            log_entry += f"- Total Remediations: {state.get('total_remediations', 0)}\n"
        
        elif node_name in ["node_1a_explain", "node_6_explain"]:
            log_entry += f"- Has Explanation: {state.get('explanation') is not None}\n"
            log_entry += f"- Has Final Output: {state.get('final_output') is not None}\n"
        
        else:
            # Fallback for old architecture or unknown nodes
            log_entry += f"- Attempts: {state.get('attempts', state.get('code_attempts', 0))}\n"
            log_entry += f"- Success: {state.get('execution_success', 'N/A')}\n"
            log_entry += f"- Has Plan: {state.get('plan') is not None}\n"
            log_entry += f"- Has Code: {state.get('code') is not None}\n"
            log_entry += f"- Has Evaluation: {state.get('evaluation') is not None}\n"
            log_entry += f"- Has Explanation: {state.get('explanation') is not None}\n"
            log_entry += f"- Error: {error if error else 'None'}\n"
        
        log_entry += "\n"
        
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
                        "code_attempts": state.get('code_attempts', 0),
                        "alignment_iterations": state.get('alignment_iterations', 0),
                        "total_remediations": state.get('total_remediations', 0),
                        "execution_success": state.get('execution_success', False)
                    }
                )
            except Exception as e:
                print(f"⚠️ Failed to log node completion to Supabase: {str(e)}")
    
    def log_react_execution(self, exec_log) -> None:
        """
        Log a V2 ReAct agent execution with full detail.
        
        Args:
            exec_log: ExecutionLog object from react_agent.py containing
                      iterations, tool calls, timing, and results.
        """
        # Write detailed markdown to file
        try:
            markdown_content = exec_log.to_markdown()
            with open(self.file_logger.session_log_file, 'a', encoding='utf-8') as f:
                f.write(markdown_content)
        except Exception as e:
            print(f"⚠️ Failed to log ReAct execution to file: {str(e)}")
        
        # Log summary to Supabase if enabled
        if self.supabase_enabled and self.supabase_logger:
            try:
                self.supabase_logger.log_interaction(
                    interaction_type="react_execution",
                    user_question=exec_log.question,
                    llm_response=f"Completed with {len(exec_log.iterations)} iterations, {exec_log.total_tool_calls} tool calls",
                    success=exec_log.final_output_type != "error",
                    metadata={
                        "architecture": "v2_react",
                        "iterations": len(exec_log.iterations),
                        "total_tool_calls": exec_log.total_tool_calls,
                        "output_type": exec_log.final_output_type,
                        "confidence": exec_log.final_confidence,
                        "loop_detected": exec_log.loop_detected,
                        "max_iterations_reached": exec_log.max_iterations_reached,
                        "start_time": exec_log.start_time,
                        "end_time": exec_log.end_time,
                        "execution_log": exec_log.to_dict()
                    }
                )
            except Exception as e:
                print(f"⚠️ Failed to log ReAct execution to Supabase: {str(e)}")
    
    def get_session_logs(self, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve logs for a specific session (Supabase only)."""
        if self.supabase_enabled and self.supabase_logger:
            return self.supabase_logger.get_session_logs(session_id)
        return []
    
    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """Get list of all unique sessions (Supabase only)."""
        if self.supabase_enabled and self.supabase_logger:
            return self.supabase_logger.get_all_sessions()
        return []
