import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import io
import base64
import os
from datetime import datetime


class InteractionLogger:
    """
    Comprehensive logger for all user interactions with the AI assistant.
    Saves to markdown format for easy reading and navigation.
    Each session gets its own timestamped log file, and all interactions are also logged to a global log.
    """
    
    def __init__(self, session_timestamp=None):
        # Create logs directory if it doesn't exist
        self.logs_dir = "logs"
        os.makedirs(self.logs_dir, exist_ok=True)
        
        # Create session-specific log filename with timestamp
        if session_timestamp:
            self.session_log_file = os.path.join(self.logs_dir, f"log_{session_timestamp}.md")
        else:
            # Fallback to current timestamp if none provided
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
            self.session_log_file = os.path.join(self.logs_dir, f"log_{timestamp}.md")
        
        # Global log file that accumulates all sessions
        self.global_log_file = os.path.join(self.logs_dir, "log_global.md")
        
        self.interaction_count = 0
        self.session_timestamp = session_timestamp
        
        # Initialize session log file with header if it doesn't exist
        try:
            with open(self.session_log_file, 'r', encoding='utf-8') as f:
                pass
        except FileNotFoundError:
            with open(self.session_log_file, 'w', encoding='utf-8') as f:
                f.write("# AI Data Scientist - Session Log\n\n")
                f.write("This log contains interactions for this specific session.\n\n")
                if session_timestamp:
                    f.write(f"**Session Timestamp:** {session_timestamp}\n\n")
                f.write("---\n\n")
        
        # Initialize global log file with header if it doesn't exist
        try:
            with open(self.global_log_file, 'r', encoding='utf-8') as f:
                pass
        except FileNotFoundError:
            with open(self.global_log_file, 'w', encoding='utf-8') as f:
                f.write("# AI Data Scientist - Global Log\n\n")
                f.write("This log contains all interactions across all sessions.\n\n")
                f.write("---\n\n")
    
    def log_text_qa(self, user_question: str, llm_response: str):
        """Log a text-based Q&A interaction."""
        self.interaction_count += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        log_entry = f"""## Interaction #{self.interaction_count} - Text Q&A
**Timestamp:** {timestamp}  
**Type:** Text Question & Answer

### User Question:
{user_question}

### AI Response:
{llm_response}

---

"""
        self._append_to_logs(log_entry)
    
    def log_visualization(self, user_question: str, generated_code: str, 
                         explanation: str, success: bool, figures: list = None, error: str = ""):
        """Log a visualization generation interaction with embedded images."""
        self.interaction_count += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        status_emoji = "✅" if success else "❌"
        
        log_entry = f"""## Interaction #{self.interaction_count} - Visualization {status_emoji}
**Timestamp:** {timestamp}  
**Type:** Data Visualization  
**Status:** {"Success" if success else "Failed"}

### User Request:
{user_question}

### Generated Python Code:
```python
{generated_code}
```

### AI Explanation:
{explanation}
"""
        
        # Embed figures as base64 images if successful
        if success and figures:
            log_entry += "\n### Generated Visualizations:\n\n"
            for i, fig in enumerate(figures, 1):
                base64_img = self._fig_to_base64(fig)
                log_entry += f"**Figure {i}:**\n\n"
                log_entry += f"![Visualization {i}](data:image/png;base64,{base64_img})\n\n"
        
        if not success:
            log_entry += f"""
### Error:
```
{error}
```
"""
        
        log_entry += "\n---\n\n"
        self._append_to_logs(log_entry)
    
    def log_summary_generation(self, summary_type: str, llm_response: str):
        """Log initial data summary generation."""
        self.interaction_count += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        log_entry = f"""## Interaction #{self.interaction_count} - {summary_type}
**Timestamp:** {timestamp}  
**Type:** Data Summary Generation

### AI Summary:
{llm_response}

---

"""
        self._append_to_logs(log_entry)
    
    def _fig_to_base64(self, fig) -> str:
        """Convert matplotlib figure to base64 string."""
        buffer = io.BytesIO()
        fig.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        buffer.close()
        return img_base64
    
    def _append_to_logs(self, entry: str):
        """Append entry to both session-specific and global log files."""
        # Write to session-specific log
        with open(self.session_log_file, 'a', encoding='utf-8') as f:
            f.write(entry)
        
        # Write to global log with session identifier
        global_entry = entry
        if self.interaction_count == 1 and self.session_timestamp:
            # Add session header to global log for first interaction
            global_entry = f"\n## === New Session: {self.session_timestamp} ===\n\n" + entry
        
        with open(self.global_log_file, 'a', encoding='utf-8') as f:
            f.write(global_entry)


# Legacy class name for backward compatibility
CodeExecutionLogger = InteractionLogger


