import matplotlib
matplotlib.use('Agg')  # Set backend before importing pyplot to prevent GUI windows
import matplotlib.pyplot as plt
plt.ioff()  # Turn off interactive mode to prevent new window pop-ups
import pandas as pd
import numpy as np
import io
import base64
import os
from datetime import datetime
import threading
from environment import should_save_visualizations

# Import plotly at module level
try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
    import plotly.io as pio
    
    # Disable automatic display in browser
    pio.renderers.default = "json"
    
    # Override show methods to prevent browser tabs
    def _no_show(*args, **kwargs):
        """Dummy show function that does nothing"""
        pass
    
    # Monkey patch show methods
    go.Figure.show = _no_show
    px.show = _no_show
    
    PLOTLY_AVAILABLE = True
except ImportError:
    go = None
    px = None
    make_subplots = None
    pio = None
    PLOTLY_AVAILABLE = False

# Import sklearn at module level
try:
    from sklearn.linear_model import LogisticRegression, LinearRegression
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.preprocessing import StandardScaler, LabelEncoder
    from sklearn.metrics import accuracy_score, mean_squared_error, r2_score, classification_report, confusion_matrix
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    from sklearn.neighbors import NearestNeighbors
    import sklearn
    SKLEARN_AVAILABLE = True
except ImportError:
    sklearn = None
    SKLEARN_AVAILABLE = False

# Import scipy at module level
try:
    import scipy
    from scipy import stats
    SCIPY_AVAILABLE = True
except ImportError:
    scipy = None
    stats = None
    SCIPY_AVAILABLE = False

# Import statsmodels at module level
try:
    import statsmodels.api as sm
    import statsmodels.formula.api as smf
    STATSMODELS_AVAILABLE = True
except ImportError:
    sm = None
    smf = None
    STATSMODELS_AVAILABLE = False

# Import seaborn at module level
try:
    import seaborn as sns
    SEABORN_AVAILABLE = True
except ImportError:
    sns = None
    SEABORN_AVAILABLE = False


