import pandas as pd
import numpy as np
from datetime import datetime, timedelta

np.random.seed(42)

def generate_customer_profiles(n_customers=5000):
    """
    Generate customer profile data for Santander bank customers.
    Includes demographics, account information, and product holdings.
    """
    
    customer_ids = [f"CUST{str(i).zfill(6)}" for i in range(1, n_customers + 1)]
    
    ages = np.random.normal(45, 15, n_customers).clip(22, 75).astype(int)
    
    income_brackets = np.random.choice(
        ['<30K', '30-50K', '50-75K', '75-100K', '100-150K', '>150K'],
        n_customers,
        p=[0.15, 0.25, 0.25, 0.20, 0.10, 0.05]
    )
    
    account_tenure_months = np.random.exponential(48, n_customers).clip(1, 240).astype(int)
    
    credit_score_tiers = np.random.choice(
        ['Poor', 'Fair', 'Good', 'Very Good', 'Excellent'],
        n_customers,
        p=[0.08, 0.15, 0.35, 0.30, 0.12]
    )
    
    num_products = np.random.poisson(2.5, n_customers).clip(1, 6)
    
    has_checking = np.random.binomial(1, 0.95, n_customers)
    has_savings = np.random.binomial(1, 0.70, n_customers)
    has_mortgage = np.random.binomial(1, 0.35, n_customers)
    has_auto_loan = np.random.binomial(1, 0.25, n_customers)
    has_credit_card = np.zeros(n_customers, dtype=int)
    
    avg_monthly_balance = np.random.lognormal(8.5, 1.2, n_customers).clip(500, 500000).round(2)
    
    digital_user = np.random.binomial(1, 0.65, n_customers)
    
    customer_segments = []
    for i in range(n_customers):
        if avg_monthly_balance[i] > 50000 and credit_score_tiers[i] in ['Excellent', 'Very Good']:
            segment = 'Premium'
        elif avg_monthly_balance[i] > 20000 and num_products[i] >= 3:
            segment = 'Growth'
        elif account_tenure_months[i] < 12:
            segment = 'New'
        else:
            segment = 'Standard'
        customer_segments.append(segment)
    
    df = pd.DataFrame({
        'customer_id': customer_ids,
        'age': ages,
        'income_bracket': income_brackets,
        'account_tenure_months': account_tenure_months,
        'credit_score_tier': credit_score_tiers,
        'num_products': num_products,
        'has_checking': has_checking,
        'has_savings': has_savings,
        'has_mortgage': has_mortgage,
        'has_auto_loan': has_auto_loan,
        'has_credit_card': has_credit_card,
        'avg_monthly_balance': avg_monthly_balance,
        'digital_user': digital_user,
        'customer_segment': customer_segments
    })
    
    return df


def generate_campaign_results(customer_df, campaign_start_date='2024-07-01', months_before=3, months_after=3):
    """
    Generate campaign results data with treatment/control groups.
    Includes pre-campaign and post-campaign periods for DiD analysis.
    """
    
    campaign_start = pd.to_datetime(campaign_start_date)
    start_date = campaign_start - timedelta(days=30 * months_before)
    end_date = campaign_start + timedelta(days=30 * months_after)
    
    n_customers = len(customer_df)
    treatment_prob = np.where(
        (customer_df['customer_segment'].isin(['Premium', 'Growth'])) & 
        (customer_df['digital_user'] == 1),
        0.6,
        0.4
    )
    campaign_group = np.random.binomial(1, treatment_prob, n_customers)
    campaign_group = ['Treatment' if x == 1 else 'Control' for x in campaign_group]
    
    customer_df['campaign_group'] = campaign_group
    
    records = []
    
    current_date = start_date
    month_counter = 0
    
    while current_date <= end_date:
        is_post_campaign = current_date >= campaign_start
        
        for idx, row in customer_df.iterrows():
            customer_id = row['customer_id']
            group = row['campaign_group']
            segment = row['customer_segment']
            digital = row['digital_user']
            credit_tier = row['credit_score_tier']
            
            base_email_open_rate = 0.15 if digital == 1 else 0.08
            base_click_rate = 0.05 if digital == 1 else 0.02
            base_apply_rate = 0.01
            base_activate_rate = 0.70
            
            if group == 'Treatment' and is_post_campaign:
                email_open_rate = base_email_open_rate * 2.5
                click_rate = base_click_rate * 3.0
                apply_rate = base_apply_rate * 4.0
                activate_rate = base_activate_rate * 1.2
            else:
                email_open_rate = base_email_open_rate
                click_rate = base_click_rate
                apply_rate = base_apply_rate
                activate_rate = base_activate_rate
            
            if segment == 'Premium':
                apply_rate *= 1.5
                activate_rate *= 1.1
            elif segment == 'Growth':
                apply_rate *= 1.2
            
            email_opened = np.random.binomial(1, email_open_rate) if group == 'Treatment' else 0
            clicked_offer = np.random.binomial(1, click_rate) if email_opened else 0
            applied_for_card = np.random.binomial(1, apply_rate)
            
            if applied_for_card and credit_tier not in ['Poor']:
                card_activated = np.random.binomial(1, activate_rate)
            else:
                card_activated = 0
            
            if card_activated:
                if segment == 'Premium':
                    monthly_spend = np.random.lognormal(7.5, 0.8)
                elif segment == 'Growth':
                    monthly_spend = np.random.lognormal(6.8, 0.7)
                else:
                    monthly_spend = np.random.lognormal(6.2, 0.6)
                
                monthly_spend = round(monthly_spend, 2)
                revenue = round(monthly_spend * 0.02, 2)
            else:
                monthly_spend = 0.0
                revenue = 0.0
            
            records.append({
                'customer_id': customer_id,
                'date': current_date,
                'campaign_group': group,
                'campaign_start_date': campaign_start_date,
                'email_opened': email_opened,
                'clicked_offer': clicked_offer,
                'applied_for_card': applied_for_card,
                'card_activated': card_activated,
                'monthly_card_spend': monthly_spend,
                'revenue_generated': revenue
            })
        
        current_date += timedelta(days=30)
        month_counter += 1
    
    campaign_df = pd.DataFrame(records)
    
    return campaign_df


