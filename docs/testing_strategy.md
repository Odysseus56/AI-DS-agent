# AI Data Scientist Agent - Testing Strategy

## Overview

This document outlines a comprehensive testing strategy for stress-testing the AI data scientist agent. The goal is to create a "gauntlet" of scenarios that will expose edge cases, failure modes, and robustness issues in the agent's logic across all nodes (Node 0 through Node 6).

## Current Test Coverage

### Existing Scenarios
1. **basic_stats.json** - Basic descriptive statistics on single dataset
2. **merge_datasets.json** - Simple two-dataset merge operation
3. **visualization.json** - Basic chart generation

### Coverage Gaps
- No multi-step analytical workflows
- No error handling scenarios (missing data, malformed data)
- No complex statistical analyses (hypothesis testing, causal inference)
- No scenarios testing the agent's reasoning under ambiguity
- No scenarios with conflicting or unclear requirements
- Limited testing of Node 3 (alignment check) and Node 5A (remediation)

---

## Testing Dimensions

We will stress-test across these key dimensions:

### 1. **Analytical Complexity**
- Simple descriptive statistics → Complex statistical inference
- Single-step operations → Multi-step analytical workflows
- Clear requirements → Ambiguous/underspecified questions

### 2. **Data Characteristics**
- Clean data → Missing values, outliers, data quality issues
- Single dataset → Multiple datasets with complex relationships
- Small data → Large data (edge of memory limits)
- Simple schema → Complex nested/hierarchical structures

### 3. **Question Clarity**
- Explicit requests → Implicit requirements
- Technical language → Business language requiring translation
- Single question → Compound questions requiring decomposition

### 4. **Node-Specific Stress Tests**
- **Node 0**: Ambiguous questions, conceptual vs. analytical classification
- **Node 1B**: Underspecified requirements, conflicting objectives
- **Node 2**: Missing columns, data type mismatches
- **Node 3**: Misalignment between requirements and available data
- **Node 4**: Code execution errors, edge cases in data
- **Node 5**: Invalid results, partial failures
- **Node 5A**: Remediation planning and recovery
- **Node 6**: Complex explanations, visualization interpretation

---

## Comprehensive Test Scenarios

### Category A: Statistical Analysis & Inference

#### A1. Hypothesis Testing (T-Test)
**Purpose:** Test statistical inference capabilities
**Datasets:** customer_profiles.csv, campaign_results.csv
**Questions:**
1. "Is there a statistically significant difference in average monthly balance between Premium and Standard customer segments?"
2. "Test if digital users have significantly higher account tenure than non-digital users"
3. "Are customers with credit cards more likely to have mortgages?"

**Expected Challenges:**
- Proper statistical test selection
- Assumptions checking (normality, equal variance)
- Interpretation of p-values and confidence intervals

#### A2. Difference-in-Differences (DiD) Analysis
**Purpose:** Test causal inference understanding (core to campaign evaluation)
**Datasets:** customer_profiles.csv, campaign_results.csv
**Questions:**
1. "Perform a difference-in-differences analysis to estimate the causal effect of the email campaign on credit card applications"
2. "What was the incremental lift in card activation rates due to the treatment?"
3. "Calculate the treatment effect on monthly card spend, controlling for customer segment"

**Expected Challenges:**
- Understanding parallel trends assumption
- Proper pre/post period identification
- Interaction term calculation
- Handling time-series structure

#### A3. Segmentation & Clustering
**Purpose:** Test unsupervised learning and pattern detection
**Datasets:** customer_profiles.csv, campaign_results.csv
**Questions:**
1. "Identify natural customer segments based on their behavior and demographics"
2. "Which customer characteristics best predict campaign response?"
3. "Are there hidden subgroups within the Premium segment?"

**Expected Challenges:**
- Feature selection and scaling
- Choosing appropriate number of clusters
- Interpreting cluster characteristics

### Category B: Data Quality & Edge Cases

