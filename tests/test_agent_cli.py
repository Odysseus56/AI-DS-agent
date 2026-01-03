#!/usr/bin/env python
"""
Headless Test CLI for AI Data Scientist Agent

This script provides a command-line interface for running the LangGraph agent
in headless mode without the Streamlit UI.

Usage:
    python test_agent_cli.py --scenario merge_datasets
    python test_agent_cli.py --all
    python test_agent_cli.py --list

Key Principle: This is a thin wrapper that delegates to test_runner.py.
No business logic here - only CLI parsing and orchestration.
"""

import argparse
import sys
import os
import logging
from datetime import datetime

# Add parent directory to path to import application modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from test_runner import (
    run_scenario,
    load_scenario,
    list_available_scenarios,
    initialize_datasets,
    run_agent_on_question,
    build_combined_summary,
    format_test_results
)

# Configure logging
def setup_logging(verbose: bool = False):
    """Configure logging based on verbosity level."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%H:%M:%S'
    )

# =============================================================================
# CLI COMMANDS
# =============================================================================

def cmd_run_scenario(args):
    """Run a single test scenario."""
    scenario_path = os.path.join(args.scenarios_dir, f"{args.scenario}.json")
    
    if not os.path.exists(scenario_path):
        print(f"[ERROR] Scenario not found: {scenario_path}")
        print(f"\nAvailable scenarios:")
        for name in list_available_scenarios(args.scenarios_dir):
            print(f"  - {name}")
        return 1
    
    print(f"[RUNNING] Scenario: {args.scenario}")
    print(f"   Source: {scenario_path}")
    print("")
    
    try:
        output_path = run_scenario(scenario_path, args.output_dir)
        print("")
        print(f"[SUCCESS] Test completed!")
        print(f"[OUTPUT] Results saved to: {output_path}")
        
        # Print summary to console
        if args.show_output:
            print("")
            print("=" * 60)
            with open(output_path, 'r', encoding='utf-8') as f:
                print(f.read())
        
        return 0
        
    except Exception as e:
        print(f"[ERROR] Error running scenario: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def cmd_run_all(args):
    """Run all available test scenarios."""
    scenarios = list_available_scenarios(args.scenarios_dir)
    
    if not scenarios:
        print(f"[ERROR] No scenarios found in: {args.scenarios_dir}")
        return 1
    
    print(f"[RUNNING] {len(scenarios)} scenarios...")
    print("")
    
    results = []
    for scenario_name in scenarios:
        print(f"  > {scenario_name}")
        scenario_path = os.path.join(args.scenarios_dir, f"{scenario_name}.json")
        
        try:
            output_path = run_scenario(scenario_path, args.output_dir)
            results.append((scenario_name, True, output_path))
            print(f"     [OK] Completed")
        except Exception as e:
            results.append((scenario_name, False, str(e)))
            print(f"     [FAIL] Failed: {e}")
        print("")
    
    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    successes = sum(1 for _, success, _ in results if success)
    print(f"Passed: {successes}/{len(results)}")
    
    if successes < len(results):
        print("\nFailed scenarios:")
        for name, success, error in results:
            if not success:
                print(f"  [FAIL] {name}: {error}")
    
    return 0 if successes == len(results) else 1


def cmd_list_scenarios(args):
    """List all available test scenarios."""
    scenarios = list_available_scenarios(args.scenarios_dir)
    
    if not scenarios:
        print(f"No scenarios found in: {args.scenarios_dir}")
        print("\nCreate a scenario file in test_scenarios/ folder.")
        return 0
    
    print(f"Available scenarios ({len(scenarios)}):")
    print("")
    
    for name in scenarios:
        scenario_path = os.path.join(args.scenarios_dir, f"{name}.json")
        try:
            scenario = load_scenario(scenario_path)
            desc = scenario.get('description', 'No description')
            questions = len(scenario.get('questions', []))
            datasets = len(scenario.get('datasets', []))
            print(f"  [SCENARIO] {name}")
            print(f"     {desc}")
            print(f"     Datasets: {datasets} | Questions: {questions}")
            print("")
        except Exception as e:
            print(f"  [WARNING] {name} (error loading: {e})")
            print("")
    
    return 0


def cmd_interactive(args):
    """Run interactive mode - ask questions directly."""
    print("Interactive Headless Mode")
    print("=" * 60)
    print("")
    
    # Check for datasets
    if not args.datasets:
        print("[ERROR] No datasets specified. Use --datasets to specify CSV files.")
        print("   Example: python test_agent_cli.py --interactive --datasets data/campaign_results.csv data/customer_profiles.csv")
        return 1
    
    # Build dataset configs
    dataset_configs = []
    for path in args.datasets:
        if not os.path.exists(path):
            print(f"[ERROR] Dataset not found: {path}")
            return 1
        dataset_id = os.path.basename(path).replace('.csv', '').lower().replace(' ', '_').replace('-', '_')
        dataset_configs.append({'path': path, 'id': dataset_id})
    
    # Load datasets
    print("Loading datasets...")
    try:
        datasets = initialize_datasets(dataset_configs)
    except Exception as e:
        print(f"[ERROR] Error loading datasets: {e}")
        return 1
    
    print(f"[OK] Loaded {len(datasets)} datasets: {', '.join(datasets.keys())}")
    print("")
    print("Enter questions (type 'quit' to exit):")
    print("-" * 40)
    
    messages = []
    results = []
    
    while True:
        try:
            question = input("\nQuestion: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nExiting...")
            break
        
        if question.lower() in ['quit', 'exit', 'q']:
            break
        
        if not question:
            continue
        
        print("\nProcessing...")
        result = run_agent_on_question(question, datasets, messages)
        results.append({'question': question, 'result': result})
        
        if result['success']:
            print(f"\n[OK] Completed in {result['execution_time']:.1f}s")
            
            # Show key outputs
            final = result['final_output']
            if final.get('code'):
                print("\nGenerated Code:")
                print("-" * 40)
                print(final['code'])
            
            if final.get('explanation'):
                print("\nExplanation:")
                print("-" * 40)
                print(final['explanation'][:500])
                if len(final.get('explanation', '')) > 500:
                    print("... (truncated)")
            
            # Update message history
            messages.append({"role": "user", "content": question})
            if final.get('explanation'):
                messages.append({"role": "assistant", "content": final['explanation']})
        else:
            print(f"\n[FAIL] Failed: {result['error']}")
    
    # Save session log if any questions were asked
    if results:
        print("\n" + "=" * 60)
        save = input("Save session log? (y/n): ").strip().lower()
        if save == 'y':
            # Create a pseudo-scenario for formatting
            scenario = {
                'name': 'Interactive Session',
                'description': 'Questions asked in interactive mode',
                'datasets': dataset_configs,
                'questions': [r['question'] for r in results]
            }
            
            total_time = sum(r['result']['execution_time'] for r in results)
            log_content = format_test_results(
                scenario, 
                [r['result'] for r in results],
                total_time
            )
            
            os.makedirs(args.output_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            output_path = os.path.join(args.output_dir, f"{timestamp}_interactive.md")
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(log_content)
            
            print(f"[OUTPUT] Session saved to: {output_path}")
    
    return 0


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Headless Test CLI for AI Data Scientist Agent',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_agent_cli.py --scenario merge_datasets
  python test_agent_cli.py --all
  python test_agent_cli.py --list
  python test_agent_cli.py --interactive --datasets data/file1.csv data/file2.csv
        """
    )
    
    # Mode selection (mutually exclusive)
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        '--scenario', '-s',
        type=str,
        help='Run a specific scenario by name'
    )
    mode_group.add_argument(
        '--all', '-a',
        action='store_true',
        help='Run all available scenarios'
    )
    mode_group.add_argument(
        '--list', '-l',
        action='store_true',
        help='List all available scenarios'
    )
    mode_group.add_argument(
        '--interactive', '-i',
        action='store_true',
        help='Run in interactive mode'
    )
    
    # Options
    parser.add_argument(
        '--scenarios-dir',
        type=str,
        default=os.path.join(os.path.dirname(__file__), 'test_scenarios'),
        help='Directory containing scenario files (default: tests/test_scenarios)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='logs/cli',
        help='Directory for output logs (default: logs/cli)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    parser.add_argument(
        '--show-output',
        action='store_true',
        help='Print full results to console after completion'
    )
    parser.add_argument(
        '--datasets',
        nargs='+',
        help='Dataset files for interactive mode'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Route to appropriate command
    if args.scenario:
        return cmd_run_scenario(args)
    elif args.all:
        return cmd_run_all(args)
    elif args.list:
        return cmd_list_scenarios(args)
    elif args.interactive:
        return cmd_interactive(args)
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
