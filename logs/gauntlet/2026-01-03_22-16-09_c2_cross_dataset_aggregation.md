# Test Run: C2: Cross-Dataset Aggregation
**Timestamp:** 2026-01-03 22:16:05
**Total Duration:** 65.8 seconds
**Status:** [OK] All questions completed

---

## Scenario Details
- **Name:** C2: Cross-Dataset Aggregation
- **Description:** Tests aggregation and summary statistics across multiple datasets at different granularities
- **Datasets:** customer_profiles, campaign_results
- **Questions:** 3

---

## Question 1: "For each customer segment, calculate the average campaign response rate and average monthly balance"

### Node 0: Understand Question
[OK] Completed

- **needs_data_work:** True
- **reasoning:** The question requires calculations to determine the average campaign response rate and average monthly balance for each customer segment, which involves data analysis.

### Node 1B: Formulate Requirements
[OK] Completed

- **analysis_type:** data_merging
- **variables_needed:** ['customer_id', 'customer_segment', 'avg_monthly_balance', 'email_opened', 'clicked_offer', 'applied_for_card']
- **success_criteria:** A summary table showing the average campaign response rate and average monthly balance for each customer segment.

### Node 2: Profile Data
[OK] Completed

- **available_columns:** ['customer_id', 'customer_segment', 'avg_monthly_balance', 'email_opened', 'clicked_offer', 'applied_for_card']
- **missing_columns:** []
- **is_suitable:** True
- **reasoning:** The required columns exist across the two datasets, and there are no missing values in the key columns needed for the analysis. Both datasets can be merged on 'customer_id', allowing for the calculation of average campaign response rates and average monthly balances per customer segment.

### Node 3: Alignment Check
[OK] Completed

- **aligned:** True
- **recommendation:** proceed

### Node 4: Generate & Execute Code
[OK] Completed

- **execution_success:** True
- **code_attempts:** 1

**Code:**
```python
# Load datasets
customer_profiles = datasets['customer_profiles']
campaign_results = datasets['campaign_results']

# Verify necessary columns exist
required_columns_profiles = ['customer_id', 'customer_segment', 'avg_monthly_balance']
required_columns_campaign = ['customer_id', 'email_opened', 'clicked_offer', 'applied_for_card']

if all(col in customer_profiles.columns for col in required_columns_profiles) and \
   all(col in campaign_results.columns for col in required_columns_campaign):
    
    # Merge datasets on 'customer_id'
    merged_df = pd.merge(customer_profiles, campaign_results, on='customer_id')
    
    # Calculate response rate as the mean of the binary response columns
    merged_df['response_rate'] = merged_df[['email_opened', 'clicked_offer', 'applied_for_card']].mean(axis=1)
    
    # Group by 'customer_segment' and calculate average response rate and average monthly balance
    summary_table = merged_df.groupby('customer_segment').agg(
        avg_response_rate=('response_rate', 'mean'),
        avg_monthly_balance=('avg_monthly_balance', 'mean')
    ).reset_index()
    
    # Store result
    result = summary_table
```

### Node 5: Evaluate Results
[OK] Completed

- **is_valid:** True

### Node 6: Explain Results
[OK] Completed

- **explanation:** 1. **DIRECT ANSWER:**

The analysis successfully calculated the average campaign response rate and average monthly balance for each customer segment.

2. **KEY FINDINGS:**

- **Growth Segment:**
  - Average Monthly Balance: $38,012.44

- **New Segment:**
  - Average Monthly Balance: $7,608.70

- **P...

### Final Output Summary
- **Output Type:** analysis

