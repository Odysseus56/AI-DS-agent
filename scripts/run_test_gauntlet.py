#!/usr/bin/env python3
"""
Test Gauntlet Runner

Runs all test scenarios sequentially to stress-test the AI data scientist agent.
Each scenario runs independently with detailed logging.

Usage:
    python scripts/run_test_gauntlet.py
    python scripts/run_test_gauntlet.py --category A  # Run only Category A
    python scripts/run_test_gauntlet.py --scenario a1_hypothesis_testing  # Run single scenario
"""

import os
import sys
import json
import argparse
import time
from datetime import datetime
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count
import threading
import random

# Add parent directory to path to import test runner
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_runner import run_scenario, list_available_scenarios, evaluate_agent_success


class TeeLogger:
    """Captures console output and writes to both console and file."""
    
    def __init__(self, filepath, mode='w'):
        self.terminal = sys.stdout
        self.log_file = open(filepath, mode, encoding='utf-8')
        self.buffer = []
    
    def write(self, message):
        self.terminal.write(message)
        self.log_file.write(message)
        self.log_file.flush()  # Ensure immediate write
    
    def flush(self):
        self.terminal.flush()
        self.log_file.flush()
    
    def close(self):
        self.log_file.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def parse_agent_metrics_from_log(log_path: str) -> dict:
    """
    Parse agent quality metrics from a generated log file.
    
    Returns:
        Dictionary with agent metrics extracted from the log summary section.
    """
    metrics = {
        'agent_success': 0,
        'agent_total': 0,
        'exec_success': 0,
        'eval_valid': 0,
        'output_correct': 0,
        'issues': []
    }
    
    if not log_path or not os.path.exists(log_path):
        return metrics
    
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse Agent Success line: "- **Agent Success:** 2/3 (67%)"
        import re
        agent_match = re.search(r'\*\*Agent Success:\*\* (\d+)/(\d+)', content)
        if agent_match:
            metrics['agent_success'] = int(agent_match.group(1))
            metrics['agent_total'] = int(agent_match.group(2))
        
        # Parse sub-metrics
        exec_match = re.search(r'Code Execution Success: (\d+)/(\d+)', content)
        if exec_match:
            metrics['exec_success'] = int(exec_match.group(1))
        
        eval_match = re.search(r'Evaluation Valid: (\d+)/(\d+)', content)
        if eval_match:
            metrics['eval_valid'] = int(eval_match.group(1))
        
        output_match = re.search(r'Output Type Correct: (\d+)/(\d+)', content)
        if output_match:
            metrics['output_correct'] = int(output_match.group(1))
        
        # Parse issues section
        issues_section = re.search(r'### Issues Detected\n(.+?)(?=\n##|$)', content, re.DOTALL)
        if issues_section:
            issues_text = issues_section.group(1)
            metrics['issues'] = [line.strip('- ').strip() for line in issues_text.strip().split('\n') if line.strip().startswith('-')]
    
    except Exception as e:
        print(f"Warning: Could not parse metrics from {log_path}: {e}")
    
    return metrics


def get_all_scenarios():
    """Get all available scenarios with their metadata."""
    scenarios_dir = os.path.join(os.path.dirname(__file__), '..', 'tests', 'test_scenarios')
    scenarios = []
    
    for filename in sorted(os.listdir(scenarios_dir)):
        if filename.endswith('.json'):
            scenario_path = os.path.join(scenarios_dir, filename)
            try:
                with open(scenario_path, 'r') as f:
                    metadata = json.load(f)
                scenarios.append({
                    'filename': filename,
                    'path': scenario_path,
                    'name': metadata.get('name', filename.replace('.json', '')),
                    'category': metadata.get('metadata', {}).get('category', 'unknown'),
                    'difficulty': metadata.get('metadata', {}).get('difficulty', 'unknown'),
                    'num_questions': len(metadata.get('questions', [])),
                    'tags': metadata.get('metadata', {}).get('tags', [])
                })
            except Exception as e:
                print(f"Warning: Could not load {filename}: {e}")
    
    return scenarios


def group_scenarios_by_category(scenarios):
    """Group scenarios by their category."""
    categories = {}
    for scenario in scenarios:
        cat = scenario['category']
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(scenario)
    return categories


def print_summary(scenarios):
    """Print a summary of available scenarios."""
    categories = group_scenarios_by_category(scenarios)
    
    print("="*80)
    print("TEST GAUNTLET SUMMARY")
    print("="*80)
    print(f"Total scenarios: {len(scenarios)}")
    print(f"Categories: {len(categories)}")
    print()
    
    for cat_name, cat_scenarios in sorted(categories.items()):
        print(f"📂 {cat_name.upper()} ({len(cat_scenarios)} scenarios)")
        for scenario in cat_scenarios:
            difficulty_emoji = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}.get(scenario['difficulty'], "⚪")
            print(f"   {difficulty_emoji} {scenario['filename']} - {scenario['num_questions']} questions")
        print()
    
    print("="*80)


