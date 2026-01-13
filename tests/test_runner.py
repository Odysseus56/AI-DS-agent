"""
Core Test Execution Logic for Headless Testing

This module provides the core functionality for running the ReAct agent
in headless mode. It reuses existing application logic - no duplication.

Key Principle: Import and call existing functions, don't copy them.
"""

import json
import os
import sys
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging
import io
import base64

# Add parent directory to path to import application modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set environment to local mode for CLI testing (before importing other modules)
os.environ['ENVIRONMENT_MODE'] = 'local'
print("=" * 60)
print("CLI Test Runner - Environment Configuration")
print("=" * 60)
print(f"ENVIRONMENT_MODE set to: {os.environ.get('ENVIRONMENT_MODE')}")

# Reuse existing application modules
from react_agent import process_question_v2, ExecutionLog
from data_analyzer import generate_data_summary
from environment import print_environment_info
from dual_logger import DualLogger

# Print environment info for debugging
print_environment_info()
print("=" * 60)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# SCENARIO LOADING
# =============================================================================

def load_scenario(scenario_path: str) -> Dict[str, Any]:
    """
    Load and validate a test scenario from a JSON file.
    
    Args:
        scenario_path: Path to the scenario JSON file
        
    Returns:
        Dictionary containing scenario configuration
        
    Raises:
        FileNotFoundError: If scenario file doesn't exist
        ValueError: If scenario JSON is invalid or missing required fields
    """
    if not os.path.exists(scenario_path):
        raise FileNotFoundError(f"Scenario file not found: {scenario_path}")
    
    try:
        with open(scenario_path, 'r', encoding='utf-8') as f:
            scenario = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in scenario file: {e}")
    
    # Validate required fields
    required_fields = ['name', 'datasets', 'questions']
    for field in required_fields:
        if field not in scenario:
            raise ValueError(f"Missing required field in scenario: {field}")
    
    # Validate datasets have required structure
    for i, ds in enumerate(scenario['datasets']):
        if 'path' not in ds:
            raise ValueError(f"Dataset {i} missing 'path' field")
        if 'id' not in ds:
            raise ValueError(f"Dataset {i} missing 'id' field")
    
    # Validate questions is non-empty
    if not scenario['questions']:
        raise ValueError("Scenario must have at least one question")
    
    logger.info(f"Loaded scenario: {scenario['name']}")
    return scenario


def list_available_scenarios(scenarios_dir: str = None) -> List[str]:
    """
    List all available test scenarios in the scenarios directory.
    
    Args:
        scenarios_dir: Path to the scenarios directory (default: tests/test_scenarios)
        
    Returns:
        List of scenario names (without .json extension)
    """
    # Default to test_scenarios in the same directory as this script
    if scenarios_dir is None:
        scenarios_dir = os.path.join(os.path.dirname(__file__), 'test_scenarios')
    
    if not os.path.exists(scenarios_dir):
        return []
    
    scenarios = []
    for filename in os.listdir(scenarios_dir):
        if filename.endswith('.json'):
            scenarios.append(filename.replace('.json', ''))
    
    return sorted(scenarios)


# =============================================================================
# DATASET INITIALIZATION
# =============================================================================

