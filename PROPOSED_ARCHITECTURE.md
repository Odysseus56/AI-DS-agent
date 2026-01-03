# MVP LangGraph Architecture - Robust Data Scientist Agent

**Created**: January 2, 2026  
**Status**: Finalized for Implementation  
**Version**: MVP 1.0

---

## Graph Structure

```mermaid
flowchart TD
    START([User Question]) --> NODE0[Node 0: Question Understanding]
    
    NODE0 -->|Explanation only| NODE1A[Node 1A: Provide Explanation]
    NODE0 -->|Data work needed| NODE1B[Node 1B: Formulate Requirements]
    
    NODE1A --> END([Final Output])
    
    NODE1B --> NODE2[Node 2: Data Summary & Profiling]
    NODE2 --> NODE3[Node 3: Alignment Check]
    
    NODE3 -->|Aligned| NODE4[Node 4: Generate & Execute Code]
    NODE3 -->|Gap in requirements<br/>iterations < 2| NODE1B
    NODE3 -->|Gap in data understanding<br/>iterations < 2| NODE2
    NODE3 -->|Cannot align<br/>iterations >= 2| NODE1A
    
    NODE4 -->|Code attempts < 2<br/>& execution failed| NODE4
    NODE4 -->|Success or<br/>attempts >= 2| NODE5[Node 5: Evaluate Results]
    
    NODE5 -->|Valid & sensible| NODE6[Node 6: Explain Results]
    NODE5 -->|Issues detected| NODE5A[Node 5a: Remediation Planning]
    
    NODE5A -->|Code error<br/>total_remediations < 3| NODE4
    NODE5A -->|Wrong approach<br/>total_remediations < 3| NODE1B
    NODE5A -->|Data issue<br/>total_remediations < 3| NODE2
    NODE5A -->|Max attempts exceeded| NODE6
    
    NODE6 --> END
    
    style START fill:#e1f5e1
    style END fill:#ffe1e1
    style NODE0 fill:#e1e5ff
    style NODE1A fill:#e1f9ff
    style NODE1B fill:#fff4e1
    style NODE2 fill:#ffe6cc
    style NODE3 fill:#f0e1ff
    style NODE4 fill:#fff9e1
    style NODE5 fill:#ffe6f0
    style NODE5A fill:#ffcccc
    style NODE6 fill:#e1f9ff
```

---

## Node Specifications

### **Node 0: Question Understanding**

**Purpose**: Determine if question needs explanation only or data work

**Inputs**:
- `question`: User's question
- `data_summary`: Available datasets summary

**LLM Prompt**:
```python
Analyze the user's question and determine if it requires data analysis or just conceptual explanation.

Examples:
- "What is a p-value?" → explanation_only
- "What's the average age?" → data_work
- "Show me age distribution" → data_work
- "Explain what correlation means" → explanation_only

Return JSON:
{
  "needs_data_work": true/false,
  "reasoning": "..."
}
```

**Outputs**:
- `needs_data_work`: boolean
- `reasoning`: string

**Routing**:
- If `needs_data_work = false` → **Node 1A**
- If `needs_data_work = true` → **Node 1B**

---

### **Node 1A: Provide Explanation**

**Purpose**: Answer conceptual/explanation questions or explain limitations

**Inputs**:
- `question`: User's question
- `data_summary`: Context (if relevant)
- `alignment_check`: Alignment issues (if coming from Node 3)

**LLM Prompt**:
```python
You are a data science educator explaining concepts to business users.

Question: {question}

Provide a clear, concise explanation using:
- Plain language suitable for non-technical audiences
- Concrete examples when helpful
- Practical context for business decisions

If this is explaining a limitation (data doesn't support the question):
- Clearly state what's missing
- Suggest alternatives if possible
```

**Outputs**:
- `explanation`: Final explanation text
- `final_output`: Complete output package

**Routing**: → **END**

---

### **Node 1B: Formulate Requirements**

**Purpose**: Define what's needed to answer the question

**Inputs**:
- `question`: User's question
- `data_summary`: Available datasets
- `remediation_plan`: Guidance from Node 5a (if retrying)

