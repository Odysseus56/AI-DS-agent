# Headless Testing Tool - Technical Requirements Document

**Version:** 1.0  
**Date:** January 3, 2026  
**Status:** Draft for Review

---

## Executive Summary

We are building a **headless testing tool** that allows us to run the AI Data Scientist agent in a non-interactive mode. This tool will simulate user scenarios (e.g., loading datasets, asking questions) and capture detailed logs of the agent's behavior. The goal is to accelerate the development cycle by eliminating the need to manually test through the Streamlit UI after every code change.

**Key Principle:** Reuse existing application logic. Do not duplicate code.

---

## Problem Statement

### Current Development Workflow (Slow)
1. Make a code change (e.g., update a prompt in `llm_client.py`)
2. Kill the Streamlit app
3. Restart Streamlit (`streamlit run app.py`)
4. Wait for app to load
5. Upload datasets through UI
6. Type questions manually
7. Observe results
8. Repeat for multiple test cases

**Time per iteration:** 2-5 minutes  
**Pain points:** Manual, repetitive, slow feedback loop

### Desired Workflow (Fast)
1. Make a code change
2. Run: `python test_agent_cli.py --scenario merge_datasets`
3. Review detailed log output
4. Iterate

**Time per iteration:** 10-30 seconds  
**Benefits:** Automated, fast feedback, reproducible tests

---

## Goals & Non-Goals

### Goals ✅
- **Automate end-to-end testing** of the LangGraph agent workflow
- **Reuse existing application logic** from `app.py`, `langgraph_agent.py`, etc.
- **Create a scenario library** with pre-defined test cases
- **Generate detailed logs** capturing all node executions
- **Enable rapid iteration** during development
- **Keep it simple and modular** following software best practices

### Non-Goals ❌
- Unit testing (testing individual functions in isolation)
- Regression testing framework (automated pass/fail assertions)
- UI testing (Streamlit interface validation)
- Performance benchmarking
- Production deployment tooling

---

## Architecture Overview

### High-Level Design

```
┌─────────────────────────────────────────────────────────────┐
│                    TEST SCENARIO (JSON)                     │
│  - Datasets to load                                         │
│  - Questions to ask                                         │
│  - Expected behavior (optional)                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                  TEST RUNNER (CLI Script)                   │
│  - Loads datasets programmatically                          │
│  - Calls LangGraph agent (reuses app logic)                 │
│  - Captures all node outputs                                │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                   LANGGRAPH AGENT (Reused)                  │
│  - Same code as Streamlit app                               │
│  - No modifications needed                                  │
│  - Executes nodes: Understand → Requirements → Profile      │
│                    → Alignment → Code → Evaluate            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    LOG OUTPUT (Markdown)                    │
│  - Timestamped execution trace                              │
│  - Each node's input/output                                 │
│  - Generated code                                           │
│  - Execution results                                        │
│  - Saved to test_results/ folder                            │
└─────────────────────────────────────────────────────────────┘
```

---

## Component Specifications

### 1. Test Scenario Format

**File:** `test_scenarios/<scenario_name>.json`

**Schema:**
```json
{
  "name": "Human-readable scenario name",
  "description": "What this test validates",
  "datasets": [
    {
      "path": "data/campaign_results.csv",
      "id": "campaign_results"
    },
    {
      "path": "data/customer_profiles.csv", 
      "id": "customer_profiles"
    }
  ],
  "questions": [
    "Can you merge these two datasets on customer_id?",
    "What is the average age of customers?",
    "Show me a histogram of monthly card spend"
  ],
  "metadata": {
    "author": "Your Name",
    "created": "2026-01-03",
    "tags": ["merge", "multi-dataset"]
  }
}
```

**Design Rationale:**
- **Simple JSON format** - Easy to read and edit
- **Multiple questions per scenario** - Test sequential interactions
- **Flexible dataset specification** - Support any CSV files
- **Metadata for organization** - Track who created what and when

---

### 2. CLI Test Runner

**File:** `test_agent_cli.py`

**Responsibilities:**
1. Parse command-line arguments
2. Load test scenario from JSON
3. Initialize datasets (load CSVs into pandas DataFrames)
4. Execute questions through LangGraph agent
5. Capture and format output
6. Save logs to file

**Command-Line Interface:**
```bash
# Run a specific scenario
python test_agent_cli.py --scenario merge_datasets

# Run all scenarios in test_scenarios/ folder
python test_agent_cli.py --all

# Verbose output (show LLM prompts/responses)
python test_agent_cli.py --scenario merge_datasets --verbose

# Save output to specific file
python test_agent_cli.py --scenario merge_datasets --output my_test.md
```