class InteractionLogger:
    """
    Comprehensive logger for all user interactions with the AI assistant.
    Saves to markdown format for easy reading and navigation.
    Logs are saved to logs/local/ directory for Streamlit app usage.
    """
    
    def __init__(self, session_timestamp=None, log_dir="logs/local"):
        self.logs_dir = log_dir
        os.makedirs(self.logs_dir, exist_ok=True)
        
        if session_timestamp:
            self.session_log_file = os.path.join(self.logs_dir, f"log_{session_timestamp}.md")
        else:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
            self.session_log_file = os.path.join(self.logs_dir, f"log_{timestamp}.md")
        
        self.global_log_file = os.path.join(self.logs_dir, "log_global.md")
        self.interaction_count = 0
        self.session_timestamp = session_timestamp
        
        # Initialize session log file
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
        
        # Initialize global log file
        try:
            with open(self.global_log_file, 'r', encoding='utf-8') as f:
                pass
        except FileNotFoundError:
            with open(self.global_log_file, 'w', encoding='utf-8') as f:
                f.write("# AI Data Scientist - Global Log\n\n")
                f.write("This log contains all interactions across all sessions.\n\n")
                f.write("---\n\n")
    
    def log_text_qa(self, user_question: str, llm_response: str):
        """Log a simple text-based Q&A interaction."""
        self.interaction_count += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        log_entry = f"""## Interaction #{self.interaction_count} - Text Q&A
*{timestamp}*

**User Question:**
{user_question}

**AI Response:**
{llm_response}

---

"""
        self._append_to_logs(log_entry)
    
    def log_analysis_workflow(self, user_question: str, question_type: str, 
                             generated_code: str, execution_result: str, 
                             final_answer: str, success: bool, error: str = "",
                             execution_plan: dict = None, evaluation: str = None):
        """Log a detailed analysis workflow with all intermediate steps."""
        self.interaction_count += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        status_emoji = "✅" if success else "❌"
        
        log_entry = f"""## Interaction #{self.interaction_count} - Analysis {status_emoji}
*{timestamp} • {question_type}*

**User Question:**
{user_question}
"""
        
        # Add execution plan if provided
        if execution_plan:
            log_entry += f"""
**Execution Plan:**
- **Reasoning:** {execution_plan.get('reasoning', 'N/A')}
- **Needs Code:** {execution_plan.get('needs_code', False)}
- **Needs Evaluation:** {execution_plan.get('needs_evaluation', False)}
- **Needs Explanation:** {execution_plan.get('needs_explanation', False)}
"""
        
        log_entry += f"""
**Generated Code:**
```python
{generated_code}
```

**Execution Result:**
```
{execution_result}
```
"""
        
        if not success and error:
            log_entry += f"\n**Error:**\n```\n{error}\n```\n"
        
        # Add evaluation if provided
        if evaluation:
            log_entry += f"""
**Evaluation:**
{evaluation}
"""
        
        log_entry += f"""
**Final Answer:**
{final_answer}

---

"""
        self._append_to_logs(log_entry)
    
    def log_visualization_workflow(self, user_question: str, question_type: str,
                                   generated_code: str, explanation: str, 
                                   success: bool, figures: list = None, error: str = "",
                                   execution_plan: dict = None, evaluation: str = None):
        """Log a detailed visualization workflow with all intermediate steps."""
        self.interaction_count += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        status_emoji = "✅" if success else "❌"
        
        log_entry = f"""## Interaction #{self.interaction_count} - Visualization {status_emoji}
*{timestamp} • {question_type}*

**User Request:**
{user_question}
"""
        
        # Add execution plan if provided
        if execution_plan:
            log_entry += f"""
**Execution Plan:**
- **Reasoning:** {execution_plan.get('reasoning', 'N/A')}
- **Needs Code:** {execution_plan.get('needs_code', False)}
- **Needs Evaluation:** {execution_plan.get('needs_evaluation', False)}
- **Needs Explanation:** {execution_plan.get('needs_explanation', False)}
"""
        
        log_entry += f"""
**Generated Code:**
```python
{generated_code}
```
"""
        
        # Add evaluation if provided
        if evaluation:
            log_entry += f"""
**Evaluation:**
{evaluation}
"""
        
        log_entry += f"""
**Explanation:**
{explanation}
"""
        
        if success and figures:
            log_entry += "\n**Visualizations:**\n\n"
            # Only save visualizations in local environment (CLI/headless mode)
            # In Streamlit, visualizations are shown in UI and saving causes issues
            save_viz = should_save_visualizations()
            print(f"[DEBUG] Environment check: should_save_visualizations() = {save_viz}")
            print(f"[DEBUG] Number of figures to process: {len(figures)}")
            
            if save_viz:
                for i, fig in enumerate(figures, 1):
                    print(f"[DEBUG] Processing figure {i}/{len(figures)}: {type(fig).__name__}")
                    base64_img = self._fig_to_base64(fig)
                    if base64_img:  # Only add image if conversion succeeded
                        log_entry += f"![Visualization {i}](data:image/png;base64,{base64_img})\n\n"
                        print(f"[SUCCESS] Added visualization {i} to log")
                    else:
                        log_entry += f"*Visualization {i}: Unable to embed (conversion failed)*\n\n"
                        print(f"[ERROR] Failed to add visualization {i} to log")
            else:
                # Streamlit environment - just note that visualizations were generated
                log_entry += f"*{len(figures)} visualization(s) generated (displayed in UI, not saved to logs)*\n\n"
                print(f"[INFO] Streamlit mode: Not saving visualizations to logs")
        elif not success and error:
            log_entry += f"\n**Error:**\n```\n{error}\n```\n"
        
        log_entry += "\n---\n\n"
        self._append_to_logs(log_entry)
    
    def log_summary_generation(self, summary_type: str, llm_response: str):
        """Log initial data summary generation."""
        self.interaction_count += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        log_entry = f"""## Interaction #{self.interaction_count} - {summary_type}
*{timestamp}*

{llm_response}

---

"""
        self._append_to_logs(log_entry)
    
    def _fig_to_base64(self, fig) -> str:
        """Convert matplotlib or Plotly figure to base64 string."""
        buffer = io.BytesIO()
        
        if hasattr(fig, 'write_image'):
            # Plotly figure - convert to static image
            try:
                # Try to export as static image (requires kaleido)
                fig.write_image(buffer, format='png', width=800, height=600)
                buffer.seek(0)
                img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
                buffer.close()
                print(f"[SUCCESS] Converted Plotly figure to base64 ({len(img_base64)} chars)")
                return img_base64
            except Exception as e:
                # If kaleido not available or conversion fails, return empty
                # This happens in Streamlit Cloud or when kaleido is not installed
                print(f"[WARNING] Failed to convert Plotly figure to base64: {str(e)}")
                print(f"[WARNING] Install kaleido: pip install kaleido")
                buffer.close()
                return ""
        else:
            # Matplotlib figure
            fig.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
            buffer.seek(0)
            img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
            buffer.close()
            print(f"[SUCCESS] Converted Matplotlib figure to base64 ({len(img_base64)} chars)")
            return img_base64
    
    def _append_to_logs(self, entry: str):
        """Append entry to both session-specific and global log files."""
        with open(self.session_log_file, 'a', encoding='utf-8') as f:
            f.write(entry)
        
        global_entry = entry
        if self.interaction_count == 1 and self.session_timestamp:
            global_entry = f"\n## === New Session: {self.session_timestamp} ===\n\n" + entry
        
        with open(self.global_log_file, 'a', encoding='utf-8') as f:
            f.write(global_entry)