**LLM Prompt**:
```python
You are a data scientist planning an analysis. Define requirements to answer this question.

Question: {question}
Available Data: {data_summary}

Specify:
1. VARIABLES NEEDED: Which columns/features are required?
2. DATA CONSTRAINTS: What data quality is needed? (e.g., no missing values in X, Y must be numeric)
3. ANALYSIS APPROACH: What type of analysis? (descriptive stats, visualization, correlation, regression, etc.)
4. SUCCESS CRITERIA: What output would answer the question?

Return JSON:
{
  "variables_needed": ["col1", "col2", ...],
  "constraints": ["constraint1", "constraint2", ...],
  "analysis_type": "descriptive/visualization/correlation/regression/classification/...",
  "success_criteria": "what the output should contain",
  "reasoning": "why this approach"
}
```

**Outputs**:
- `requirements`: Dictionary with variables, constraints, analysis_type, success_criteria

**Routing**: → **Node 2**

---

### **Node 2: Data Summary & Profiling**

**Purpose**: Examine data to understand what's actually available

**Inputs**:
- `question`: User's question
- `requirements`: What we need (from Node 1B)
- `datasets`: Actual dataframes
- `data_summary`: Pre-computed summary
- `remediation_plan`: Guidance from Node 5a (if retrying)

**LLM Prompt**:
```python
You are examining the dataset to profile what's available for this analysis.

Question: {question}
Requirements: {requirements}
Dataset Summary: {data_summary}

Profile the data:
1. AVAILABLE COLUMNS: Which required columns exist?
2. DATA QUALITY: Missing values, data types, value ranges for relevant columns
3. LIMITATIONS: What's missing or problematic?
4. SUITABILITY: Can this data support the required analysis?

Return JSON:
{
  "available_columns": ["col1", "col2", ...],
  "missing_columns": ["col3", ...],
  "data_quality": {
    "col1": "description of quality",
    "col2": "description of quality"
  },
  "limitations": ["limitation1", "limitation2", ...],
  "is_suitable": true/false,
  "reasoning": "..."
}
```

**Outputs**:
- `data_profile`: Dictionary with available columns, quality, limitations, suitability

**Note**: Future enhancement - This node may need to execute code to profile data when the pre-computed summary is insufficient.

**Routing**: → **Node 3**

---

### **Node 3: Alignment Check**

**Purpose**: Verify data can satisfy requirements; iterate if not

**Inputs**:
- `requirements`: What we need
- `data_profile`: What we have
- `alignment_iterations`: Current iteration count

**LLM Prompt**:
```python
Check if the available data can satisfy the analysis requirements.

Requirements: {requirements}
Data Profile: {data_profile}

Determine:
1. ALIGNMENT: Does data satisfy requirements?
2. GAPS: What's missing or misaligned?
3. RECOMMENDATION: What should we do?
   - "proceed" if aligned
   - "revise_requirements" if requirements are too strict/wrong
   - "revise_data_understanding" if we need to look at data differently
   - "cannot_proceed" if fundamentally incompatible

Return JSON:
{
  "aligned": true/false,
  "gaps": ["gap1", "gap2", ...],
  "recommendation": "proceed/revise_requirements/revise_data_understanding/cannot_proceed",
  "reasoning": "..."
}
```

**Outputs**:
- `alignment_check`: Dictionary with aligned status, gaps, recommendation
- `alignment_iterations`: Incremented counter

**Routing**:
- If `aligned = true` → **Node 4**
- If `recommendation = "revise_requirements"` AND `iterations < 2` → **Node 1B**
- If `recommendation = "revise_data_understanding"` AND `iterations < 2` → **Node 2**
- If `iterations >= 2` OR `recommendation = "cannot_proceed"` → **Node 1A** (explain limitation)

---

### **Node 4: Generate & Execute Code**

**Purpose**: Write and run Python code to perform the analysis

**Inputs**:
- `question`: User's question
- `requirements`: Analysis requirements
- `data_profile`: Data context
- `datasets`: Actual dataframes
- `code_attempts`: Current attempt count
- `error`: Previous error (if retrying)
- `remediation_plan`: Guidance from Node 5a (if retrying)

**LLM Prompt (First Attempt)**:
```python
You are an expert data analyst writing Python code to answer this question.

Question: {question}
Requirements: {requirements}
Data Profile: {data_profile}

Write clean, executable Python code using pandas, numpy, and Plotly.

CODE REQUIREMENTS:
- Access datasets using: datasets['dataset_id'] or df (for single dataset)
- Libraries pre-imported: pd, np, plt, px, go, make_subplots, sklearn, scipy, statsmodels
- For visualizations: Store figure in variable 'fig'
- For analysis: Store result in variable 'result'
- Use Plotly for visualizations (plotly_white template)
- Perform actual calculations, never hardcode results

Return ONLY the Python code, no explanations or markdown.
```

