# Data Summary Flow & Multi-Dataset Merge Fix - Explained

## Overview: What Are Data Summaries?

Data summaries are text descriptions of your datasets that get passed to the LLM at various stages. Think of them as "context" that helps the AI understand what data is available.

There are **two types** of summaries in the system:

1. **Verbose Summary** - Full detailed report (used for most operations)
2. **Concise Summary** - Minimal column info only (used for profiling)

---

## The Data Flow: From Upload to Analysis

### Step 1: Dataset Upload (`app.py`)

When you upload a CSV file, the system creates a **verbose summary**:

```python
# In app.py, line 352
data_summary = generate_data_summary(df)
```

This verbose summary includes:
- Dataset shape (rows × columns)
- Column information (name, type, missing values, ranges)
- **Descriptive statistics** (mean, std, quartiles)
- **First 5 rows of actual data**
- Data quality issues

**Example of verbose summary:**
```
Dataset Shape: 35000 rows × 10 columns

Column Information:
  - customer_id (object) - 35000 unique values
  - date (object) - 1 unique values
  - campaign_group (object) - 2 unique values
  ...

Descriptive Statistics:
       customer_id  date  campaign_group  ...
count        35000 35000           35000  ...
unique       35000     1               2  ...
...

First 5 Rows:
  customer_id        date campaign_group  ...
0  CUST000001  2024-04-02      Treatment  ...
1  CUST000002  2024-04-02      Treatment  ...
...
```

This gets stored in `st.session_state.datasets[dataset_id]['data_summary']`.

---

### Step 2: User Asks a Question (`app.py`, line 513-515)

When you ask a question, the system builds a **combined verbose summary** for all datasets:

```python
combined_summary = "Available datasets:\n\n"
for ds_id, ds_info in st.session_state.datasets.items():
    combined_summary += f"Dataset '{ds_id}' ({ds_info['name']}):\n"
    combined_summary += ds_info['data_summary']  # ← VERBOSE summary
    combined_summary += "\n\n"
```

This combined summary is passed to the LangGraph agent as `initial_state["data_summary"]`.

---

### Step 3: LangGraph Nodes Use the Summary

The agent flows through multiple nodes. Here's what each node receives:

#### **Node 0: Understand Question**
- **Receives**: Combined verbose summary
- **Purpose**: Determine if question needs data work
- **Works fine**: Just reads the summary, doesn't generate JSON

#### **Node 1B: Formulate Requirements**
- **Receives**: Combined verbose summary
- **Purpose**: Define what columns/analysis are needed
- **Works fine**: Generates simple JSON with requirements

#### **Node 2: Profile Data** ⚠️ **THIS IS WHERE THE PROBLEM WAS**
- **Used to receive**: Combined verbose summary (with sample data!)
- **Purpose**: Check which required columns actually exist
- **Problem**: Had to generate JSON response while processing huge text with special characters

---

## The Problem: JSON Parsing Error

### What Went Wrong

In **Node 2 (Data Profiling)**, the `profile_data()` function:

1. **Received** the verbose summary (thousands of characters with sample data)
2. **Sent it to GPT-4o** with instructions to return JSON
3. **GPT-4o tried to parse** the sample data which contained:
   - Newlines (`\n`)
   - Quotes (`"`)
   - Special characters
   - Long strings

4. **GPT-4o generated malformed JSON** like:
   ```json
   {
     "available_columns": ["customer_id"],
     "reasoning": "The dataset contains customer_id column which appears in row:
   CUST000001  2024-04-02  Treatment  ...
   This column can be used for merging"  ← UNTERMINATED STRING!
   }
   ```

5. **Python's `json.loads()` failed** with:
   ```
   Unterminated string starting at: line 29 column 19 (char 1995)
   ```

### Why It Failed

The LLM tried to **include sample data in its JSON response**, but didn't properly escape special characters. The verbose summary was too complex for reliable JSON generation.

---

## The Solution: Two-Tier Summary System

### What We Changed

We now use **different summaries for different purposes**:

| Node | Summary Type | Why |
|------|-------------|-----|
| Node 0 (Understand) | Verbose | Needs context to understand question |
| Node 1B (Requirements) | Verbose | Needs full context to plan analysis |
| **Node 2 (Profile)** | **Concise** | **Only needs column names - no sample data** |
| Node 3 (Alignment) | N/A | Uses output from Node 2 |
| Node 4 (Code Gen) | Verbose | Needs full context to write code |

### Implementation

#### Created `generate_concise_summary()` in `data_analyzer.py`

```python
def generate_concise_summary(df: pd.DataFrame) -> str:
    """Generate concise summary - NO sample data, NO statistics"""
    summary_parts = []
    
    summary_parts.append(f"Dataset Shape: {df.shape[0]} rows × {df.shape[1]} columns\n")
    summary_parts.append("Columns:")
    
    for col in df.columns:
        dtype = df[col].dtype
        null_count = df[col].isnull().sum()
        
        col_info = f"  - {col} ({dtype})"
        if null_count > 0:
            col_info += f" - {null_count} missing"
        
        summary_parts.append(col_info)
    
    return "\n".join(summary_parts)
```