def run_with_timeout(func, timeout_seconds):
    """Run a function with a timeout (cross-platform using threading)."""
    result = {'success': False, 'value': None, 'error': None}
    
    def target():
        try:
            result['value'] = func()
            result['success'] = True
        except Exception as e:
            result['error'] = e
    
    thread = threading.Thread(target=target)
    thread.daemon = True
    thread.start()
    thread.join(timeout_seconds)
    
    if thread.is_alive():
        raise TimeoutError(f"Code execution exceeded {timeout_seconds} second timeout")
    
    if not result['success'] and result['error']:
        raise result['error']
    
    return result['value']


def execute_unified_code(code: str, datasets: dict) -> tuple:
    """
    Unified code executor for both visualization and analysis.
    Detects whether code generates a figure or a result and returns appropriately.
    
    Args:
        code: Python code string to execute
        datasets: Dict of datasets {dataset_id: {'df': DataFrame, 'name': str, ...}}
    
    Returns:
        tuple: (success: bool, output: dict, error_message: str)
        output dict contains:
            - 'type': 'visualization' or 'analysis'
            - 'figures': list of figures (if visualization)
            - 'result': result value (if analysis)
            - 'result_str': stringified result
    """
    # Build safe_globals with all available libraries (using module-level imports)
    safe_globals = {
        'pd': pd,
        'np': np,
        'plt': plt,
        'datasets': {ds_id: ds_info['df'] for ds_id, ds_info in datasets.items()},
    }
    
    # Add plotly if available
    if PLOTLY_AVAILABLE:
        safe_globals.update({
            'go': go,
            'px': px,
            'make_subplots': make_subplots,
        })
    
    # Add sklearn components if available
    if SKLEARN_AVAILABLE:
        safe_globals.update({
            'sklearn': sklearn,
            'LogisticRegression': LogisticRegression,
            'LinearRegression': LinearRegression,
            'RandomForestClassifier': RandomForestClassifier,
            'RandomForestRegressor': RandomForestRegressor,
            'train_test_split': train_test_split,
            'cross_val_score': cross_val_score,
            'StandardScaler': StandardScaler,
            'LabelEncoder': LabelEncoder,
            'accuracy_score': accuracy_score,
            'mean_squared_error': mean_squared_error,
            'r2_score': r2_score,
            'classification_report': classification_report,
            'confusion_matrix': confusion_matrix,
            'KMeans': KMeans,
            'PCA': PCA,
            'NearestNeighbors': NearestNeighbors,
        })
    
    # Add scipy if available
    if SCIPY_AVAILABLE:
        safe_globals.update({
            'scipy': scipy,
            'stats': stats,
        })
    
    # Add statsmodels if available
    if STATSMODELS_AVAILABLE:
        safe_globals.update({
            'sm': sm,
            'smf': smf,
        })
    
    # Add seaborn if available
    if SEABORN_AVAILABLE:
        safe_globals['sns'] = sns
    
    # For backward compatibility, if there's only one dataset, also provide it as 'df'
    if len(datasets) == 1:
        safe_globals['df'] = list(datasets.values())[0]['df']
    
    plt.close('all')
    
    def execute():
        exec(code, safe_globals)
        return safe_globals
    
    try:
        safe_globals = run_with_timeout(execute, 30)
        
        has_fig = 'fig' in safe_globals
        has_result = 'result' in safe_globals
        has_matplotlib = len(plt.get_fignums()) > 0
        
        if has_fig or has_matplotlib:
            # Visualization output
            figures = []
            
            matplotlib_figs = [plt.figure(n) for n in plt.get_fignums()]
            figures.extend(matplotlib_figs)
            
            if has_fig:
                plotly_fig = safe_globals['fig']
                if hasattr(plotly_fig, 'write_image'):
                    figures.append(plotly_fig)
            
            if 'figs' in safe_globals:
                plotly_figs = safe_globals['figs']
                if isinstance(plotly_figs, list):
                    for fig in plotly_figs:
                        if hasattr(fig, 'write_image'):
                            figures.append(fig)
            
            return True, {
                'type': 'visualization',
                'figures': figures,
                'result_str': f"Generated {len(figures)} visualization(s)"
            }, ""
        
        elif has_result:
            # Analysis output
            result = safe_globals['result']
            result_str = str(result)
            
            return True, {
                'type': 'analysis',
                'result': result,
                'result_str': result_str
            }, ""
        
        else:
            return False, {}, "Code did not produce a 'fig' or 'result' variable"
    
    except TimeoutError as e:
        error_msg = f"Execution timeout: {str(e)}"
        return False, {}, error_msg
    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        return False, {}, error_msg


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


