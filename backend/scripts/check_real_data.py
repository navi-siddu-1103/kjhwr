import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from app.comparison import actuals_to_hourly, build_comparison
from app.metrics import compute_metrics, error_by_horizon

a = pd.read_csv("data/actuals_jan2026.csv", parse_dates=["startTime"])
f = pd.read_csv("data/forecasts_jan2026.csv", parse_dates=["startTime", "publishTime"])

for h in (9, 10):
    c = build_comparison(a, f, h)
    print(f"\n=== cutoff {h}:00 ===")
    m = compute_metrics(c)
    print({k: round(v, 1) if isinstance(v, float) else v for k, v in m.items()})

c = build_comparison(a, f, 9)
print("\nSample (Jan 10, 12:00-14:00):")
mask = (c.startTime >= "2026-01-10 12:00Z") & (c.startTime <= "2026-01-10 14:00Z")
print(c[mask].to_string())

print("\nMAE by horizon:")
print(error_by_horizon(f, actuals_to_hourly(a)))