**Generated Code:**
```python
# Load datasets
customer_profiles = datasets['customer_profiles']
campaign_results = datasets['campaign_results']

# Verify necessary columns exist
required_columns_profiles = ['customer_id', 'customer_segment', 'avg_monthly_balance']
required_columns_campaign = ['customer_id', 'email_opened', 'clicked_offer', 'applied_for_card']

if all(col in customer_profiles.columns for col in required_columns_profiles) and \
   all(col in campaign_results.columns for col in required_columns_campaign):
    
    # Merge datasets on 'customer_id'
    merged_df = pd.merge(customer_profiles, campaign_results, on='customer_id')
    
    # Calculate response rate as the mean of the binary response columns
    merged_df['response_rate'] = merged_df[['email_opened', 'clicked_offer', 'applied_for_card']].mean(axis=1)
    
    # Group by 'customer_segment' and calculate average response rate and average monthly balance
    summary_table = merged_df.groupby('customer_segment').agg(
        avg_response_rate=('response_rate', 'mean'),
        avg_monthly_balance=('avg_monthly_balance', 'mean')
    ).reset_index()
    
    # Store result
    result = summary_table
```

**Explanation:**
1. **DIRECT ANSWER:**

The analysis successfully calculated the average campaign response rate and average monthly balance for each customer segment.

2. **KEY FINDINGS:**

- **Growth Segment:**
  - Average Monthly Balance: $38,012.44

- **New Segment:**
  - Average Monthly Balance: $7,608.70

- **Premium Segment:**
  - Average Monthly Balance: $81,966.28

- **Standard Segment:**
  - Average Monthly Balance: $7,383.59

(Note: The average campaign response rates are not listed in the results provided, but they were calculated during the analysis as part of the requirements.)

3. **CONTEXT:**

These numbers reflect the typical amount of money customers in each segment keep in their accounts on a monthly basis. For example, the Premium segment has a much higher average monthly balance compared to other segments, indicating that customers in this group tend to have more financial resources. This information can help tailor marketing campaigns to better fit the financial behaviors of each s
... (truncated)

**Execution Time:** 19.4s

---

## Question 2: "Create a summary table showing treatment vs control performance by segment and digital user status"

### Node 0: Understand Question
[OK] Completed

- **needs_data_work:** True
- **reasoning:** The question asks for a summary table, which requires data aggregation and analysis to compare treatment and control performance by segment and digital user status.

### Node 1B: Formulate Requirements
[OK] Completed

- **analysis_type:** data_merging
- **variables_needed:** ['customer_id', 'campaign_group', 'email_opened', 'clicked_offer', 'applied_for_card', 'card_activated', 'monthly_card_spend', 'revenue_generated', 'digital_user', 'customer_segment']
- **success_criteria:** A summary table showing the average performance metrics (email_opened, clicked_offer, applied_for_card, card_activated, monthly_card_spend, revenue_generated) grouped by campaign_group, customer_segment, and digital_user status

### Node 2: Profile Data
[OK] Completed

- **available_columns:** ['customer_id', 'campaign_group', 'email_opened', 'clicked_offer', 'applied_for_card', 'card_activated', 'monthly_card_spend', 'revenue_generated', 'digital_user', 'customer_segment']
- **missing_columns:** []
- **is_suitable:** True
- **reasoning:** All required columns exist across the provided datasets. There are no missing values in the key columns required for the analysis. The data types for the binary and numeric variables meet the constraints specified. Therefore, the data is suitable to create the summary table comparing treatment and control performance by segment and digital user status.

### Node 3: Alignment Check
[OK] Completed

- **aligned:** True
- **recommendation:** proceed

### Node 4: Generate & Execute Code
[OK] Completed

- **execution_success:** True
- **code_attempts:** 1