**LLM Prompt (Retry)**:
```python
Fix the code that failed with this error.

Question: {question}
Previous Code: {code}
Error: {error}
Remediation Guidance: {remediation_plan}

Analyze the error and generate CORRECTED code.

Return ONLY the fixed Python code, no explanations.
```

**Execution**: Via `code_executor.py:execute_unified_code()`

**Outputs**:
- `code`: Generated/fixed code
- `execution_result`: Output dictionary
- `execution_success`: Boolean
- `error`: Error message (if failed)
- `code_attempts`: Incremented counter

**Routing**:
- If `execution_success = true` → **Node 5**
- If `execution_success = false` AND `code_attempts < 2` → **Node 4** (retry)
- If `execution_success = false` AND `code_attempts >= 2` → **Node 5** (evaluate failure)

---

### **Node 5: Evaluate Results**

**Purpose**: Validate if results are correct and make sense

**Inputs**:
- `question`: User's question
- `requirements`: What we were trying to achieve
- `code`: Executed code
- `execution_result`: Code output
- `execution_success`: Whether code ran
- `error`: Error message (if failed)

**LLM Prompt**:
```python
Evaluate the analysis results for correctness and sensibility.

Question: {question}
Requirements: {requirements}
Code: {code}
Execution Success: {execution_success}
Results: {execution_result}
Error: {error}

Validate:
1. PLAUSIBILITY: Are numbers reasonable? Any impossible values (e.g., correlation > 1)?
2. METHODOLOGY: Was the approach appropriate for the question?
3. COMPLETENESS: Did this actually answer the question?
4. ISSUES: Any errors, red flags, or concerns?

Return JSON:
{
  "is_valid": true/false,
  "issues_found": ["issue1", "issue2", ...],
  "confidence": 0.0-1.0,
  "recommendation": "accept/code_error/wrong_approach/data_issue",
  "reasoning": "..."
}
```

**Outputs**:
- `evaluation`: Dictionary with validity, issues, confidence, recommendation

**Routing**:
- If `is_valid = true` → **Node 6**
- If `is_valid = false` → **Node 5a**

---

### **Node 5a: Remediation Planning**

**Purpose**: Determine root cause and which node to revisit

**Inputs**:
- `question`: User's question
- `evaluation`: Issues identified
- `code`: Current code
- `error`: Error message
- `requirements`: Current requirements
- `data_profile`: Current data understanding
- `total_remediations`: Global counter

**LLM Prompt**:
```python
Determine the root cause of the issue and plan remediation.

Question: {question}
Evaluation Issues: {evaluation}
Code: {code}
Error: {error}

Diagnose:
1. ROOT CAUSE: What's the fundamental problem?
2. ACTION: What should we do?
   - "rewrite_code": Code has bugs or wrong implementation
   - "revise_requirements": We're approaching the problem wrong
   - "reexamine_data": We misunderstood the data structure/quality

Return JSON:
{
  "root_cause": "description",
  "action": "rewrite_code/revise_requirements/reexamine_data",
  "guidance": "specific instructions for the target node",
  "reasoning": "..."
}
```

**Outputs**:
- `remediation_plan`: Dictionary with root_cause, action, guidance
- `total_remediations`: Incremented global counter

**Routing**:
- If `total_remediations >= 3` → **Node 6** (give up gracefully)
- If `action = "rewrite_code"` → **Node 4**
- If `action = "revise_requirements"` → **Node 1B**
- If `action = "reexamine_data"` → **Node 2**

---

### **Node 6: Explain Results**

**Purpose**: Communicate findings to user in plain language

**Inputs**:
- `question`: User's question
- `evaluation`: Analysis evaluation
- `execution_result`: Code output
- `code`: Executed code
- `requirements`: Analysis requirements

**LLM Prompt**:
```python
Explain the analysis results to a business user.

Question: {question}
Evaluation: {evaluation}
Results: {execution_result}
Remediation Attempts: {total_remediations}
Max Attempts Exceeded: {max_attempts_exceeded}

Provide:
1. DIRECT ANSWER: Clear answer to the user's question (or explain what went wrong)
2. KEY FINDINGS: Main insights from the analysis (if successful)
3. CONTEXT: What the numbers mean in practical terms
4. CAVEATS: Any limitations or concerns (if evaluation flagged issues)

If max remediation attempts were exceeded:
- Clearly explain what error occurred
- Describe what we tried to fix it
- Suggest how the user might help resolve it (e.g., clarify question, check data quality)

Use plain language suitable for non-technical audiences.
Be concise but thorough.
```

