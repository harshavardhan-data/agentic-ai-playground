import pandas as pd
import numpy as np
from datetime import date,timedelta

np.random.seed(42)

def daily_range(start,days):
    return [start+timedelta(days=i) for i in range(days)]

# --- Run 1: January, baseline ---
jan = daily_range(date(2026, 1, 1), 31)
df1 = pd.DataFrame({
    "date": jan,
    "region": np.random.choice(["US", "EU", "APAC"], size=31,p=[0.4,0.3,0.3]),
    "revenue": np.random.normal(1000, 50, 31).round(2),
})

# --- Run 2: February, revenue up 25%, EU spike in week 2 ---
feb = daily_range(date(2026, 2, 1), 28)
rev2 = np.random.normal(1250, 60, 28).round(2)
regions2 = np.random.choice(["US", "EU", "APAC"], size=28,p=[0.4,0.3,0.3])
# Inject EU spike days 8-14
for i in range(7,11):
    regions2[i]="EU"
    rev2[i]=np.random.randint(low=3500,high=4000)
df2 = pd.DataFrame({"date": feb, "region": regions2, "revenue": rev2})



# --- Run 3: March, revenue back to baseline, no EU spike ---
mar = daily_range(date(2026, 3, 1), 31)
df3 = pd.DataFrame({
    "date": mar,
    "region": np.random.choice(["US", "EU", "APAC"], size=31),
    "revenue": np.random.normal(1250, 50, 31).round(2),
})


df1.to_csv("storage/test_run_1.csv",index=False)
df2.to_csv("storage/test_run_2.csv",index=False)
df3.to_csv("storage/test_run_3.csv",index=False)