def initialize_datasets(dataset_configs: List[Dict]) -> Dict[str, Dict]:
    """
    Load CSV files into the same format as app.py uses.
    
    This function replicates the dataset structure from app.py to ensure
    compatibility. Each dataset is stored with its DataFrame and metadata.
    
    Args:
        dataset_configs: List of dicts with 'path' and 'id' keys
        
    Returns:
        Dictionary of datasets in app.py format
    """
    datasets = {}
    
    # Get the project root directory (parent of tests/)
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    
    for config in dataset_configs:
        dataset_path = config['path']
        dataset_id = config['id']
        
        # If path is relative, make it relative to project root
        if not os.path.isabs(dataset_path):
            dataset_path = os.path.join(project_root, dataset_path)
        
        if not os.path.exists(dataset_path):
            raise FileNotFoundError(f"Dataset file not found: {dataset_path}")
        
        logger.info(f"Loading dataset: {dataset_id} from {dataset_path}")
        
        try:
            # Load CSV with same parameters as app.py
            df = pd.read_csv(dataset_path, nrows=1_000_000)
            
            if len(df) == 1_000_000:
                logger.warning(f"Dataset {dataset_id} truncated to 1 million rows")
                
        except Exception as e:
            raise ValueError(f"Error reading CSV file {dataset_path}: {e}")
        
        # Generate data summary using existing function (REUSE, not duplicate!)
        data_summary = generate_data_summary(df)
        
        # Store in same format as app.py
        datasets[dataset_id] = {
            'name': os.path.basename(dataset_path),
            'df': df,
            'data_summary': data_summary,
            'uploaded_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        logger.info(f"Loaded {dataset_id}: {df.shape[0]} rows, {df.shape[1]} columns")
    
    return datasets


def build_combined_summary(datasets: Dict[str, Dict]) -> str:
    """
    Build combined data summary for all datasets.
    
    This replicates the logic from app.py lines 513-515.
    
    Args:
        datasets: Dictionary of loaded datasets
        
    Returns:
        Combined summary string for all datasets
    """
    combined_summary = "Available datasets:\n\n"
    for ds_id, ds_info in datasets.items():
        combined_summary += f"Dataset '{ds_id}' ({ds_info['name']}):\n"
        combined_summary += ds_info['data_summary']
        combined_summary += "\n\n"
    
    return combined_summary


# =============================================================================
# AGENT EXECUTION
# =============================================================================

def run_agent_on_question(
    question: str, 
    datasets: Dict[str, Dict],
    messages: Optional[List] = None
) -> Dict[str, Any]:
    """
    Execute ReAct agent on a single question and capture execution details.
    
    This function uses the V2 ReAct agent from react_agent.py.
    
    Args:
        question: The user question to process
        datasets: Dictionary of loaded datasets
        messages: Optional chat history (for context)
        
    Returns:
        Dictionary containing:
        - final_output: The agent's final output
        - exec_log: ExecutionLog with iteration details
        - execution_time: Total execution time in seconds
        - success: Boolean indicating if execution completed
        - error: Error message if execution failed
    """
    if messages is None:
        messages = []
    
    # Track execution
    start_time = datetime.now()
    error_message = None
    result = None
    exec_log = None
    
    try:
        # Call V2 ReAct agent
        result = process_question_v2(question, datasets)
        exec_log = result.get('execution_log')  # Note: process_question_v2 returns 'execution_log' not 'exec_log'
        
    except Exception as e:
        import traceback
        error_message = str(e)
        stack_trace = traceback.format_exc()
        logger.error(f"Agent execution failed: {error_message}")
        logger.error(f"Stack trace:\n{stack_trace}")
    
    end_time = datetime.now()
    execution_time = (end_time - start_time).total_seconds()
    
    # Build final output from result
    final_output = {}
    if result:
        final_output = {
            'answer': result.get('answer', ''),
            'code': result.get('code', ''),
            'output_type': result.get('output_type', ''),
            'confidence': result.get('confidence', 0),
            'caveats': result.get('caveats', []),
            'reasoning_trace': result.get('reasoning_trace', [])
        }
    
    return {
        'final_output': final_output,
        'exec_log': exec_log,
        'execution_time': execution_time,
        'success': error_message is None and result is not None,
        'error': error_message
    }


def evaluate_agent_success(result: Dict) -> Dict:
    """
    Evaluate agent-level success metrics for a single question result.
    
    This checks whether the agent produced correct, valid results - NOT just
    whether the infrastructure ran without crashing.
    
    Returns:
        Dictionary with:
        - agent_success: bool - True if agent produced valid results
        - execution_success: bool - True if code executed without errors
        - confidence: float - Agent's confidence in the result
        - issues: list - List of issues found
    """
    issues = []
    
    # Check if infrastructure even succeeded
    if not result.get('success', False):
        return {
            'agent_success': False,
            'execution_success': False,
            'evaluation_valid': False,
            'output_type_correct': False,
            'confidence': 0.0,
            'issues': ['Infrastructure failure - agent did not complete']
        }
    
    final_output = result.get('final_output', {})
    exec_log = result.get('exec_log')
    
    # Check confidence from agent
    confidence = final_output.get('confidence', 0.0)
    
    # Check if we have an answer
    has_answer = bool(final_output.get('answer', ''))
    if not has_answer:
        issues.append("No answer produced")
    
    # Check output type
    output_type = final_output.get('output_type', '')
    if output_type == 'error':
        issues.append("Final output type is 'error'")
    
    # Check execution log for issues
    if exec_log:
        if exec_log.loop_detected:
            issues.append("Loop detected during execution")
        if exec_log.max_iterations_reached:
            issues.append("Max iterations reached")
    
    # Check confidence threshold
    execution_success = output_type != 'error' and has_answer
    high_confidence = confidence >= 0.7
    
    if not high_confidence and execution_success:
        issues.append(f"Low confidence: {confidence:.0%}")
    
    # Agent success requires answer + reasonable confidence
    agent_success = execution_success and confidence >= 0.5
    
    # For backward compatibility with gauntlet metrics parsing
    evaluation_valid = confidence >= 0.5
    output_type_correct = output_type != 'error'
    
    return {
        'agent_success': agent_success,
        'execution_success': execution_success,
        'evaluation_valid': evaluation_valid,
        'output_type_correct': output_type_correct,
        'confidence': confidence,
        'issues': issues
    }


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def run_scenario(scenario_path: str, output_dir: str = "logs/cli") -> str:
    """
    Run a complete test scenario and save results.
    
    This is the main entry point for running a test scenario.
    Uses DualLogger for unified logging (same as Streamlit UI).
    
    Args:
        scenario_path: Path to the scenario JSON file
        output_dir: Directory to save results (default: logs/cli)
        
    Returns:
        Path to the saved results file
    """
    import traceback
    
    scenario = None
    results = []
    total_time = 0
    error_occurred = False
    critical_error = None
    
    # Create timestamp for this scenario run
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    scenario_name = os.path.basename(scenario_path).replace('.json', '')
    
    # Initialize DualLogger - uses same logging as Streamlit UI
    # This ensures identical log format across all modes
    # Pass output_dir to ensure logs go to the correct location (not default logs/cli)
    dual_logger = DualLogger(session_timestamp=f"{timestamp}_{scenario_name}", log_dir=output_dir)
    
    try:
        # Load scenario
        scenario = load_scenario(scenario_path)
        
        # Initialize datasets
        logger.info("Loading datasets...")
        datasets = initialize_datasets(scenario['datasets'])
        
        # Log scenario header
        _write_scenario_header(dual_logger, scenario)
        
        # Log dataset summaries (like Streamlit UI does on upload)
        for ds_config in scenario['datasets']:
            ds_id = ds_config['id']
            if ds_id in datasets:
                ds_info = datasets[ds_id]
                dual_logger.log_summary_generation(
                    summary_type=f"Dataset: {ds_id}",
                    llm_response=ds_info.get('data_summary', 'No summary available')
                )
        
        # Run each question
        messages = []  # Accumulate messages for context
        total_start = datetime.now()
        
        for i, question in enumerate(scenario['questions'], 1):
            logger.info(f"Running question {i}/{len(scenario['questions'])}: {question[:50]}...")
            
            try:
                result = run_agent_on_question(question, datasets, messages)
                results.append(result)
                
                # Use DualLogger to log the execution - SAME as Streamlit UI
                exec_log = result.get('exec_log')
                if exec_log:
                    dual_logger.log_react_execution(exec_log)
                
                # Add to message history for context in subsequent questions
                messages.append({"role": "user", "content": question})
                if result['final_output'].get('answer'):
                    messages.append({
                        "role": "assistant", 
                        "content": result['final_output']['answer']
                    })
            except Exception as e:
                # Capture question-level errors
                logger.error(f"Question {i} failed: {str(e)}")
                logger.error(traceback.format_exc())
                results.append({
                    'final_output': {},
                    'exec_log': None,
                    'execution_time': 0,
                    'success': False,
                    'error': str(e)
                })
                error_occurred = True
        
        total_time = (datetime.now() - total_start).total_seconds()
        
    except Exception as e:
        # Capture scenario-level critical errors
        critical_error = e
        error_occurred = True
        logger.error(f"Critical error in scenario execution: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Create minimal scenario info if loading failed
        if scenario is None:
            scenario = {
                'name': os.path.basename(scenario_path).replace('.json', ''),
                'description': 'Failed to load scenario',
                'datasets': [],
                'questions': []
            }
    
    # Write summary to the log file
    _write_scenario_summary(dual_logger, scenario, results, total_time, critical_error)
    
    # Return the log file path
    log_path = dual_logger.file_logger.session_log_file
    logger.info(f"Results saved to: {log_path}")
    
    return log_path


def _write_scenario_header(dual_logger: DualLogger, scenario: Dict[str, Any]) -> None:
    """Write scenario header to log file."""
    header = f"""# Test Scenario: {scenario['name']}

**Description:** {scenario.get('description', 'N/A')}
**Datasets:** {', '.join(d['id'] for d in scenario['datasets'])}
**Questions:** {len(scenario['questions'])}

---

"""
    with open(dual_logger.file_logger.session_log_file, 'a', encoding='utf-8') as f:
        f.write(header)


def _write_scenario_summary(dual_logger: DualLogger, scenario: Dict[str, Any], 
                           results: List[Dict], total_time: float, 
                           critical_error: Optional[Exception] = None) -> None:
    """Write scenario summary to log file."""
    # Calculate metrics
    agent_evaluations = [evaluate_agent_success(r) for r in results]
    infra_successes = sum(1 for r in results if r.get('success', False))
    agent_successes = sum(1 for e in agent_evaluations if e['agent_success'])
    
    summary = f"""
---

## Scenario Summary

- **Questions Completed:** {len(results)}
- **Total Execution Time:** {total_time:.1f} seconds
- **Infrastructure Success:** {infra_successes}/{len(results)} ({infra_successes/len(results)*100:.0f}% if results else 0)
- **Agent Success:** {agent_successes}/{len(results)} ({agent_successes/len(results)*100:.0f}% if results else 0)

"""
    
    # Add issues if any
    all_issues = []
    for i, (eval_result, question) in enumerate(zip(agent_evaluations, scenario.get('questions', [])), 1):
        if eval_result['issues']:
            for issue in eval_result['issues']:
                all_issues.append(f"Q{i}: {issue}")
    
    if all_issues:
        summary += "### Issues Detected\n"
        for issue in all_issues:
            summary += f"- {issue}\n"
        summary += "\n"
    
    # Add critical error if present
    if critical_error:
        import traceback
        summary += f"""
## CRITICAL ERROR

**Error Type:** {type(critical_error).__name__}
**Error Message:** {str(critical_error)}

**Stack Trace:**
```
{traceback.format_exc()}
```
"""
    
    with open(dual_logger.file_logger.session_log_file, 'a', encoding='utf-8') as f:
        f.write(summary)
