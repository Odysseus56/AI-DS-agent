# Two-Tier Profiling Implementation

## Overview

Implemented adaptive two-tier data profiling for Node 2 to handle datasets with varying column counts efficiently.

## Architecture

### Adaptive Logic

```
IF total_columns <= 30:
    Use Summary B (Detailed Profile) directly
ELSE:
    Step 1: Generate Summary A (Compact Overview) for ALL columns
    Step 2: LLM selects relevant columns (max 40)
    Step 3: Generate Summary B (Detailed Profile) for selected columns
    Step 4: Combine A + B for final profiling
```

### Summary Formats

#### Summary A (Compact Overview)
- **Purpose**: Give LLM breadth - see all columns at a glance
- **Token cost**: ~10 tokens per column
- **Content**: `column_name (dtype), unique=X, mean=Y, missing=Z%`
- **Example**:
  ```
  customer_id (int64), unique=995, mean=1500.5
  age (int64), unique=68, mean=45.2, missing=5.0%
  income_bracket (object), unique=4, mode='Middle'
  ```

#### Summary B (Detailed Profile)
- **Purpose**: Give LLM depth - detailed quality assessment
- **Token cost**: ~70 tokens per column
- **Content**: Range, mean/std, unique count, top values, smart samples
- **Smart sampling**: head/middle/tail/rare values to catch format inconsistencies
- **Example**:
  ```
  • date (object)
    - Unique: 365
    - Top: '2023-01-15' (5), '2023-02-20' (4)
    - Sample (head/mid/tail/rare): '2023-01-15', '2023-06-15', '12/31/2023', '01/05/2023'
                                     ↑ Detects mixed date formats!
  ```

## Token Budget Analysis

### Small Dataset (≤30 columns)
- **Strategy**: Summary B only
- **Tokens**: ~2,100 (30 columns × 70 tokens)
- **Status**: ✅ Safe

### Large Dataset (100 columns)
- **Strategy**: Summary A (all) + Summary B (selected 40)
- **Tokens**: 
  - Summary A: ~1,000 (100 × 10)
  - Summary B: ~2,800 (40 × 70)
  - Total: ~3,800
- **Status**: ✅ Safe (well under 128K context limit)

## Implementation Details

### New Functions in `data_analyzer.py`

1. **`generate_compact_summary(df)`**
   - Generates Summary A
   - Ultra-compact one-liner per column
   - Includes key statistics (mean, mode, unique count, missing %)

2. **`generate_detailed_profile(df, columns=None)`**
   - Generates Summary B
   - Detailed profiling with smart sampling
   - Can profile all columns or selected subset

### New Function in `llm_client.py`

3. **`select_columns_for_profiling(question, requirements, compact_summary, max_columns=40)`**
   - LLM analyzes Summary A
   - Selects most relevant columns based on:
     - Required columns from requirements
     - Columns with missing data (quality issues)
     - Numeric columns (most analyses use these)
     - ID/key columns (for joins)
   - Returns list of column names

### Updated Logic in `langgraph_agent.py`

4. **`node_2_profile_data(state)`**
   - Adaptive logic based on `total_columns`
   - Small datasets: Direct to Summary B
   - Large datasets: A → Select → B → Combine
   - Prints debug info about profiling strategy

## Benefits

1. **Scalability**: Handles 100+ column datasets without token overflow
2. **Intelligence**: LLM selects relevant columns instead of heuristics
3. **Quality Detection**: Smart sampling catches format inconsistencies
4. **Efficiency**: Only detailed profiling where needed

## Expected Impact on Test Results

This should improve performance on tests that failed due to:

- **B3 (Data Type Issues)**: Sample values will expose mixed date formats
- **B2 (Outliers)**: Min/max sampling will catch extreme values
- **A2 (DiD Analysis)**: Better detection of data quality issues
- **E1 (Complex Viz)**: Format detection for time series

## Configuration

- `LARGE_DATASET_COLUMN_THRESHOLD = 30`: Threshold for two-tier profiling
- `MAX_DETAILED_COLUMNS = 40`: Maximum columns for detailed profiling
- Both configurable in `langgraph_agent.py`

## Model Requirements

- Node 2 uses `gpt-4o-mini` (128K context)
- Current max_tokens: 1000 (sufficient for response)
- Input tokens: ~3,800 max (well within limits)