**Key Design Principle:**
- **Thin wrapper** - Minimal logic, delegates to existing code
- **No business logic** - Only orchestration and formatting
- **Reuses app.py patterns** - Same dataset loading, same agent initialization

---

### 3. Core Test Execution Logic

**File:** `test_runner.py`

**Purpose:** Encapsulate the test execution logic separate from CLI parsing

**Key Functions:**

```python
def load_scenario(scenario_path: str) -> dict:
    """Load and validate test scenario from JSON file"""
    
def initialize_datasets(dataset_configs: list) -> dict:
    """Load CSV files into the same format as app.py uses"""
    # Returns: {dataset_id: {name, df, data_summary, uploaded_at}}
    
def run_agent_on_question(question: str, datasets: dict) -> dict:
    """Execute LangGraph agent and capture all node outputs"""
    # Returns: {final_output, node_states, execution_time}
    
def format_test_results(scenario: dict, results: list) -> str:
    """Format execution results as markdown log"""
```

**Design Rationale:**
- **Separation of concerns** - CLI parsing vs. execution logic
- **Testable** - Functions can be unit tested later if needed
- **Reusable** - Could be imported by other tools

---

### 4. Log Output Format

**File:** `test_results/<timestamp>_<scenario_name>.md`

**Structure:**
```markdown
# Test Run: Merge Datasets Scenario
**Timestamp:** 2026-01-03 11:30:45  
**Duration:** 8.5 seconds  
**Status:** ✅ All questions completed

---

## Scenario Details
- **Name:** Merge Two Datasets
- **Datasets:** campaign_results.csv, customer_profiles.csv
- **Questions:** 3

---

## Question 1: "Can you merge these two datasets on customer_id?"

### Node 0: Understand Question
⏱️ 0.5s | ✅ Completed
- **needs_data_work:** True
- **reasoning:** "Question requires data merging operation"

### Node 1B: Formulate Requirements
⏱️ 0.6s | ✅ Completed
- **analysis_type:** data_merging
- **variables_needed:** ['customer_id']
- **success_criteria:** "Merged dataset with all columns from both sources"

### Node 2: Profile Data
⏱️ 0.8s | ✅ Completed
- **available_columns:** ['customer_id']
- **is_suitable:** True
- **reasoning:** "customer_id exists in both datasets"

### Node 3: Alignment Check
⏱️ 0.4s | ✅ Completed
- **aligned:** True
- **recommendation:** proceed

### Node 4: Generate & Execute Code
⏱️ 1.2s | ✅ Completed

**Generated Code:**
```python
df1 = datasets['campaign_results']['df']
df2 = datasets['customer_profiles']['df']
merged_df = pd.merge(df1, df2, on='customer_id', how='inner')
result = merged_df
```

**Execution Result:**
- ✅ Code executed successfully
- Output: DataFrame with 35000 rows, 23 columns

### Node 6: Explanation
⏱️ 0.5s | ✅ Completed
[Explanation text...]

---

## Question 2: "What is the average age of customers?"
[Similar structure...]

---

## Summary
✅ **3/3 questions completed successfully**
- Total execution time: 8.5 seconds
- No errors encountered
- All nodes executed as expected
```

**Design Rationale:**
- **Human-readable** - Easy to scan and understand
- **Detailed** - Captures everything needed for debugging
- **Structured** - Consistent format for all tests
- **Timestamped** - Can track changes over time

---

## Implementation Requirements

### Critical Requirement #1: Reuse Application Logic

**DO:**
- Import and call functions from `langgraph_agent.py`
- Use the same `agent_app` instance
- Load datasets using the same pattern as `app.py`
- Reuse `data_analyzer.generate_data_summary()`
- Reuse `DualLogger` for logging

**DO NOT:**
- Copy-paste code from `app.py` or `langgraph_agent.py`
- Create duplicate implementations of agent logic
- Modify core application files to support testing

**Implementation Pattern:**
```python
# CORRECT: Reuse existing code
from langgraph_agent import agent_app
from data_analyzer import generate_data_summary

# Initialize datasets same way as app.py
datasets = {}
for dataset_config in scenario['datasets']:
    df = pd.read_csv(dataset_config['path'])
    datasets[dataset_config['id']] = {
        'name': dataset_config['id'],
        'df': df,
        'data_summary': generate_data_summary(df),
        'uploaded_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

# Run agent same way as app.py
initial_state = {
    "question": question,
    "datasets": datasets,
    "data_summary": combined_summary,
    # ... rest of state
}

for event in agent_app.stream(initial_state):
    # Capture node outputs
```

---

### Critical Requirement #2: Keep It Simple

**Simplicity Guidelines:**
1. **Single responsibility** - Each file has one clear purpose
2. **Minimal dependencies** - Only use what's already in the project
3. **No over-engineering** - Start with basics, add features later
4. **Clear naming** - Functions and variables should be self-documenting
5. **Modular design** - Easy to extend without rewriting