**Code:**
```python
# Load datasets
customer_profiles = datasets['customer_profiles']
campaign_results = datasets['campaign_results']

# Merge datasets on 'customer_id'
merged_df = pd.merge(customer_profiles, campaign_results, on='customer_id')

# Check for required columns before proceeding
required_columns = [
    'customer_id', 'campaign_group', 'email_opened', 'clicked_offer', 
    'applied_for_card', 'card_activated', 'monthly_card_spend', 
    'revenue_generated', 'digital_user', 'customer_segment'
]

if all(column in merged_df.columns for column in required_columns):
    # Group by 'campaign_group', 'customer_segment', and 'digital_user'
    summary_table = merged_df.groupby(['campaign_group', 'customer_segment', 'digital_user']).agg(
        avg_email_opened=('email_opened', 'mean'),
        avg_clicked_offer=('clicked_offer', 'mean'),
        avg_applied_for_card=('applied_for_card', 'mean'),
        avg_card_activated=('card_activated', 'mean'),
        avg_monthly_card_spend=('monthly_card_spend', 'mean'),
        avg_revenue_generated=('revenue_generated', 'mean')
    ).reset_index()

    # Store the result in the variable 'result'
    result = summary_table
else:
    result = "Required columns are missing from the merged dataset."
```

### Node 5: Evaluate Results
[OK] Completed

- **is_valid:** True

### Node 6: Explain Results
[OK] Completed

- **explanation:** 1. **DIRECT ANSWER:** The analysis successfully created a summary table that compares the performance of treatment and control groups across different segments and digital user statuses. This table helps you understand how different groups responded to the treatment versus the control.

2. **KEY FIN...

### Final Output Summary
- **Output Type:** analysis

**Generated Code:**
```python
# Load datasets
customer_profiles = datasets['customer_profiles']
campaign_results = datasets['campaign_results']

# Merge datasets on 'customer_id'
merged_df = pd.merge(customer_profiles, campaign_results, on='customer_id')

# Check for required columns before proceeding
required_columns = [
    'customer_id', 'campaign_group', 'email_opened', 'clicked_offer', 
    'applied_for_card', 'card_activated', 'monthly_card_spend', 
    'revenue_generated', 'digital_user', 'customer_segment'
]

if all(column in merged_df.columns for column in required_columns):
    # Group by 'campaign_group', 'customer_segment', and 'digital_user'
    summary_table = merged_df.groupby(['campaign_group', 'customer_segment', 'digital_user']).agg(
        avg_email_opened=('email_opened', 'mean'),
        avg_clicked_offer=('clicked_offer', 'mean'),
        avg_applied_for_card=('applied_for_card', 'mean'),
        avg_card_activated=('card_activated', 'mean'),
        avg_monthly_card_spend=('monthly_card_spend', 'mean'),
        avg_revenue_generated=('revenue_generated', 'mean')
    ).reset_index()

    # Store the result in the variable 'result'
    result = summary_table
else:
    result = "Required columns are missing from the merged dataset."
```

**Explanation:**
1. **DIRECT ANSWER:** The analysis successfully created a summary table that compares the performance of treatment and control groups across different segments and digital user statuses. This table helps you understand how different groups responded to the treatment versus the control.

2. **KEY FINDINGS:** 
   - The table includes average revenue generated for each combination of campaign group (treatment or control), customer segment, and digital user status.
   - The average revenue varies across segments and whether the customer is a digital user, indicating differences in how these groups responded to the treatment.

3. **CONTEXT:** 
   - "Campaign Group" distinguishes between customers who were part of the treatment (received some kind of intervention, like a special offer) and those in the control group (did not receive the intervention).
   - "Customer Segment" might refer to different categories of customers based on characteristics like demographics or purchasing behavior.
  
... (truncated)

**Execution Time:** 25.3s

---

## Question 3: "What is the relationship between account tenure and card activation rates?"

### Node 0: Understand Question
[OK] Completed

- **needs_data_work:** True
- **reasoning:** The question asks for the relationship between account tenure and card activation rates, which requires analyzing the data to calculate and possibly visualize this relationship.

### Node 1B: Formulate Requirements
[OK] Completed

- **analysis_type:** data_merging
- **variables_needed:** ['customer_id', 'account_tenure_months', 'card_activated']
- **success_criteria:** A merged dataset containing account_tenure_months and card_activated for each customer, along with a correlation analysis or regression model to quantify the relationship.

### Node 2: Profile Data
[OK] Completed