**Output example:**
```
Dataset Shape: 35000 rows × 10 columns

Columns:
  - customer_id (object)
  - date (object)
  - campaign_group (object)
  - email_opened (int64)
  ...
```

Clean, simple, no special characters that break JSON!

#### Modified `node_2_profile_data()` in `langgraph_agent.py`

```python
def node_2_profile_data(state: MVPAgentState) -> dict:
    # Build CONCISE summary for profiling (not verbose!)
    concise_summary = "Available datasets:\n\n"
    for ds_id, ds_info in state["datasets"].items():
        concise_summary += f"Dataset '{ds_id}' ({ds_info['name']}):\n"
        concise_summary += generate_concise_summary(ds_info['df'])  # ← CONCISE!
        concise_summary += "\n\n"
    
    # Pass concise summary to profile_data()
    data_profile = profile_data(
        state["question"],
        state["requirements"],
        concise_summary,  # ← Not state["data_summary"]!
        remediation_guidance
    )
    
    return {"data_profile": data_profile}
```

---

## Visual Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ DATASET UPLOAD                                              │
│ ─────────────────────────────────────────────────────────── │
│ CSV File → generate_data_summary() → VERBOSE SUMMARY       │
│            (includes stats + sample rows)                   │
│                                                             │
│ Stored in: st.session_state.datasets[id]['data_summary']   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ USER ASKS QUESTION                                          │
│ ─────────────────────────────────────────────────────────── │
│ app.py builds combined_summary from all datasets            │
│ → Uses VERBOSE summaries                                    │
│                                                             │
│ Passed to LangGraph as: initial_state["data_summary"]      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ NODE 0: UNDERSTAND QUESTION                                 │
│ ─────────────────────────────────────────────────────────── │
│ Input: state["data_summary"] (VERBOSE)                      │
│ Output: needs_data_work = True/False                        │
│ ✅ Works fine - just reads summary                          │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ NODE 1B: FORMULATE REQUIREMENTS                             │
│ ─────────────────────────────────────────────────────────── │
│ Input: state["data_summary"] (VERBOSE)                      │
│ Output: requirements = {variables_needed, analysis_type}    │
│ ✅ Works fine - generates simple JSON                       │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ NODE 2: PROFILE DATA                                        │
│ ─────────────────────────────────────────────────────────── │
│ BEFORE FIX:                                                 │
│   Input: state["data_summary"] (VERBOSE with sample data)  │
│   ❌ FAILED: JSON parsing error from special characters    │
│                                                             │
│ AFTER FIX:                                                  │
│   node_2_profile_data() builds CONCISE summary on-the-fly  │
│   Input: concise_summary (column names only)               │
│   ✅ WORKS: Clean JSON generation                          │
│                                                             │
│ Output: data_profile = {available_columns, is_suitable}    │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ NODE 3: ALIGNMENT CHECK                                     │
│ ─────────────────────────────────────────────────────────── │
│ Input: requirements + data_profile                          │
│ Output: aligned = True/False                                │
│ ✅ Works - uses Node 2's output                             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ NODE 4: GENERATE CODE                                       │
│ ─────────────────────────────────────────────────────────── │
│ Input: state["data_summary"] (VERBOSE - needs full context)│
│ Output: Python code for merge/analysis                      │
│ ✅ Works - needs detailed context to write good code        │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Insight

**The problem wasn't that the summary was wrong - it was that we were using the WRONG TYPE of summary for Node 2.**

- **Node 2's job**: Check if required columns exist
- **What it needs**: Just column names and types
- **What it was getting**: Full dataset with sample rows and statistics
- **Result**: LLM tried to include sample data in JSON → parsing error

**The fix**: Give Node 2 only what it needs - a clean, concise list of columns.

---

## Why This Matters for Multi-Dataset Merges

For merge operations specifically:

1. **Node 1B** identifies: "We need to merge on `customer_id`"
2. **Node 2** checks: "Does `customer_id` exist in BOTH datasets?"
   - With verbose summary: ❌ JSON parsing error
   - With concise summary: ✅ "Yes, found in both datasets"
3. **Node 3** verifies: "Requirements aligned with data"
4. **Node 4** generates: `pd.merge(df1, df2, on='customer_id')`

The concise summary makes Node 2 reliable, which makes the entire merge workflow work.

---

## Summary

| Aspect | Before Fix | After Fix |
|--------|-----------|-----------|
| **Node 2 Input** | Verbose summary (1000s of chars) | Concise summary (100s of chars) |
| **Sample Data** | Included in summary | Excluded from summary |
| **JSON Generation** | ❌ Malformed (unterminated strings) | ✅ Clean and parseable |
| **Merge Operations** | ❌ Failed at Node 2 | ✅ Works end-to-end |
| **Root Cause** | Special chars in sample data | Removed sample data from profiling |

The fix is elegant: **Use the right tool for the job.** Node 2 doesn't need sample data, so don't give it sample data.