**What NOT to build (yet):**
- Complex assertion frameworks
- Test result databases
- Web dashboards
- Parallel test execution
- Test coverage metrics

---

### Critical Requirement #3: Modularity & Best Practices

**File Organization:**
```
d:\1_Projects\AI-DS-agent\
├── test_scenarios/          # Test case definitions
│   ├── merge_datasets.json
│   ├── basic_stats.json
│   └── visualization.json
├── test_results/            # Output logs (gitignored)
│   └── 2026-01-03_11-30_merge_datasets.md
├── test_agent_cli.py        # CLI entry point
├── test_runner.py           # Core execution logic
└── readmes/
    └── HEADLESS_TESTING_REQUIREMENTS.md  # This document
```

**Code Quality Standards:**
- **Type hints** - Use Python type annotations
- **Docstrings** - Document all public functions
- **Error handling** - Graceful failure with clear messages
- **Logging** - Use Python's logging module for debug output
- **Configuration** - Use constants for file paths, timeouts, etc.

**Example:**
```python
from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)

def load_scenario(scenario_path: str) -> Dict[str, Any]:
    """
    Load and validate a test scenario from a JSON file.
    
    Args:
        scenario_path: Path to the scenario JSON file
        
    Returns:
        Dictionary containing scenario configuration
        
    Raises:
        FileNotFoundError: If scenario file doesn't exist
        ValueError: If scenario JSON is invalid
    """
    try:
        with open(scenario_path, 'r') as f:
            scenario = json.load(f)
        
        # Validate required fields
        required_fields = ['name', 'datasets', 'questions']
        for field in required_fields:
            if field not in scenario:
                raise ValueError(f"Missing required field: {field}")
        
        logger.info(f"Loaded scenario: {scenario['name']}")
        return scenario
        
    except FileNotFoundError:
        logger.error(f"Scenario file not found: {scenario_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in scenario file: {e}")
        raise ValueError(f"Invalid scenario JSON: {e}")
```

---

## Data Flow Diagram

```
┌──────────────────┐
│  User runs CLI   │
│  with scenario   │
└────────┬─────────┘
         │
         ↓
┌────────────────────────────────────────────────────────┐
│  test_agent_cli.py                                     │
│  - Parse arguments                                     │
│  - Load scenario JSON                                  │
└────────┬───────────────────────────────────────────────┘
         │
         ↓
┌────────────────────────────────────────────────────────┐
│  test_runner.py                                        │
│  - Load datasets (reuse app.py pattern)                │
│  - Build combined_summary                              │
└────────┬───────────────────────────────────────────────┘
         │
         ↓ (for each question)
┌────────────────────────────────────────────────────────┐
│  langgraph_agent.py (REUSED, NOT MODIFIED)             │
│  - agent_app.stream(initial_state)                     │
│  - Executes nodes: 0 → 1B → 2 → 3 → 4 → 5 → 6         │
└────────┬───────────────────────────────────────────────┘
         │
         ↓ (capture events)
┌────────────────────────────────────────────────────────┐
│  test_runner.py                                        │
│  - Collect node outputs                                │
│  - Track timing                                        │
│  - Format as markdown                                  │
└────────┬───────────────────────────────────────────────┘
         │
         ↓
┌────────────────────────────────────────────────────────┐
│  test_results/<timestamp>_<scenario>.md                │
│  - Detailed execution log                              │
│  - Human-readable format                               │
└────────────────────────────────────────────────────────┘
```

---

## Success Criteria

### Minimum Viable Product (MVP)
- [ ] Can run a single scenario from command line
- [ ] Loads datasets programmatically (no UI needed)
- [ ] Executes LangGraph agent using existing code
- [ ] Captures all node outputs
- [ ] Generates readable markdown log
- [ ] Saves log to `test_results/` folder

### Definition of Success
1. **Faster iteration** - Can test a change in < 30 seconds
2. **Reproducible** - Same scenario produces consistent results
3. **Debuggable** - Logs contain enough detail to diagnose issues
4. **Maintainable** - Code is clean and easy to modify
5. **Reusable** - Can easily add new test scenarios

---

## Future Enhancements (Out of Scope for V1)

These are good ideas but NOT part of the initial implementation:

1. **Automated Assertions**
   - Check if specific nodes were executed
   - Validate generated code syntax
   - Compare outputs against expected results

2. **Regression Testing**
   - Save "golden" outputs
   - Detect when behavior changes
   - Flag breaking changes

3. **Performance Metrics**
   - Track execution time trends
   - Identify slow nodes
   - Optimize bottlenecks