def execute_analysis_code(code: str, df: pd.DataFrame) -> tuple:
    """
    Execute Python code for data analysis and return text results.
    
    Unlike execute_visualization_code, this returns the value of the 'result' variable
    rather than matplotlib figures.
    
    Args:
        code: Python code string to execute (should store result in 'result' variable)
        df: DataFrame to make available to the code
    
    Returns:
        tuple: (success: bool, result_str: str, error_message: str)
    """
    # Validate code quality - detect suspicious patterns
    suspicious_patterns = [
        ("result = {", "hardcoded dictionary without calculations"),
        ("result = [", "hardcoded list without calculations"),
        ("result = '", "hardcoded string without calculations"),
        ('result = "', "hardcoded string without calculations"),
    ]
    
    code_lower = code.lower().strip()
    for pattern, issue in suspicious_patterns:
        if pattern in code_lower:
            # Check if there's actual dataframe usage before the result assignment
            lines_before_result = code_lower.split(pattern)[0]
            if 'df[' not in lines_before_result and 'df.' not in lines_before_result:
                warning_msg = f"Warning: Code may contain {issue}. Ensure calculations use 'df'."
                # Don't fail, but flag it
                print(f"[CODE VALIDATION] {warning_msg}")
    
    # Prepare safe execution environment
    safe_globals = {
        'pd': pd,
        'np': np,
        'df': df,
    }
    
    try:
        # Execute the code
        exec(code, safe_globals)
        
        # Get the result variable
        if 'result' in safe_globals:
            result = safe_globals['result']
            # Convert result to string representation
            result_str = str(result)
            return True, result_str, ""
        else:
            return False, "", "Code did not produce a 'result' variable"
    
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        return False, "", error_msg


def execute_visualization_code(code: str, df: pd.DataFrame, logger: InteractionLogger = None):
    """
    Execute Python code to generate visualizations.
    
    Args:
        code: Python code string to execute
        df: DataFrame to make available to the code
        logger: Optional logger to record execution (not used here - logging done in app.py)
    
    Returns:
        tuple: (success: bool, figures: list, error_message: str)
    """
    # Prepare safe execution environment
    # Only allow access to safe libraries and the dataframe
    safe_globals = {
        'pd': pd,
        'np': np,
        'plt': plt,
        'df': df,  # Make the dataframe available as 'df'
    }
    
    # Close any existing figures to avoid memory leaks
    plt.close('all')
    
    try:
        # Execute the code
        exec(code, safe_globals)
        
        # Capture all generated figures
        figures = [plt.figure(n) for n in plt.get_fignums()]
        
        return True, figures, ""
    
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        return False, [], error_msg


def get_log_content(session_timestamp=None) -> str:
    """Read and return the contents of the session-specific interaction log."""
    logs_dir = "logs"
    
    if session_timestamp:
        log_file = os.path.join(logs_dir, f"log_{session_timestamp}.md")
    else:
        log_file = os.path.join(logs_dir, "log_global.md")
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "# No Interactions Logged Yet\n\nUpload a dataset and start asking questions to see logs here."


def convert_log_to_pdf(session_timestamp=None) -> bytes:
    """
    Convert the markdown interaction log to PDF.
    
    Args:
        session_timestamp: Optional session timestamp to identify which log to convert
    
    Returns:
        bytes: PDF file content
    """
    import markdown
    from xhtml2pdf import pisa
    
    # Read markdown content for this session
    md_content = get_log_content(session_timestamp)
    
    # Convert markdown to HTML
    html_content = markdown.markdown(md_content, extensions=['tables', 'fenced_code'])
    
    # Add CSS styling for better PDF appearance
    styled_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 40px;
                line-height: 1.6;
            }}
            h1 {{
                color: #2c3e50;
                border-bottom: 3px solid #3498db;
                padding-bottom: 10px;
            }}
            h2 {{
                color: #34495e;
                border-bottom: 2px solid #95a5a6;
                padding-bottom: 5px;
                margin-top: 30px;
            }}
            h3 {{
                color: #7f8c8d;
                margin-top: 20px;
            }}
            code {{
                background-color: #f4f4f4;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: 'Courier New', monospace;
            }}
            pre {{
                background-color: #f4f4f4;
                padding: 15px;
                border-radius: 5px;
                overflow-x: auto;
                border-left: 4px solid #3498db;
            }}
            pre code {{
                background-color: transparent;
                padding: 0;
            }}
            strong {{
                color: #2c3e50;
            }}
            hr {{
                border: none;
                border-top: 2px solid #ecf0f1;
                margin: 30px 0;
            }}
            img {{
                max-width: 100%;
                height: auto;
                margin: 20px 0;
                border: 1px solid #ddd;
                border-radius: 5px;
            }}
        </style>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """
    
    # Convert HTML to PDF
    pdf_buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(styled_html.encode('utf-8'), dest=pdf_buffer)
    
    if pisa_status.err:
        raise Exception("Error converting to PDF")
    
    pdf_buffer.seek(0)
    return pdf_buffer.getvalue()
