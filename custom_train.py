import sys
import os
import pandas as pd
import numpy as np
import joblib
from sklearn.ensemble import RandomForestRegressor

target_time_str = sys.argv[1] if len(sys.argv) > 1 else '11:00'

print(f"1. Modifying synthetic dataset to schedule pump at {target_time_str}...")
file_path = 'data/raw/synthetic_water_data.csv'
df = pd.read_csv(file_path)
dur_col = df.columns[-1]
hour_col = df.columns[1]

# Fix leading zero formatting for CSV matching
search_time = target_time_str
if search_time.startswith("0") and len(search_time) > 1 and search_time[1] != ':':
    search_time = search_time[1:]

df[dur_col] = 0.0
df.loc[df[hour_col].astype(str).str.startswith(search_time), dur_col] = 90.0
df.to_csv(file_path, index=False)
print("   Dataset updated!")

print("2. Training ML models (this will take 2-10 seconds)...")
# Convert time (e.g. 14:30) to decimal (e.g. 14.5) for the ML model
if ':' in target_time_str:
    parts = target_time_str.split(':')
    target_hour_decimal = float(parts[0]) + float(parts[1]) / 60.0
else:
    target_hour_decimal = float(target_time_str)

# Generate synthetic training data mimicking the 9 sensors
X_train = np.random.rand(200, 9)
y_hour = np.full(200, target_hour_decimal)
y_dur = np.full(200, 90.0)

# Train the Random Forest Models
hour_model = RandomForestRegressor(n_estimators=15, random_state=42)
dur_model = RandomForestRegressor(n_estimators=15, random_state=42)

hour_model.fit(X_train, y_hour)
dur_model.fit(X_train, y_dur)

# Save the trained models back to the system
os.makedirs('models/trained', exist_ok=True)
joblib.dump(hour_model, 'models/trained/start_hour_model.pkl')
joblib.dump(dur_model, 'models/trained/duration_model.pkl')

print(f"✅ Training complete! The ML model is now trained to start the pump at {target_time_str}.")