def main():
    """Generate and save both datasets."""
    
    print("Generating customer profiles...")
    customer_df = generate_customer_profiles(n_customers=5000)
    customer_df.to_csv('customer_profiles.csv', index=False)
    print(f"✓ Created customer_profiles.csv ({len(customer_df)} customers)")
    
    print("\nGenerating campaign results...")
    campaign_df = generate_campaign_results(
        customer_df,
        campaign_start_date='2024-07-01',
        months_before=3,
        months_after=3
    )
    
    campaign_df_final = campaign_df[['customer_id', 'date', 'campaign_group', 'campaign_start_date',
                                      'email_opened', 'clicked_offer', 'applied_for_card', 
                                      'card_activated', 'monthly_card_spend', 'revenue_generated']]
    
    campaign_df_final.to_csv('campaign_results.csv', index=False)
    print(f"✓ Created campaign_results.csv ({len(campaign_df_final)} records)")
    
    print("\n" + "="*60)
    print("DATASET SUMMARY")
    print("="*60)
    
    print("\n📊 Customer Profiles:")
    print(f"  - Total customers: {len(customer_df):,}")
    print(f"  - Customer segments: {customer_df['customer_segment'].value_counts().to_dict()}")
    print(f"  - Digital users: {customer_df['digital_user'].sum():,} ({customer_df['digital_user'].mean()*100:.1f}%)")
    print(f"  - Avg products per customer: {customer_df['num_products'].mean():.2f}")
    
    print("\n📈 Campaign Results:")
    print(f"  - Total records: {len(campaign_df_final):,}")
    print(f"  - Treatment group: {(campaign_df_final['campaign_group']=='Treatment').sum():,}")
    print(f"  - Control group: {(campaign_df_final['campaign_group']=='Control').sum():,}")
    print(f"  - Date range: {campaign_df_final['date'].min()} to {campaign_df_final['date'].max()}")
    
    post_campaign = campaign_df_final[campaign_df_final['date'] >= '2024-07-01']
    treatment_activations = post_campaign[post_campaign['campaign_group']=='Treatment']['card_activated'].sum()
    control_activations = post_campaign[post_campaign['campaign_group']=='Control']['card_activated'].sum()
    
    print(f"\n💳 Card Activations (Post-Campaign):")
    print(f"  - Treatment group: {treatment_activations:,}")
    print(f"  - Control group: {control_activations:,}")
    print(f"  - Lift: {((treatment_activations/control_activations - 1)*100):.1f}%")
    
    total_revenue = campaign_df_final['revenue_generated'].sum()
    print(f"\n💰 Total Revenue Generated: ${total_revenue:,.2f}")
    
    print("\n" + "="*60)
    print("✅ Sample data generation complete!")
    print("="*60)
    
    print("\n📝 Suggested questions for the AI agent:")
    print("  1. 'Show me the customer segmentation breakdown'")
    print("  2. 'Visualize card activation rates over time by campaign group'")
    print("  3. 'Perform a difference-in-differences analysis of the campaign impact'")
    print("  4. 'What customer segments had the highest response rates?'")
    print("  5. 'Calculate the ROI of the marketing campaign'")


if __name__ == "__main__":
    main()
