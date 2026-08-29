import pandas as pd
import os

print("1. Hiding ML models...")
if os.path.exists('models/trained'):
    os.rename('models/trained', 'models/trained_backup')
    print("   Done! System will now fall back to the dataset.")

print("2. Modifying dataset (synthetic_water_data.csv)...")
file_path = 'data/raw/synthetic_water_data.csv'
df = pd.read_csv(file_path)

# The last column is Duration, the second is Hour.
dur_col = df.columns[-1]
hour_col = df.columns[1]

# Erase all old pump run times
df[dur_col] = 0.0

# Set the pump to run for 90 minutes at 11:00 AM every day
df.loc[df[hour_col].astype(str).str.startswith('11:'), dur_col] = 90.0

df.to_csv(file_path, index=False)
print("   Done! The dataset now says the pump always runs at 11:00 AM.")