**Outputs**:
- `explanation`: Final user-facing explanation
- `final_output`: Complete output package with:
  - `explanation`
  - `evaluation`
  - `code`
  - `requirements`
  - `output_type`: "visualization", "analysis", "error", or "explanation"
  - `figures`: Plotly figures (if visualization)
  - `result_str`: Raw execution output

**Routing**: → **END**

---

## State Schema

```python
class MVPAgentState(TypedDict):
    # Input
    question: str
    datasets: dict  # {dataset_id: {name, df, data_summary, ...}}
    data_summary: str
    messages: list
    
    # Node 0
    needs_data_work: bool
    
    # Node 1B
    requirements: Optional[dict]  # {variables_needed, constraints, analysis_type, success_criteria}
    
    # Node 2
    data_profile: Optional[dict]  # {available_columns, data_quality, limitations, is_suitable}
    
    # Node 3
    alignment_check: Optional[dict]  # {aligned, gaps, recommendation}
    alignment_iterations: int  # Max 2
    
    # Node 4
    code: Optional[str]
    execution_result: Optional[dict]
    execution_success: bool
    error: Optional[str]
    code_attempts: int  # Max 2
    
    # Node 5
    evaluation: Optional[dict]  # {is_valid, issues_found, confidence, recommendation}
    
    # Node 5a
    remediation_plan: Optional[dict]  # {root_cause, action, guidance}
    total_remediations: int  # Max 3 (global counter)
    
    # Node 6
    explanation: str
    final_output: dict
```

---

## Routing Functions

```python
def route_from_node_0(state):
    """Route from question understanding"""
    if not state["needs_data_work"]:
        return "node_1a_explain"
    else:
        return "node_1b_requirements"

def route_from_node_3(state):
    """Route from alignment check"""
    if state["alignment_check"]["aligned"]:
        return "node_4_code"
    elif state["alignment_iterations"] >= 2:
        return "node_1a_explain_limitation"
    elif state["alignment_check"]["recommendation"] == "revise_requirements":
        return "node_1b_requirements"
    else:  # revise_data_understanding
        return "node_2_data"

def route_from_node_4(state):
    """Route from code execution"""
    if state["execution_success"] or state["code_attempts"] >= 2:
        return "node_5_evaluate"
    else:
        return "node_4_code"  # Retry

def route_from_node_5(state):
    """Route from evaluation"""
    if state["evaluation"]["is_valid"]:
        return "node_6_explain"
    else:
        return "node_5a_remediation"

def route_from_node_5a(state):
    """Route from remediation planning"""
    if state["total_remediations"] >= 3:
        return "node_6_explain"  # Give up gracefully
    
    action = state["remediation_plan"]["action"]
    if action == "rewrite_code":
        return "node_4_code"
    elif action == "revise_requirements":
        return "node_1b_requirements"
    else:  # reexamine_data
        return "node_2_data"
```

---

## Loop Limits Summary

| Loop | Max Iterations | Behavior When Exceeded |
|------|----------------|------------------------|
| **Alignment Loop** (Node 3 ↔ 1B/2) | 2 | Route to Node 1A (explain limitation) |
| **Code Retry** (Node 4 → 4) | 2 | Proceed to Node 5 with failure |
| **Remediation Loop** (Node 5a → 1B/2/4) | 3 total | Route to Node 6 (explain with caveats) |

---

## Model Configuration

### **Premium Configuration** (Recommended)

Using GPT-5 series for optimal cost-performance balance:

| Node | Model | Input/Output (per 1M tokens) | Rationale |
|------|-------|------------------------------|-----------|
| **Node 0** | `gpt-5-nano` | $0.05 / $0.40 | Simple binary classification |
| **Node 1A** | `gpt-5-mini` | $0.25 / $2.00 | Conceptual explanations |
| **Node 1B** | `gpt-5.1` | $1.25 / $10.00 | Better requirement understanding |
| **Node 2** | `gpt-5-mini` | $0.25 / $2.00 | Data profiling |
| **Node 3** | `gpt-5.1` | $1.25 / $10.00 | Better alignment judgment |
| **Node 4** | `gpt-5.1-codex` | $1.25 / $10.00 | Code-specialized model |
| **Node 5** | `gpt-5.1` | $1.25 / $10.00 | Critical validation gate |
| **Node 5a** | `gpt-5.1` | $1.25 / $10.00 | Root cause diagnosis |
| **Node 6** | `gpt-5-mini` | $0.25 / $2.00 | Final explanation |

