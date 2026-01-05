"""
Core Test Execution Logic for Headless Testing

This module provides the core functionality for running the LangGraph agent
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
from langgraph_agent import agent_app
from data_analyzer import generate_data_summary
from environment import print_environment_info

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
    Execute LangGraph agent on a single question and capture all node outputs.
    
    This function reuses the existing agent_app from langgraph_agent.py.
    It mirrors the execution logic from app.py but captures detailed state.
    
    Args:
        question: The user question to process
        datasets: Dictionary of loaded datasets
        messages: Optional chat history (for context)
        
    Returns:
        Dictionary containing:
        - final_output: The agent's final output
        - node_states: Dict of each node's output state
        - execution_time: Total execution time in seconds
        - success: Boolean indicating if execution completed
        - error: Error message if execution failed
    """
    if messages is None:
        messages = []
    
    # Build combined summary (same as app.py)
    combined_summary = build_combined_summary(datasets)
    
    # Build initial state - mirrors app.py lines 523-553
    initial_state = {
        "question": question,
        "datasets": datasets,
        "data_summary": combined_summary,
        "messages": messages,
        # Node 0
        "needs_data_work": True,
        "question_reasoning": "",
        # Node 1B
        "requirements": None,
        # Node 2
        "data_profile": None,
        # Node 3
        "alignment_check": None,
        "alignment_iterations": 0,
        # Node 4
        "code": None,
        "execution_result": None,
        "execution_success": False,
        "error": None,
        "code_attempts": 0,
        "failed_attempts": [],
        # Node 5
        "evaluation": None,
        # Node 5a
        "remediation_plan": None,
        "total_remediations": 0,
        # Node 6
        "explanation": "",
        "final_output": {}
    }
    
    # Track execution
    start_time = datetime.now()
    node_states = {}
    final_state = None
    last_state = None
    error_message = None
    
    try:
        # Stream through the graph (same as app.py)
        for event in agent_app.stream(initial_state):
            for node_name, node_state in event.items():
                last_state = node_state
                node_states[node_name] = {
                    'timestamp': datetime.now().isoformat(),
                    'state': _extract_node_output(node_name, node_state)
                }
                logger.debug(f"Node completed: {node_name}")
                
                # Track final state
                if node_name in ["node_1a_explain", "node_6_explain"]:
                    final_state = node_state
        
        # Use last state if no explain node was reached
        if final_state is None:
            final_state = last_state
            
    except Exception as e:
        import traceback
        error_message = str(e)
        stack_trace = traceback.format_exc()
        logger.error(f"Agent execution failed: {error_message}")
        logger.error(f"Stack trace:\n{stack_trace}")
        
        # Store detailed error info in node_states for logging
        node_states['ERROR'] = {
            'timestamp': datetime.now().isoformat(),
            'state': {
                'error_type': type(e).__name__,
                'error_message': error_message,
                'stack_trace': stack_trace,
                'last_successful_node': list(node_states.keys())[-1] if node_states else 'None'
            }
        }
    
    end_time = datetime.now()
    execution_time = (end_time - start_time).total_seconds()
    
    # Safely extract final output even if final_state is None
    final_output = {}
    if final_state is not None:
        final_output = final_state.get('final_output', {})
    elif last_state is not None:
        # Try to extract from last state if available
        final_output = last_state.get('final_output', {})
    
    return {
        'final_output': final_output,
        'node_states': node_states,
        'execution_time': execution_time,
        'success': error_message is None and final_state is not None,
        'error': error_message,
        'final_state_was_none': final_state is None
    }