- **available_columns:** ['customer_id', 'account_tenure_months', 'card_activated']
- **missing_columns:** []
- **is_suitable:** True
- **reasoning:** The available datasets contain all the required columns for the analysis. Both 'customer_profiles' and 'campaign_results' datasets include 'customer_id', which can be used to merge the datasets. The 'account_tenure_months' has no missing values and is within the specified range, while 'card_activated' is binary and also has no missing values. Therefore, the data is suitable for performing the required correlation or regression analysis to quantify the relationship between account tenure and card activation rates.

### Node 3: Alignment Check
[OK] Completed

- **aligned:** True
- **recommendation:** proceed

### Node 4: Generate & Execute Code
[OK] Completed

- **execution_success:** True
- **code_attempts:** 1

**Code:**
```python
# Load datasets
customer_profiles = datasets['customer_profiles']
campaign_results = datasets['campaign_results']

# Check if required columns exist in both datasets
required_columns_profiles = ['customer_id', 'account_tenure_months']
required_columns_campaign = ['customer_id', 'card_activated']

if all(column in customer_profiles.columns for column in required_columns_profiles) and \
   all(column in campaign_results.columns for column in required_columns_campaign):

    # Merge datasets on 'customer_id'
    merged_df = pd.merge(customer_profiles[['customer_id', 'account_tenure_months']],
                         campaign_results[['customer_id', 'card_activated']],
                         on='customer_id',
                         how='inner')

    # Ensure 'card_activated' is binary (0 or 1)
    if merged_df['card_activated'].isin([0, 1]).all():
        
        # Perform correlation analysis
        correlation = merged_df['account_tenure_months'].corr(merged_df['card_activated'])
        result = {'correlation_coefficient': correlation}
        
        # Visualize the relationship using a scatter plot
        fig = px.scatter(merged_df, x='account_tenure_months', y='card_activated',
                         title='Relationship between Account Tenure and Card Activation',
                         labels={'account_tenure_months': 'Account Tenure (Months)',
                                 'card_activated': 'Card Activated'},
                         template='plotly_white')
    else:
        result = "Error: 'card_activated' column contains non-binary values."
else:
    result = "Error: Required columns are missing in the datasets."
```

**Visualizations:**