**Implementation**:
```python
NODE_MODELS = {
    "node_0": "gpt-5-nano",
    "node_1a": "gpt-5-mini",
    "node_1b": "gpt-5.1",
    "node_2": "gpt-5-mini",
    "node_3": "gpt-5.1",
    "node_4": "gpt-5.1-codex",
    "node_5": "gpt-5.1",
    "node_5a": "gpt-5.1",
    "node_6": "gpt-5-mini",
}
```

**Cost Estimate**: ~$0.014 per question with caching (see below)

---

## Prompt Caching Strategy

### **What is Prompt Caching?**

OpenAI's prompt caching reuses previously processed tokens at a **90% discount** (cached input: $0.125/1M vs standard: $1.25/1M for gpt-5.1). When the same content appears in multiple requests, only the first occurrence pays full price.

### **Why It Matters for Our Architecture**

Our agent reuses context across multiple nodes:
- `data_summary` - Used in Nodes 1B, 2, 3, 4, 5 (5 nodes)
- `requirements` - Used in Nodes 3, 4, 5, 6 (4 nodes)
- `data_profile` - Used in Nodes 3, 4, 5 (3 nodes)

**Without caching**: Each node pays full price for repeated context  
**With caching**: Only first occurrence pays full price, rest pay 10%

### **Cost Impact**

**Typical question flow (Node 0 → 1B → 2 → 3 → 4 → 5 → 6)**:

| Scenario | Cost per Question | Monthly (1000 questions) |
|----------|-------------------|--------------------------|
| Without caching | ~$0.028 | ~$840 |
| With caching | ~$0.014 | ~$420 |
| **Savings** | **50%** | **$420/month** |

### **Implementation Strategy**

**1. Standardize Context Format**:
```python
def create_cached_context(state):
    """Create cacheable context with consistent formatting"""
    parts = []
    
    # Always include in same order for cache hits
    if state.get('data_summary'):
        parts.append(f"=== DATA SUMMARY ===\n{state['data_summary']}")
    
    if state.get('requirements'):
        # Use sorted JSON for consistency
        req_json = json.dumps(state['requirements'], sort_keys=True, indent=2)
        parts.append(f"=== REQUIREMENTS ===\n{req_json}")
    
    if state.get('data_profile'):
        profile_json = json.dumps(state['data_profile'], sort_keys=True, indent=2)
        parts.append(f"=== DATA PROFILE ===\n{profile_json}")
    
    return "\n\n".join(parts)
```

**2. Build Prompts with Cached Context**:
```python
def build_prompt(state, node_type, node_specific_prompt):
    """Build prompt with cacheable context first"""
    cached_context = create_cached_context(state)
    
    # Cached context goes first, then node-specific prompt
    return f"{cached_context}\n\n{node_specific_prompt}"
```

**3. Cache Key Requirements**:
- ✅ Exact text matching (no variations)
- ✅ Consistent ordering (use `sort_keys=True` in JSON)
- ✅ Same formatting (no extra spaces/newlines)
- ✅ Stable across requests

### **Caching by Node**

| Node | Cached Content | Cache Savings |
|------|----------------|---------------|
| Node 0 | None | - |
| Node 1A | None | - |
| Node 1B | `data_summary` | ~0% (first use) |
| Node 2 | `data_summary`, `requirements` | ~40% |
| Node 3 | `data_summary`, `requirements`, `data_profile` | ~60% |
| Node 4 | `data_summary`, `requirements`, `data_profile` | ~60% |
| Node 5 | `data_summary`, `requirements`, `data_profile` | ~60% |
| Node 6 | `requirements`, `data_profile` | ~50% |

### **Monitoring Cache Performance**

Track in logging:
```python
{
    "cache_hit_rate": 0.85,  # 85% of tokens were cached
    "tokens_cached": 8500,
    "tokens_uncached": 1500,
    "cost_saved": 0.014,  # Dollars saved from caching
}
```

---

## Example Execution Flows