#### B1. Missing Data Handling
**Purpose:** Test robustness to data quality issues
**Datasets:** customer_profiles_missing.csv (NEW - needs creation)
**Questions:**
1. "What is the average age of customers?" (with 30% missing ages)
2. "How does income bracket relate to credit score?" (with missing values in both)
3. "Should we impute or exclude missing data for this analysis?"

**Expected Challenges:**
- Detecting missing data patterns
- Choosing appropriate handling strategy
- Communicating data quality issues to user

#### B2. Outliers & Anomalies
**Purpose:** Test detection and handling of extreme values
**Datasets:** customer_profiles_outliers.csv (NEW - needs creation)
**Questions:**
1. "What is the average monthly balance?" (with extreme outliers)
2. "Identify customers with unusual account patterns"
3. "Are these outliers errors or legitimate high-value customers?"

**Expected Challenges:**
- Outlier detection methods
- Deciding when to exclude vs. investigate
- Robust statistics (median vs. mean)

#### B3. Data Type Mismatches
**Purpose:** Test handling of schema issues
**Datasets:** campaign_results_messy.csv (NEW - needs creation)
**Questions:**
1. "Show me the trend in card activations over time" (date stored as string)
2. "What's the correlation between spend and revenue?" (numeric stored as string with $ signs)

**Expected Challenges:**
- Type detection and conversion
- Parsing formatted numbers
- Error recovery

### Category C: Multi-Dataset Operations

#### C1. Complex Joins
**Purpose:** Test multi-dataset integration
**Datasets:** customer_profiles.csv, campaign_results.csv, transactions.csv (NEW - needs creation)
**Questions:**
1. "Join customer profiles with campaign results and transaction history to analyze customer lifetime value"
2. "Which customers received the treatment but never made a transaction?"
3. "Merge all three datasets and calculate ROI by customer segment"

**Expected Challenges:**
- Multiple join keys
- One-to-many relationships
- Handling unmatched records

#### C2. Aggregation Across Datasets
**Purpose:** Test cross-dataset calculations
**Datasets:** customer_profiles.csv, campaign_results.csv
**Questions:**
1. "For each customer segment, calculate the average campaign response rate and average monthly balance"
2. "Create a summary table showing treatment vs control performance by segment and digital status"

**Expected Challenges:**
- Proper grouping logic
- Aggregation at different granularities
- Reshaping data for presentation

### Category D: Ambiguous & Underspecified Questions

#### D1. Business Language Translation
**Purpose:** Test requirement interpretation
**Datasets:** customer_profiles.csv, campaign_results.csv
**Questions:**
1. "How well did the campaign perform?" (vague success criteria)
2. "Tell me about our customers" (no specific metric)
3. "Is this campaign worth it?" (requires ROI calculation not explicitly stated)

**Expected Challenges:**
- Inferring implicit requirements
- Choosing appropriate metrics
- Asking clarifying questions vs. making assumptions

#### D2. Compound Questions
**Purpose:** Test question decomposition
**Datasets:** customer_profiles.csv, campaign_results.csv
**Questions:**
1. "Compare treatment vs control groups, break it down by segment, and tell me if the differences are significant"
2. "Show me customer demographics, their campaign response, and recommend which segments to target next"

**Expected Challenges:**
- Breaking into sub-questions
- Maintaining context across steps
- Synthesizing multi-part answers

#### D3. Conceptual Questions
**Purpose:** Test Node 0 routing (should go to Node 1A, not data work)
**Datasets:** Any
**Questions:**
1. "What is a difference-in-differences analysis?"
2. "How should I think about statistical significance?"
3. "Explain the concept of customer lifetime value"

**Expected Challenges:**
- Correctly identifying no data work needed
- Providing clear conceptual explanations
- Not attempting unnecessary analysis

### Category E: Visualization & Communication