def _extract_node_output(node_name: str, state: Dict) -> Dict:
    """
    Extract relevant output from a node's state for logging.
    
    This extracts only the fields that changed/matter for each node,
    making logs more readable.
    """
    extractors = {
        'node_0_understand': lambda s: {
            'needs_data_work': s.get('needs_data_work'),
            'question_reasoning': s.get('question_reasoning')
        },
        'node_1a_explain': lambda s: {
            'explanation': s.get('explanation', '')[:500] + '...' if len(s.get('explanation', '')) > 500 else s.get('explanation', ''),
            'has_final_output': bool(s.get('final_output'))
        },
        'node_1b_requirements': lambda s: {
            'requirements': s.get('requirements')
        },
        'node_2_profile': lambda s: {
            'data_profile': s.get('data_profile')
        },
        'node_3_alignment': lambda s: {
            'alignment_check': s.get('alignment_check'),
            'alignment_iterations': s.get('alignment_iterations')
        },
        'node_4_code': lambda s: {
            'code': s.get('code'),
            'execution_success': s.get('execution_success'),
            'error': s.get('error'),
            'code_attempts': s.get('code_attempts'),
            'execution_result': s.get('execution_result'),  # Include full execution_result with figures
            'execution_result_type': s.get('execution_result', {}).get('type') if s.get('execution_result') else None
        },
        'node_5_evaluate': lambda s: {
            'evaluation': s.get('evaluation')
        },
        'node_5a_remediation': lambda s: {
            'remediation_plan': s.get('remediation_plan'),
            'total_remediations': s.get('total_remediations')
        },
        'node_6_explain': lambda s: {
            'explanation': s.get('explanation', '')[:500] + '...' if len(s.get('explanation', '')) > 500 else s.get('explanation', ''),
            'has_final_output': bool(s.get('final_output'))
        }
    }
    
    extractor = extractors.get(node_name, lambda s: {'raw_keys': list(s.keys())})
    return extractor(state)


# =============================================================================
# LOG FORMATTING
# =============================================================================

def _fig_to_base64(fig) -> str:
    """Convert matplotlib or Plotly figure to base64 string for embedding in markdown."""
    buffer = io.BytesIO()
    
    if hasattr(fig, 'write_image'):
        # Plotly figure - convert to static image
        try:
            fig.write_image(buffer, format='png', width=800, height=600)
            buffer.seek(0)
            img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
            buffer.close()
            print(f"[SUCCESS] Converted Plotly figure to base64 ({len(img_base64)} chars)")
            return img_base64
        except Exception as e:
            print(f"[WARNING] Failed to convert Plotly figure: {str(e)}")
            print(f"[WARNING] Install kaleido: pip install kaleido")
            buffer.close()
            return ""
    else:
        # Matplotlib figure
        try:
            fig.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
            buffer.seek(0)
            img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
            buffer.close()
            print(f"[SUCCESS] Converted Matplotlib figure to base64 ({len(img_base64)} chars)")
            return img_base64
        except Exception as e:
            print(f"[WARNING] Failed to convert Matplotlib figure: {str(e)}")
            buffer.close()
            return ""


