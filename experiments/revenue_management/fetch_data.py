import pandas as pd
import numpy as np
import seaborn as sns
from pathlib import Path
import json

def fetch_and_prepare_data():
    print("Fetching open flight data...")
    # Load flights dataset from seaborn (commonly used open dataset)
    df = sns.load_dataset('flights')
    
    # We will synthetically scale this up to simulate modern RM data
    # by adding ticket classes, stochastic demand, and pricing features.
    
    # Expand the dataset to simulate 1000 individual flights per month
    expanded_rows = []
    
    print("Expanding dataset to simulate Revenue Management features...")
    for idx, row in df.iterrows():
        base_passengers = row['passengers']
        # Simulate 30 flights for this month
        for day in range(1, 31):
            # Stochastic capacity constraints
            capacity = np.random.choice([150, 200, 250, 300])
            
            # Demand varies by day of week and month
            demand_multiplier = np.random.normal(1.0, 0.2)
            actual_demand = int(base_passengers * demand_multiplier)
            
            # Pricing features (Base fares)
            base_economy = np.random.uniform(100, 300)
            base_business = base_economy * np.random.uniform(2.5, 4.0)
            
            # No-show probability (critical for overbooking hypotheses)
            no_show_prob = np.random.beta(2, 20)  # Mean around 10%
            
            expanded_rows.append({
                'year': row['year'],
                'month': row['month'],
                'day': day,
                'capacity': capacity,
                'base_demand': actual_demand,
                'base_price_economy': round(base_economy, 2),
                'base_price_business': round(base_business, 2),
                'no_show_prob': round(no_show_prob, 4)
            })
            
    expanded_df = pd.DataFrame(expanded_rows)
    
    output_dir = Path("experiments/revenue_management")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    csv_path = output_dir / "simulated_rm_data.csv"
    expanded_df.to_csv(csv_path, index=False)
    print(f"Data saved to {csv_path} with {len(expanded_df)} simulated flights.")
    
    # Save a small json sample for the LLMs to read
    sample_json = expanded_df.head(5).to_dict(orient="records")
    with open(output_dir / "data_schema_sample.json", "w") as f:
        json.dump(sample_json, f, indent=2)

if __name__ == "__main__":
    fetch_and_prepare_data()