#### E1. Complex Visualizations
**Purpose:** Test advanced plotting capabilities
**Datasets:** customer_profiles.csv, campaign_results.csv
**Questions:**
1. "Create a faceted plot showing card spend distribution by segment and treatment group"
2. "Show me a time series of application rates with separate lines for treatment and control"
3. "Make a heatmap of correlation between all numeric variables"

**Expected Challenges:**
- Choosing appropriate chart types
- Handling multiple dimensions
- Proper labeling and formatting

#### E2. Dashboard-Style Multi-Chart
**Purpose:** Test multiple visualizations in one response
**Datasets:** customer_profiles.csv, campaign_results.csv
**Questions:**
1. "Give me a complete campaign performance dashboard with 4-5 key charts"
2. "Show me customer demographics in 3 different ways"

**Expected Challenges:**
- Creating multiple figures
- Coordinating color schemes
- Logical organization

### Category F: Error Recovery & Remediation

#### F1. Forced Code Errors
**Purpose:** Test Node 4 retry logic and Node 5A remediation
**Datasets:** customer_profiles.csv
**Questions:**
1. "Calculate the correlation between age and nonexistent_column" (should trigger error and recovery)
2. "Group by invalid_column and sum monthly_balance" (should detect and remediate)

**Expected Challenges:**
- Error detection
- Root cause identification
- Successful remediation

#### F2. Alignment Failures
**Purpose:** Test Node 3 alignment check
**Datasets:** customer_profiles.csv (only)
**Questions:**
1. "Show me the campaign response rates" (requires campaign_results.csv - not available)
2. "Calculate customer churn rate" (requires temporal data not in static profile)

**Expected Challenges:**
- Detecting data-requirement misalignment
- Clear communication of limitations
- Suggesting alternatives

### Category G: Performance & Scale

#### G1. Large Dataset Operations
**Purpose:** Test performance on larger data
**Datasets:** customer_profiles_large.csv (NEW - 100K+ rows)
**Questions:**
1. "Calculate summary statistics for all numeric columns"
2. "Create a scatter plot of age vs balance for all customers"

**Expected Challenges:**
- Memory management
- Efficient computation
- Visualization performance

#### G2. Complex Computations
**Purpose:** Test computationally intensive operations
**Datasets:** campaign_results.csv
**Questions:**
1. "Calculate rolling 7-day averages for all metrics by customer"
2. "Perform bootstrap resampling (1000 iterations) to estimate confidence intervals for treatment effect"

**Expected Challenges:**
- Code efficiency
- Timeout handling
- Progress communication

### Category H: Domain-Specific Analytics

#### H1. Marketing Analytics
**Purpose:** Test domain knowledge application
**Datasets:** customer_profiles.csv, campaign_results.csv
**Questions:**
1. "Calculate customer acquisition cost and lifetime value by segment"
2. "What's the conversion funnel from email open to card activation?"
3. "Compute the incremental revenue per treatment customer"

**Expected Challenges:**
- Understanding marketing metrics
- Multi-step calculations
- Business context interpretation

#### H2. A/B Test Analysis
**Purpose:** Test experimental design understanding
**Datasets:** customer_profiles.csv, campaign_results.csv
**Questions:**
1. "Was the treatment group properly randomized? Check for balance on observable characteristics"
2. "Calculate statistical power for detecting a 10% lift in applications"
3. "What sample size would we need for 80% power?"

**Expected Challenges:**
- Randomization checks
- Power calculations
- Statistical rigor

---

## Required New Datasets

### 1. customer_profiles_missing.csv
**Purpose:** Test missing data handling
**Modifications:**
- 30% missing values in `age`
- 20% missing in `income_bracket`
- 15% missing in `avg_monthly_balance`
- Random MCAR (Missing Completely At Random) pattern

### 2. customer_profiles_outliers.csv
**Purpose:** Test outlier detection and handling
**Modifications:**
- 5% of `avg_monthly_balance` set to extreme values (10x-100x normal)
- Some negative values in balance (data errors)
- Ages outside reasonable range (e.g., 150, -5)