def format_test_results(
    scenario: Dict[str, Any], 
    results: List[Dict[str, Any]],
    total_time: float
) -> str:
    """
    Format execution results as a detailed markdown log.
    
    Args:
        scenario: The test scenario configuration
        results: List of results for each question
        total_time: Total execution time for all questions
        
    Returns:
        Formatted markdown string
    """
    lines = []
    
    # Header
    lines.append(f"# Test Run: {scenario['name']}")
    lines.append(f"**Timestamp:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Total Duration:** {total_time:.1f} seconds")
    
    # Count successes
    successes = sum(1 for r in results if r.get('success', False))
    failures = len(results) - successes
    if failures == 0:
        status = "[OK] All questions completed"
    else:
        status = f"[FAIL] {successes}/{len(results)} questions completed, {failures} failed"
    lines.append(f"**Status:** {status}")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # Scenario details
    lines.append("## Scenario Details")
    lines.append(f"- **Name:** {scenario['name']}")
    if scenario.get('description'):
        lines.append(f"- **Description:** {scenario['description']}")
    dataset_names = [d['id'] for d in scenario['datasets']]
    lines.append(f"- **Datasets:** {', '.join(dataset_names)}")
    lines.append(f"- **Questions:** {len(scenario['questions'])}")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # Results for each question
    for i, (question, result) in enumerate(zip(scenario['questions'], results), 1):
        lines.append(f"## Question {i}: \"{question}\"")
        lines.append("")
        
        if not result['success']:
            lines.append(f"[FAIL] **FAILED:** {result.get('error', 'Unknown error')}")
            lines.append("")
            
            # Show error details if available in node_states
            if 'ERROR' in result.get('node_states', {}):
                error_node = result['node_states']['ERROR']
                error_state = error_node.get('state', {})
                lines.append("### Error Details")
                lines.append(f"- **Error Type:** {error_state.get('error_type', 'Unknown')}")
                lines.append(f"- **Error Message:** {error_state.get('error_message', 'No message')}")
                if error_state.get('last_successful_node'):
                    lines.append(f"- **Last Successful Node:** {error_state.get('last_successful_node')}")
                if error_state.get('stack_trace'):
                    lines.append("")
                    lines.append("**Stack Trace:**")
                    lines.append("```")
                    lines.append(error_state['stack_trace'])
                    lines.append("```")
                lines.append("")
            
            # Show partial node execution if any nodes completed before error
            partial_nodes = {k: v for k, v in result.get('node_states', {}).items() if k != 'ERROR'}
            if partial_nodes:
                lines.append("### Partial Execution (Before Error)")
                lines.append("")
                for node_name, node_data in partial_nodes.items():
                    node_output = node_data['state']
                    lines.append(f"#### {_format_node_name(node_name)}")
                    lines.append(f"[OK] Completed")
                    lines.append("")
                    lines.extend(_format_node_output(node_name, node_output))
                    lines.append("")
            
            lines.append("---")
            lines.append("")
            continue
        
        # Node-by-node breakdown
        for node_name, node_data in result['node_states'].items():
            node_output = node_data['state']
            lines.append(f"### {_format_node_name(node_name)}")
            lines.append(f"[OK] Completed")
            lines.append("")
            
            # Format node-specific output
            lines.extend(_format_node_output(node_name, node_output))
            lines.append("")
        
        # Final output summary
        final_output = result['final_output']
        if final_output:
            lines.append("### Final Output Summary")
            lines.append(f"- **Output Type:** {final_output.get('output_type', 'N/A')}")
            if final_output.get('code'):
                lines.append("")
                lines.append("**Generated Code:**")
                lines.append("```python")
                lines.append(final_output['code'])
                lines.append("```")
            if final_output.get('explanation'):
                lines.append("")
                lines.append("**Explanation:**")
                lines.append(final_output['explanation'][:1000])
                if len(final_output.get('explanation', '')) > 1000:
                    lines.append("... (truncated)")
            lines.append("")
        
        lines.append(f"**Execution Time:** {result['execution_time']:.1f}s")
        lines.append("")
        lines.append("---")
        lines.append("")
    
    # Summary
    lines.append("## Summary")
    lines.append(f"- **Questions Completed:** {successes}/{len(results)}")
    lines.append(f"- **Total Execution Time:** {total_time:.1f} seconds")
    if successes == len(results):
        lines.append("- **Result:** [OK] All tests passed")
    else:
        lines.append("- **Result:** [WARN] Some tests failed - review logs above")
    
    return "\n".join(lines)


def _format_node_name(node_name: str) -> str:
    """Convert node name to human-readable format."""
    name_map = {
        'node_0_understand': 'Node 0: Understand Question',
        'node_1a_explain': 'Node 1A: Explain (Conceptual)',
        'node_1b_requirements': 'Node 1B: Formulate Requirements',
        'node_2_profile': 'Node 2: Profile Data',
        'node_3_alignment': 'Node 3: Alignment Check',
        'node_4_code': 'Node 4: Generate & Execute Code',
        'node_5_evaluate': 'Node 5: Evaluate Results',
        'node_5a_remediation': 'Node 5A: Remediation Planning',
        'node_6_explain': 'Node 6: Explain Results',
        'ERROR': 'ERROR: Execution Failed'
    }
    return name_map.get(node_name, node_name)


