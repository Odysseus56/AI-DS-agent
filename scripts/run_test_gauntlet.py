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

from tests.test_runner import run_scenario, list_available_scenarios


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
        
        if show_progress:
            with print_lock:
                print(f"✅ COMPLETED in {execution_time:.1f}s")
                print(f"📄 Log saved to: {result_path}")
        
        return {
            'scenario': scenario,
            'success': True,
            'execution_time': execution_time,
            'log_path': result_path,
            'error': None
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
            'error': str(e)
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
    """Print a comprehensive summary report."""
    print("\n" + "="*80)
    print("GAUNTLET EXECUTION SUMMARY")
    print("="*80)
    
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    print(f"📊 Overall Results:")
    print(f"   ✅ Successful: {len(successful)}/{len(results)} ({len(successful)/len(results)*100:.1f}%)")
    print(f"   ❌ Failed: {len(failed)}/{len(results)} ({len(failed)/len(results)*100:.1f}%)")
    print(f"   ⏱️  Total Time: {total_time:.1f}s ({total_time/60:.1f} minutes)")
    print()
    
    if successful:
        print(f"✅ Successful Scenarios:")
        for result in successful:
            scenario = result['scenario']
            print(f"   {scenario['filename']} ({result['execution_time']:.1f}s)")
        print()
    
    if failed:
        print(f"❌ Failed Scenarios:")
        for result in failed:
            scenario = result['scenario']
            print(f"   {scenario['filename']} - {result['error']}")
        print()
    
    # Category breakdown
    categories = {}
    for result in results:
        cat = result['scenario']['category']
        if cat not in categories:
            categories[cat] = {'success': 0, 'fail': 0, 'total': 0}
        categories[cat]['total'] += 1
        if result['success']:
            categories[cat]['success'] += 1
        else:
            categories[cat]['fail'] += 1
    
    print(f"📈 Performance by Category:")
    for cat_name, stats in sorted(categories.items()):
        success_rate = stats['success'] / stats['total'] * 100
        print(f"   {cat_name}: {stats['success']}/{stats['total']} ({success_rate:.1f}%)")
    
    print("\n" + "="*80)
    print("📁 All logs saved to: logs/gauntlet/")
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
    
    # Ensure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Get all scenarios
    scenarios = get_all_scenarios()
    
    if args.list:
        print_summary(scenarios)
        return
    
    if args.scenario:
        # Run single scenario
        scenario = next((s for s in scenarios if s['filename'] == f"{args.scenario}.json"), None)
        if not scenario:
            print(f"Scenario '{args.scenario}.json' not found")
            print("Use --list to see available scenarios")
            return
        
        result = run_single_scenario(scenario, args.output_dir)
        print_summary_report([result], result['execution_time'])
        
    elif args.category:
        # Run scenarios from specific category
        run_gauntlet(scenarios, args.output_dir, category_filter=args.category, 
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
            results = run_gauntlet(scenarios, args.output_dir, 
                                  parallel=args.parallel, max_workers=args.workers)
        except KeyboardInterrupt:
            print("\n\n⚠️  Gauntlet interrupted by user")
            return
    
    print("\n🎉 Gauntlet execution complete!")


if __name__ == "__main__":
    main()