![Visualization 1](data:image/png;base64,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owkYr4AC4xFwATIeLfMqoIACCjREgL/D8pIXzQ58hK3dFiEsPvj4H98J4aN2DQG2UQUUUGAKBWq6AJnCftuUAgoooEAHCaSPNPHxLd4Raaeht/PY2mmeHIsCCtROwAVI7SytSYFGCti2AgoooIACCijQEgIuQFpimuykAgoooEDzCtgzBRRQQIHxCLgAGY+WeRVQQAEFFFBAAQWaR8CetKSAC5CWnDY7rYACCiiggAIKKKBAawq4AGnNeSv22mMFFFBAAQUUUEABBVpCwAVIS0yTnVRAgeYVsGcKKKCAAgooMB4BFyDj0TKvAgoooIACCjSPgD1RQIGWFHAB0pLTZqcVUEABBRRQQAEFFGicwGRadgEyGT3LKqCAAgoooIACCiigwLgEXICMi8vMChQFPFZAAQUUUEABBRQYj4ALkPFomVcBBRRQoHkE7IkCCiigQEsKuABpyWmz0woooIACCiigQOMEbFmByQi4AJmMnmUVUEABBRRQQAEFFFBgXAIuQMbFVczssQIKKKCAAgoooIACCoxHwAXIeLTMq4ACzSNgTxRQQAEFFFCgJQVcgLTktNlpBRRQQAEFGidgywoooMBkBFyATEbPsgoooIACCiiggAIKTJ1AW7TkAqQtptFBKKCAAgoooIACCijQGgIuQFpjnuxlUcBjBRRQQAEFFFBAgZYUcAHSktNmpxVQQIHGCdiyAgoooIACkxFwATIZPcsqoIACCiiggAJTJ2BLCrSFgAuQtphGB6GAAgoooIACCiigQGsItOYCpDVs7aUCCiiggAIKKKCAAgoUBFyAFEA8VECBygKmKqCAAgoooIACkxFwATIZPcsqoIACCigwdQK2pIACCrSFgAuQtphGB6GAAgoooIACCihQPwFrrqWAC5BaalqXAgoooIACCiiggAIKVBRwAVKRx8SigMcKKKCAAgoooIACCkxGwAXIZPQsq4ACCkydgC0poIACCijQFgIuQNpiGh2EAgoooIACCtRPwJoVUKCWAi5AaqlpXQoooIACCiiggAIKKFBRYFwLkIo1maiAAgoooIACCiiggAIKjCHgAmQMIJMVaBIBu6GAAgoooIACCrSFgAuQtphGB6GAAgooUD8Ba1ZAAQUUqKWAC5BaalqXAgoooIACCiigQO0ErKktBVyAtOW0OigFFFBAAQUUUEABBZpT4P8HAAD//2sysZYAAAAGSURBVAMA9vyklJS4hhEAAAAASUVORK5CYII=)


### Node 5: Evaluate Results
[OK] Completed

- **is_valid:** True

### Node 6: Explain Results
[OK] Completed

- **explanation:** 1. DIRECT ANSWER: The analysis found a positive relationship between account tenure and card activation rates. This means that generally, the longer a customer has had their account, the more likely they are to have activated their card.

2. KEY FINDINGS: 
   - There is a positive correlation betwee...

### Final Output Summary
- **Output Type:** visualization

**Generated Code:**
```python
# Load datasets
customer_profiles = datasets['customer_profiles']
campaign_results = datasets['campaign_results']

# Check if required columns exist in both datasets
required_columns_profiles = ['customer_id', 'account_tenure_months']
required_columns_campaign = ['customer_id', 'card_activated']

if all(column in customer_profiles.columns for column in required_columns_profiles) and \
   all(column in campaign_results.columns for column in required_columns_campaign):

    # Merge datasets on 'customer_id'
    merged_df = pd.merge(customer_profiles[['customer_id', 'account_tenure_months']],
                         campaign_results[['customer_id', 'card_activated']],
                         on='customer_id',
                         how='inner')

    # Ensure 'card_activated' is binary (0 or 1)
    if merged_df['card_activated'].isin([0, 1]).all():
        
        # Perform correlation analysis
        correlation = merged_df['account_tenure_months'].corr(merged_df['card_activated'])
        result = {'correlation_coefficient': correlation}
        
        # Visualize the relationship using a scatter plot
        fig = px.scatter(merged_df, x='account_tenure_months', y='card_activated',
                         title='Relationship between Account Tenure and Card Activation',
                         labels={'account_tenure_months': 'Account Tenure (Months)',
                                 'card_activated': 'Card Activated'},
                         template='plotly_white')
    else:
        result = "Error: 'card_activated' column contains non-binary values."
else:
    result = "Error: Required columns are missing in the datasets."
```

**Explanation:**
1. DIRECT ANSWER: The analysis found a positive relationship between account tenure and card activation rates. This means that generally, the longer a customer has had their account, the more likely they are to have activated their card.

2. KEY FINDINGS: 
   - There is a positive correlation between how long customers have had their accounts (tenure) and whether they have activated their cards.
   - The correlation coefficient, which measures the strength and direction of this relationship, indicates a moderate positive correlation. This suggests that as account tenure increases, the likelihood of card activation also tends to increase.

3. CONTEXT: In practical terms, this means that customers who have been with the company longer are more inclined to activate their cards. This could imply trust built over time or simply more opportunities to interact with the product. It might be worthwhile to explore ways to engage newer customers more effectively to boost their activation rates.


... (truncated)

**Execution Time:** 21.0s

---

## Summary
- **Questions Completed:** 3/3
- **Total Execution Time:** 65.8 seconds
- **Result:** [OK] All tests passed