def _format_node_output(node_name: str, output: Dict) -> List[str]:
    """Format node output as markdown list items."""
    lines = []
    
    if node_name == 'ERROR':
        lines.append(f"- **error_type:** {output.get('error_type', 'Unknown')}")
        lines.append(f"- **error_message:** {output.get('error_message', 'No message')}")
        if output.get('last_successful_node'):
            lines.append(f"- **last_successful_node:** {output.get('last_successful_node')}")
        if output.get('question_number'):
            lines.append(f"- **question_number:** {output.get('question_number')}")
        if output.get('stack_trace'):
            lines.append("")
            lines.append("**Stack Trace:**")
            lines.append("```")
            lines.append(output['stack_trace'][:2000])  # Limit stack trace length
            if len(output['stack_trace']) > 2000:
                lines.append("... (truncated)")
            lines.append("```")
    
    elif node_name == 'node_0_understand':
        lines.append(f"- **needs_data_work:** {output.get('needs_data_work')}")
        lines.append(f"- **reasoning:** {output.get('question_reasoning', 'N/A')}")
        
    elif node_name == 'node_1b_requirements':
        req = output.get('requirements', {})
        if req:
            lines.append(f"- **analysis_type:** {req.get('analysis_type', 'N/A')}")
            lines.append(f"- **variables_needed:** {req.get('variables_needed', [])}")
            lines.append(f"- **success_criteria:** {req.get('success_criteria', 'N/A')}")
            
    elif node_name == 'node_2_profile':
        profile = output.get('data_profile', {})
        if profile:
            lines.append(f"- **available_columns:** {profile.get('available_columns', [])}")
            lines.append(f"- **missing_columns:** {profile.get('missing_columns', [])}")
            lines.append(f"- **is_suitable:** {profile.get('is_suitable', 'N/A')}")
            if profile.get('reasoning'):
                lines.append(f"- **reasoning:** {profile.get('reasoning')}")
                
    elif node_name == 'node_3_alignment':
        alignment = output.get('alignment_check', {})
        if alignment:
            lines.append(f"- **aligned:** {alignment.get('aligned')}")
            lines.append(f"- **recommendation:** {alignment.get('recommendation', 'N/A')}")
            if alignment.get('gaps'):
                lines.append(f"- **gaps:** {alignment.get('gaps')}")
                
    elif node_name == 'node_4_code':
        lines.append(f"- **execution_success:** {output.get('execution_success')}")
        lines.append(f"- **code_attempts:** {output.get('code_attempts')}")
        if output.get('error'):
            lines.append(f"- **error:** {output.get('error')}")
        if output.get('code'):
            lines.append("")
            lines.append("**Code:**")
            lines.append("```python")
            lines.append(output['code'])
            lines.append("```")
        
        # Add visualizations if present
        execution_result = output.get('execution_result', {})
        if execution_result and execution_result.get('type') == 'visualization' and execution_result.get('figures'):
            lines.append("")
            lines.append("**Visualizations:**")
            lines.append("")
            figures = execution_result['figures']
            print(f"[DEBUG] Found {len(figures)} figures in execution_result")
            for i, fig in enumerate(figures, 1):
                print(f"[DEBUG] Processing figure {i}: {type(fig).__name__}")
                base64_img = _fig_to_base64(fig)
                if base64_img:
                    lines.append(f"![Visualization {i}](data:image/png;base64,{base64_img})")
                    lines.append("")
                    print(f"[SUCCESS] Embedded visualization {i} in log")
                else:
                    lines.append(f"*Visualization {i}: Unable to embed (conversion failed)*")
                    lines.append("")
                    print(f"[ERROR] Failed to embed visualization {i}")
            
    elif node_name == 'node_5_evaluate':
        eval_result = output.get('evaluation')
        if eval_result:
            if isinstance(eval_result, dict):
                lines.append(f"- **is_valid:** {eval_result.get('is_valid', 'N/A')}")
                if eval_result.get('issues'):
                    lines.append(f"- **issues:** {eval_result.get('issues')}")
            else:
                lines.append(f"- **evaluation:** {str(eval_result)[:200]}")
                
    elif node_name in ['node_1a_explain', 'node_6_explain']:
        if output.get('explanation'):
            lines.append(f"- **explanation:** {output['explanation'][:300]}...")
            
    else:
        # Generic fallback
        for key, value in output.items():
            lines.append(f"- **{key}:** {value}")
    
    return lines


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def run_scenario(scenario_path: str, output_dir: str = "logs/cli") -> str:
    """
    Run a complete test scenario and save results.
    
    This is the main entry point for running a test scenario.
    CLI test results are saved to logs/cli/ directory.
    
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
    
    try:
        # Load scenario
        scenario = load_scenario(scenario_path)
        
        # Initialize datasets
        logger.info("Loading datasets...")
        datasets = initialize_datasets(scenario['datasets'])
        
        # Run each question
        messages = []  # Accumulate messages for context
        total_start = datetime.now()
        
        for i, question in enumerate(scenario['questions'], 1):
            logger.info(f"Running question {i}/{len(scenario['questions'])}: {question[:50]}...")
            
            try:
                result = run_agent_on_question(question, datasets, messages)
                results.append(result)
                
                # Add to message history for context in subsequent questions
                messages.append({"role": "user", "content": question})
                if result['final_output'].get('explanation'):
                    messages.append({
                        "role": "assistant", 
                        "content": result['final_output']['explanation']
                    })
            except Exception as e:
                # Capture question-level errors
                logger.error(f"Question {i} failed: {str(e)}")
                logger.error(traceback.format_exc())
                results.append({
                    'final_output': {},
                    'node_states': {
                        'ERROR': {
                            'timestamp': datetime.now().isoformat(),
                            'state': {
                                'error_type': type(e).__name__,
                                'error_message': str(e),
                                'stack_trace': traceback.format_exc(),
                                'question_number': i,
                                'question': question
                            }
                        }
                    },
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
    
    # ALWAYS save results, even on failure
    try:
        # Format results (even if partial/failed)
        log_content = format_test_results(scenario, results, total_time)
        
        # Add critical error section if present
        if critical_error:
            log_content += "\n\n---\n\n"
            log_content += "## CRITICAL ERROR\n\n"
            log_content += f"**Error Type:** {type(critical_error).__name__}\n\n"
            log_content += f"**Error Message:** {str(critical_error)}\n\n"
            log_content += "**Stack Trace:**\n```\n"
            log_content += traceback.format_exc()
            log_content += "\n```\n"
        
        # Save results
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        scenario_name = os.path.basename(scenario_path).replace('.json', '')
        output_path = os.path.join(output_dir, f"{timestamp}_{scenario_name}.md")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(log_content)
        
        logger.info(f"Results saved to: {output_path}")
        
        return output_path
        
    except Exception as e:
        # Last resort: save raw error to file
        logger.error(f"Failed to save formatted results: {str(e)}")
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        scenario_name = os.path.basename(scenario_path).replace('.json', '')
        error_path = os.path.join(output_dir, f"{timestamp}_{scenario_name}_ERROR.txt")
        
        with open(error_path, 'w', encoding='utf-8') as f:
            f.write(f"CRITICAL FAILURE IN TEST SCENARIO\n")
            f.write(f"Scenario: {scenario_path}\n")
            f.write(f"Timestamp: {timestamp}\n\n")
            f.write(f"Error during result formatting: {str(e)}\n\n")
            f.write(traceback.format_exc())
            if critical_error:
                f.write(f"\n\nOriginal scenario error: {str(critical_error)}\n")
        
        logger.error(f"Raw error saved to: {error_path}")
        return error_path