def convert_log_to_pdf(session_timestamp: str = None) -> bytes:
    """
    Convert the markdown interaction log to PDF.
    
    NOTE: PDF conversion is disabled in cloud deployments due to system dependencies.
    This function will raise an ImportError when called in Streamlit Cloud.
    
    Args:
        session_timestamp: Optional session timestamp to identify which log to convert
    
    Returns:
        bytes: PDF file content
    """
    raise ImportError("PDF conversion is not available in cloud deployments. Please download the Markdown log instead.")
    
    md_content = get_log_content(session_timestamp)
    html_content = markdown.markdown(md_content, extensions=['tables', 'fenced_code'])
    
    # Post-process HTML to add width constraints to images
    import re
    html_content = re.sub(
        r'<img\s+([^>]*?)src="data:image',
        r'<img style="width: 500px; max-width: 100%;" \1src="data:image',
        html_content
    )
    
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
                max-width: 90%;
                max-height: 500px;
                height: auto;
                display: block;
                margin: 20px auto;
                page-break-inside: avoid;
            }}
        </style>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """
    
    pdf_buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(styled_html.encode('utf-8'), dest=pdf_buffer)
    
    if pisa_status.err:
        raise Exception("Error converting to PDF")
    
    pdf_buffer.seek(0)
    return pdf_buffer.getvalue()