# Thread lock for synchronized printing
print_lock = threading.Lock()

def run_single_scenario(scenario, output_dir, show_progress=True):
    """Run a single scenario and return results."""
    if show_progress:
        with print_lock:
            print(f"\n{'='*60}")
            print(f"RUNNING: {scenario['name']}")
            print(f"File: {scenario['filename']}")
            print(f"Category: {scenario['category']} | Difficulty: {scenario['difficulty']}")
            print(f"Questions: {scenario['num_questions']}")
            print(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        result_path = run_scenario(scenario['path'], output_dir)
        execution_time = time.time() - start_time
        
        # Parse agent metrics from the generated log
        agent_metrics = parse_agent_metrics_from_log(result_path)
        
        if show_progress:
            with print_lock:
                print(f"✅ COMPLETED in {execution_time:.1f}s")
                print(f"   Agent Quality: {agent_metrics['agent_success']}/{agent_metrics['agent_total']} questions valid")
                print(f"📄 Log saved to: {result_path}")
        
        return {
            'scenario': scenario,
            'success': True,
            'execution_time': execution_time,
            'log_path': result_path,
            'error': None,
            'agent_metrics': agent_metrics
        }
        
    except Exception as e:
        execution_time = time.time() - start_time
        if show_progress:
            with print_lock:
                print(f"❌ FAILED in {execution_time:.1f}s")
                print(f"Error: {str(e)}")
        
        return {
            'scenario': scenario,
            'success': False,
            'execution_time': execution_time,
            'log_path': None,
            'error': str(e),
            'agent_metrics': {'agent_success': 0, 'agent_total': scenario['num_questions'], 'exec_success': 0, 'eval_valid': 0, 'output_correct': 0, 'issues': []}
        }


def _run_scenario_wrapper(args):
    """Wrapper function for parallel execution."""
    scenario, output_dir = args
    return run_single_scenario(scenario, output_dir, show_progress=False)


def run_gauntlet(scenarios, output_dir, category_filter=None, parallel=False, max_workers=None):
    """Run the complete test gauntlet.
    
    Args:
        scenarios: List of scenario dictionaries
        output_dir: Directory to save logs
        category_filter: Optional category to filter by
        parallel: If True, run scenarios in parallel
        max_workers: Number of parallel workers (defaults to CPU count - 1)
    """
    if category_filter:
        scenarios = [s for s in scenarios if s['category'] == category_filter]
        print(f"Running {len(scenarios)} scenarios from category {category_filter}")
    else:
        print(f"Running {len(scenarios)} scenarios from all categories")
    
    if parallel:
        if max_workers is None:
            # Conservative default to avoid API rate limits
            max_workers = min(3, max(1, cpu_count() - 1))
        print(f"🔥 Parallel mode: Using {max_workers} workers")
        print(f"⚠️  Note: Limited to {max_workers} workers to avoid API rate limits")
        print(f"   Increase with --workers if you have higher OpenAI tier limits")
    else:
        print(f"⏳ Sequential mode")
    
    results = []
    start_time = time.time()
    
    if parallel:
        # Parallel execution with staggered starts to reduce rate limit pressure
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            # Submit scenarios with staggered timing to avoid simultaneous API bursts
            future_to_scenario = {}
            for i, scenario in enumerate(scenarios):
                # Add small delay between submissions to stagger API calls
                if i > 0:
                    time.sleep(random.uniform(0.5, 1.5))  # Random delay to spread load
                future = executor.submit(_run_scenario_wrapper, (scenario, output_dir))
                future_to_scenario[future] = scenario
            
            # Process completed scenarios
            completed = 0
            for future in as_completed(future_to_scenario):
                scenario = future_to_scenario[future]
                completed += 1
                
                try:
                    result = future.result()
                    results.append(result)
                    
                    status = "✅" if result['success'] else "❌"
                    with print_lock:
                        print(f"\n[{completed}/{len(scenarios)}] {status} {scenario['filename']} ({result['execution_time']:.1f}s)")
                        if not result['success']:
                            print(f"    Error: {result['error']}")
                        
                except Exception as e:
                    with print_lock:
                        print(f"\n[{completed}/{len(scenarios)}] ❌ {scenario['filename']} - Execution error: {str(e)}")
                    results.append({
                        'scenario': scenario,
                        'success': False,
                        'execution_time': 0,
                        'log_path': None,
                        'error': str(e)
                    })
    else:
        # Sequential execution (original behavior)
        for i, scenario in enumerate(scenarios, 1):
            print(f"\n🚀 Scenario {i}/{len(scenarios)}")
            result = run_single_scenario(scenario, output_dir)
            results.append(result)
            
            # Brief pause between scenarios
            if i < len(scenarios):
                time.sleep(2)
    
    total_time = time.time() - start_time
    print_summary_report(results, total_time)
    
    return results


def print_summary_report(results, total_time):
    """Print a comprehensive summary report with dual metrics."""
    print("\n" + "="*80)
    print("GAUNTLET EXECUTION SUMMARY")
    print("="*80)
    
    # Infrastructure metrics (scenario-level)
    infra_successful = [r for r in results if r['success']]
    infra_failed = [r for r in results if not r['success']]
    
    # Agent metrics (question-level, aggregated)
    total_questions = sum(r.get('agent_metrics', {}).get('agent_total', 0) for r in results)
    agent_successes = sum(r.get('agent_metrics', {}).get('agent_success', 0) for r in results)
    exec_successes = sum(r.get('agent_metrics', {}).get('exec_success', 0) for r in results)
    eval_valid = sum(r.get('agent_metrics', {}).get('eval_valid', 0) for r in results)
    output_correct = sum(r.get('agent_metrics', {}).get('output_correct', 0) for r in results)
    
    print(f"\n📊 INFRASTRUCTURE METRICS (Did the agent run without crashing?)")
    print(f"   ✅ Scenarios Completed: {len(infra_successful)}/{len(results)} ({len(infra_successful)/len(results)*100:.1f}%)")
    print(f"   ❌ Scenarios Crashed: {len(infra_failed)}/{len(results)} ({len(infra_failed)/len(results)*100:.1f}%)")
    print(f"   ⏱️  Total Time: {total_time:.1f}s ({total_time/60:.1f} minutes)")
    
    print(f"\n🎯 AGENT QUALITY METRICS (Did the agent produce valid results?)")
    if total_questions > 0:
        print(f"   ✅ Questions with Valid Results: {agent_successes}/{total_questions} ({agent_successes/total_questions*100:.1f}%)")
        print(f"   Breakdown:")
        print(f"      - Code Execution Success: {exec_successes}/{total_questions} ({exec_successes/total_questions*100:.1f}%)")
        print(f"      - Evaluation Valid: {eval_valid}/{total_questions} ({eval_valid/total_questions*100:.1f}%)")
        print(f"      - Output Type Correct: {output_correct}/{total_questions} ({output_correct/total_questions*100:.1f}%)")
    else:
        print(f"   No questions executed.")
    
    print()
    
    # Detailed scenario breakdown
    if infra_successful:
        print(f"✅ Completed Scenarios:")
        for result in infra_successful:
            scenario = result['scenario']
            metrics = result.get('agent_metrics', {})
            agent_str = f"{metrics.get('agent_success', '?')}/{metrics.get('agent_total', '?')}" if metrics else "N/A"
            print(f"   {scenario['filename']} ({result['execution_time']:.1f}s) - Agent: {agent_str} valid")
        print()
    
    if infra_failed:
        print(f"❌ Crashed Scenarios:")
        for result in infra_failed:
            scenario = result['scenario']
            print(f"   {scenario['filename']} - {result['error']}")
        print()
    
    # Scenarios with agent quality issues (completed but had problems)
    quality_issues = [r for r in infra_successful 
                      if r.get('agent_metrics', {}).get('agent_success', 0) < r.get('agent_metrics', {}).get('agent_total', 0)]
    if quality_issues:
        print(f"⚠️  Scenarios with Agent Quality Issues:")
        for result in quality_issues:
            scenario = result['scenario']
            metrics = result.get('agent_metrics', {})
            issues = metrics.get('issues', [])
            print(f"   {scenario['filename']}: {metrics.get('agent_success', 0)}/{metrics.get('agent_total', 0)} valid")
            for issue in issues[:3]:  # Show first 3 issues
                print(f"      - {issue}")
            if len(issues) > 3:
                print(f"      ... and {len(issues) - 3} more issues")
        print()
    
    # Category breakdown with both metrics
    categories = {}
    for result in results:
        cat = result['scenario']['category']
        if cat not in categories:
            categories[cat] = {'infra_success': 0, 'infra_total': 0, 'agent_success': 0, 'agent_total': 0}
        categories[cat]['infra_total'] += 1
        if result['success']:
            categories[cat]['infra_success'] += 1
        metrics = result.get('agent_metrics', {})
        categories[cat]['agent_success'] += metrics.get('agent_success', 0)
        categories[cat]['agent_total'] += metrics.get('agent_total', 0)
    
    print(f"📈 Performance by Category:")
    print(f"   {'Category':<30} {'Infra':<12} {'Agent Quality':<15}")
    print(f"   {'-'*30} {'-'*12} {'-'*15}")
    for cat_name, stats in sorted(categories.items()):
        infra_rate = stats['infra_success'] / stats['infra_total'] * 100 if stats['infra_total'] > 0 else 0
        agent_rate = stats['agent_success'] / stats['agent_total'] * 100 if stats['agent_total'] > 0 else 0
        infra_str = f"{stats['infra_success']}/{stats['infra_total']} ({infra_rate:.0f}%)"
        agent_str = f"{stats['agent_success']}/{stats['agent_total']} ({agent_rate:.0f}%)"
        print(f"   {cat_name:<30} {infra_str:<12} {agent_str:<15}")
    
    print("\n" + "="*80)
    if results and results[0].get('log_path'):
        log_dir = os.path.dirname(results[0]['log_path'])
        print(f"📁 All logs saved to: {log_dir}")
    print("="*80)


def main():
    parser = argparse.ArgumentParser(description='Run AI data scientist agent test gauntlet')
    parser.add_argument('--category', help='Run only scenarios from specific category (e.g., A_statistical_analysis)')
    parser.add_argument('--scenario', help='Run single scenario by filename (without .json)')
    parser.add_argument('--list', action='store_true', help='List all available scenarios')
    parser.add_argument('--output-dir', default='logs/gauntlet', help='Output directory for logs')
    parser.add_argument('--parallel', action='store_true', help='Run scenarios in parallel (faster)')
    parser.add_argument('--workers', type=int, help=f'Number of parallel workers (default: 3, max recommended: 5 to avoid rate limits)')
    
    args = parser.parse_args()
    
    # Auto-enable parallel mode if workers specified
    if args.workers and not args.parallel:
        args.parallel = True
        print(f"ℹ️  Auto-enabling parallel mode (--workers {args.workers} specified)")
    
    # Create timestamped subdirectory for logs
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir = os.path.join(args.output_dir, timestamp)
    os.makedirs(output_dir, exist_ok=True)
    
    # Setup console logging to file
    console_log_path = os.path.join(output_dir, f"console_log_{timestamp}.md")
    
    print(f"📁 Logs will be saved to: {output_dir}")
    print(f"📝 Console output will be logged to: console_log_{timestamp}.md")
    
    # Get all scenarios
    scenarios = get_all_scenarios()
    
    if args.list:
        print_summary(scenarios)
        return
    
    # Redirect stdout to capture console output
    with TeeLogger(console_log_path) as tee:
        original_stdout = sys.stdout
        sys.stdout = tee
        
        try:
            # Write markdown header to log file
            print(f"# Test Gauntlet Console Log")
            print(f"**Timestamp:** {timestamp}")
            print(f"**Output Directory:** {output_dir}")
            print(f"**Parallel Mode:** {'Yes' if args.parallel else 'No'}")
            if args.parallel:
                print(f"**Workers:** {args.workers or 'default'}")
            print(f"\n{'='*80}\n")
            
            if args.scenario:
                # Run single scenario
                scenario = next((s for s in scenarios if s['filename'] == f"{args.scenario}.json"), None)
                if not scenario:
                    print(f"Scenario '{args.scenario}.json' not found")
                    print("Use --list to see available scenarios")
                    return
                
                result = run_single_scenario(scenario, output_dir)
                print_summary_report([result], result['execution_time'])
                
            elif args.category:
                # Run scenarios from specific category
                run_gauntlet(scenarios, output_dir, category_filter=args.category, 
                            parallel=args.parallel, max_workers=args.workers)
                
            else:
                # Run complete gauntlet
                print_summary(scenarios)
                print("\n🚀 Starting complete test gauntlet...")
                if args.parallel:
                    workers = args.workers or max(1, cpu_count() - 1)
                    print(f"⚡ Parallel mode enabled with {workers} workers")
                    print(f"💻 Your system has {cpu_count()} CPU cores")
                print("Press Ctrl+C to interrupt\n")
                
                try:
                    results = run_gauntlet(scenarios, output_dir, 
                                          parallel=args.parallel, max_workers=args.workers)
                except KeyboardInterrupt:
                    print("\n\n⚠️  Gauntlet interrupted by user")
                    return
            
            print("\n🎉 Gauntlet execution complete!")
            print(f"\n📝 Full console log saved to: {console_log_path}")
            
        finally:
            # Restore original stdout
            sys.stdout = original_stdout


if __name__ == "__main__":
    main()