### 3. campaign_results_messy.csv
**Purpose:** Test data type handling
**Modifications:**
- `date` stored as string in various formats ("2024-07-01", "07/01/2024", "July 1, 2024")
- `monthly_card_spend` stored as string with "$" and "," ("$1,234.56")
- Boolean columns as "Yes"/"No" instead of 0/1
- Some numeric columns with "N/A" strings

### 4. transactions.csv
**Purpose:** Test complex multi-dataset joins
**Schema:**
- `transaction_id`: Unique transaction ID
- `customer_id`: FK to customer_profiles
- `transaction_date`: Date of transaction
- `amount`: Transaction amount
- `merchant_category`: Category of merchant
- `transaction_type`: Credit/Debit

**Size:** ~50K transactions across 5K customers

### 5. customer_profiles_large.csv
**Purpose:** Test performance at scale
**Modifications:**
- Same schema as customer_profiles.csv
- 100,000 rows instead of 5,000

---

## Test Execution Strategy

### Phase 1: Core Functionality (Existing + A1, A2, C1, E1)
**Goal:** Validate basic analytical workflows work end-to-end
**Priority:** HIGH
**Expected Duration:** 10-15 scenarios

### Phase 2: Robustness (B1, B2, B3, F1, F2)
**Goal:** Test error handling and recovery mechanisms
**Priority:** HIGH
**Expected Duration:** 8-12 scenarios

### Phase 3: Complexity (A3, C2, D1, D2, H1, H2)
**Goal:** Test sophisticated analytical reasoning
**Priority:** MEDIUM
**Expected Duration:** 12-15 scenarios

### Phase 4: Edge Cases (D3, E2, G1, G2)
**Goal:** Test boundary conditions and performance
**Priority:** MEDIUM
**Expected Duration:** 6-10 scenarios

---

## Success Criteria

### Per-Scenario Metrics
- **Completion Rate:** Did the agent complete without fatal errors?
- **Correctness:** Are the analytical results accurate?
- **Code Quality:** Is generated code efficient and idiomatic?
- **Explanation Quality:** Are explanations clear and accurate?
- **Recovery:** Did the agent successfully recover from errors?

### Aggregate Metrics
- **Overall Pass Rate:** Target >85% completion across all scenarios
- **Node-Specific Success:** Each node should succeed >90% when reached
- **Remediation Success:** Node 5A should successfully fix >70% of issues
- **Average Execution Time:** Track performance trends

### Qualitative Assessment
- **Reasoning Quality:** Does the agent make sound analytical decisions?
- **User Communication:** Are explanations helpful and clear?
- **Robustness:** Does the agent gracefully handle edge cases?

---

## Log Analysis Plan

After running the test gauntlet, we will analyze logs for:

1. **Common Failure Patterns:** Which types of questions consistently fail?
2. **Node Bottlenecks:** Which nodes have the highest failure rates?
3. **Remediation Effectiveness:** How often does Node 5A successfully recover?
4. **Code Quality Issues:** Are there recurring code generation problems?
5. **Reasoning Gaps:** Where does the agent's analytical reasoning break down?

---

## Next Steps

1. **Create new datasets** (customer_profiles_missing.csv, etc.)
2. **Write scenario JSON files** for each test case (40-50 total scenarios)
3. **Run test gauntlet** in headless mode using test_runner.py
4. **Analyze logs** to identify failure patterns and improvement opportunities
5. **Iterate on agent logic** based on findings
6. **Re-run regression suite** to validate improvements

---

## Appendix: Scenario Naming Convention

Format: `{category}_{number}_{short_name}.json`

Examples:
- `a1_hypothesis_testing.json`
- `b1_missing_data.json`
- `c1_complex_joins.json`
- `d1_business_language.json`

This ensures clear organization and traceability in logs.
