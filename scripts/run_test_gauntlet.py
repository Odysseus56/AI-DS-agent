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


def run_single_scenario(scenario, output_dir):
    """Run a single scenario and return results."""
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
        print(f"❌ FAILED in {execution_time:.1f}s")
        print(f"Error: {str(e)}")
        
        return {
            'scenario': scenario,
            'success': False,
            'execution_time': execution_time,
            'log_path': None,
            'error': str(e)
        }


def run_gauntlet(scenarios, output_dir, category_filter=None):
    """Run the complete test gauntlet."""
    if category_filter:
        scenarios = [s for s in scenarios if s['category'] == category_filter]
        print(f"Running {len(scenarios)} scenarios from category {category_filter}")
    else:
        print(f"Running {len(scenarios)} scenarios from all categories")
    
    results = []
    start_time = time.time()
    
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
        run_gauntlet(scenarios, args.output_dir, category_filter=args.category)
        
    else:
        # Run complete gauntlet
        print_summary(scenarios)
        print("\n🚀 Starting complete test gauntlet...")
        print("Press Ctrl+C to interrupt\n")
        
        try:
            results = run_gauntlet(scenarios, args.output_dir)
        except KeyboardInterrupt:
            print("\n\n⚠️  Gauntlet interrupted by user")
            return
    
    print("\n🎉 Gauntlet execution complete!")


if __name__ == "__main__":
    main()