4. **Parallel Execution**
   - Run multiple scenarios simultaneously
   - Reduce total test time

5. **CI/CD Integration**
   - Run tests on every commit
   - Block merges if tests fail

6. **Interactive Mode**
   - REPL for asking questions
   - Live feedback during development

---

## Implementation Phases

### Phase 1: Core Infrastructure (Day 1)
**Goal:** Get basic headless execution working

**Tasks:**
1. Create `test_runner.py` with dataset loading logic
2. Create `test_agent_cli.py` with basic CLI
3. Test with one hardcoded scenario
4. Verify agent executes correctly

**Deliverable:** Can run agent headlessly and see output in console

---

### Phase 2: Scenario System (Day 1-2)
**Goal:** Support JSON-based test scenarios

**Tasks:**
1. Define JSON schema for scenarios
2. Implement scenario loading and validation
3. Create 3 sample scenarios
4. Test with multiple scenarios

**Deliverable:** Can run different scenarios from JSON files

---

### Phase 3: Rich Logging (Day 2)
**Goal:** Generate detailed, readable logs

**Tasks:**
1. Capture all node states during execution
2. Format as structured markdown
3. Save to `test_results/` folder
4. Add timing information

**Deliverable:** Detailed logs that enable debugging

---

### Phase 4: Polish & Documentation (Day 2-3)
**Goal:** Make it production-ready

**Tasks:**
1. Add error handling
2. Write usage documentation
3. Add example scenarios
4. Test edge cases

**Deliverable:** Stable tool ready for daily use

---

## Risk Assessment

### Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| LangGraph agent behaves differently in headless mode | High | Use exact same initialization as app.py |
| Dataset loading fails for large files | Medium | Add file size checks, use same loading logic as app.py |
| Logs become too verbose to read | Medium | Implement log levels (summary vs. detailed) |
| Scenarios become hard to maintain | Low | Keep JSON schema simple, add validation |

### Development Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Accidentally duplicate app logic | High | Code review, strict adherence to "reuse only" principle |
| Over-engineering the solution | Medium | Start with MVP, resist feature creep |
| Poor code organization | Medium | Follow modular design, clear file structure |

---

## Acceptance Criteria

Before considering this tool "done," it must:

1. ✅ **Execute without Streamlit** - Runs in pure Python, no browser needed
2. ✅ **Reuse existing logic** - Zero duplication of agent code
3. ✅ **Support multiple scenarios** - Can run different test cases
4. ✅ **Generate detailed logs** - Captures all node outputs
5. ✅ **Be fast** - Completes a test run in < 30 seconds
6. ✅ **Be simple** - Code is easy to understand and modify
7. ✅ **Be documented** - Clear README with usage examples

---

## Appendix A: Example Scenario

**File:** `test_scenarios/merge_datasets.json`

```json
{
  "name": "Merge Two Datasets on Customer ID",
  "description": "Tests the agent's ability to merge two datasets using a common join key",
  "datasets": [
    {
      "path": "data/campaign_results.csv",
      "id": "campaign_results"
    },
    {
      "path": "data/customer_profiles.csv",
      "id": "customer_profiles"
    }
  ],
  "questions": [
    "Can you merge these two datasets on customer_id?"
  ],
  "metadata": {
    "author": "Development Team",
    "created": "2026-01-03",
    "tags": ["merge", "multi-dataset", "data-operations"],
    "expected_duration_seconds": 5
  }
}
```

---

## Appendix B: Technology Stack

**Languages & Frameworks:**
- Python 3.10+
- LangGraph (existing)
- Pandas (existing)

**New Dependencies:**
- None (use only existing project dependencies)

**File Formats:**
- JSON for scenarios
- Markdown for logs
- CSV for datasets

---

## Questions & Answers

**Q: Why not use pytest or unittest?**  
A: Those are for unit testing. We're building an end-to-end integration test tool. We may add pytest later for regression testing.

**Q: Why markdown logs instead of JSON?**  
A: Markdown is human-readable and easy to review in the IDE. We can add JSON export later if needed for programmatic analysis.

**Q: Can we run this in CI/CD?**  
A: Not in V1, but the architecture supports it. We'd need to add exit codes and automated assertions.

**Q: How do we handle API costs?**  
A: Each test run makes real OpenAI API calls. Keep scenarios focused and run selectively during development.

**Q: What about testing error cases?**  
A: Good question! We can create scenarios that intentionally trigger errors (e.g., asking for a column that doesn't exist) to test error handling.

---

## Approval & Sign-Off

**Document Status:** Draft for Review

**Next Steps:**
1. Review this requirements document
2. Discuss any concerns or modifications
3. Approve for implementation
4. Begin Phase 1 development

---

**Document History:**
- v1.0 (2026-01-03): Initial draft