### Example 1: Simple Success Path
```python
User: "What's the average customer age?"
  ↓
Node 0 → needs_data_work=true, num_subtasks=1
  ↓
Node 1B → requirements: {variables: ["age"], analysis_type: "descriptive"}
  ↓
Node 2 → data_profile: {available: ["age"], quality: "good"}
  ↓
Node 3 → aligned=true
  ↓
Node 4 → code executes successfully: mean = 42.3
  ↓
Node 5 → is_valid=true (reasonable value)
  ↓
Node 6 → "The average customer age is 42.3 years..."
  ↓
END
```

### Example 2: Alignment Loop
```python
User: "Show correlation between satisfaction and revenue"
  ↓
Node 0 → needs_data_work=true
  ↓
Node 1B → requirements: {variables: ["satisfaction", "revenue"], analysis_type: "correlation"}
  ↓
Node 2 → data_profile: {available: ["satisfaction"], missing: ["revenue"]}
  ↓
Node 3 → aligned=false, recommendation="revise_requirements" (iteration 1)
  ↓
Node 1B → requirements: {variables: ["satisfaction", "sales"], analysis_type: "correlation"}
  ↓
Node 2 → (reuses existing profile)
  ↓
Node 3 → aligned=true
  ↓
[Continue to Node 4...]
```

### Example 3: Remediation Loop
```python
User: "Calculate correlation between age and income"
  ↓
[Nodes 0-3 succeed]
  ↓
Node 4 → code executes: correlation = 1.2
  ↓
Node 5 → is_valid=false (correlation > 1 is impossible!)
  ↓
Node 5a → root_cause="calculation error", action="rewrite_code" (remediation 1)
  ↓
Node 4 → fixed code executes: correlation = 0.72
  ↓
Node 5 → is_valid=true
  ↓
Node 6 → Explain results
  ↓
END
```

### Example 4: Conceptual Question
```python
User: "What is a p-value?"
  ↓
Node 0 → needs_data_work=false
  ↓
Node 1A → Explain p-value concept
  ↓
END
```

### Example 5: Max Remediation Attempts Exceeded
```python
User: "Calculate the trend coefficient"
  ↓
[Nodes 0-3 succeed]
  ↓
Node 4 → code fails (unclear what "trend coefficient" means)
  ↓
Node 5 → is_valid=false
  ↓
Node 5a → action="revise_requirements" (remediation 1)
  ↓
Node 1B → tries to interpret "trend coefficient"
  ↓
[Loop continues through attempts 2 and 3, still unclear]
  ↓
Node 5a → total_remediations=3 (max exceeded)
  ↓
Node 6 → Explain: "I attempted to calculate the trend coefficient but 
         encountered ambiguity. 'Trend coefficient' could refer to:
         - Linear regression slope
         - Time series trend parameter
         - Correlation with time
         Could you clarify which analysis you'd like?"
  ↓
END
```

---

## Implementation Checklist

### Core Architecture
- [ ] Update `langgraph_agent.py` with new node functions (0, 1A, 1B, 2, 3, 4, 5, 5a, 6)
- [ ] Update state schema with new fields (`MVPAgentState`)
- [ ] Implement routing functions with loop counters
- [ ] Add loop limit enforcement (alignment: 2, code: 2, remediation: 3)

### LLM Integration
- [ ] Configure model mapping in `llm_client.py` (`NODE_MODELS` dictionary)
- [ ] Update `llm_client.py` with new LLM prompts for each node
- [ ] Implement `create_cached_context()` function for prompt caching
- [ ] Implement `build_prompt()` function with cached context
- [ ] Test model selection per node

### Prompt Caching
- [ ] Standardize context formatting (JSON with `sort_keys=True`)
- [ ] Implement consistent ordering for cache hits
- [ ] Add cache performance tracking to logging
- [ ] Monitor cache hit rates in production

### Testing
- [ ] Test alignment loop with max iterations
- [ ] Test remediation loop with max iterations
- [ ] Test code retry with max attempts
- [ ] Test graceful failure when limits exceeded
- [ ] Test prompt caching effectiveness
- [ ] Verify cost savings from caching

### Logging & Monitoring
- [ ] Add logging for all routing decisions
- [ ] Log which model is used per node
- [ ] Track cache hit rates and cost savings
- [ ] Log loop iteration counts
- [ ] Update UI to show which node is active

### Documentation
- [ ] Document model selection rationale
- [ ] Document caching strategy
- [ ] Create troubleshooting guide for cache misses

---

**Last Updated**: January 2, 2026  
**Status**: Ready for Implementation
