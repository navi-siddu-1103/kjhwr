import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from app.comparison import actuals_to_hourly, build_comparison

a = pd.read_csv("data/actuals_jan2026.csv", parse_dates=["startTime"])
f = pd.read_csv("data/forecasts_jan2026.csv", parse_dates=["startTime", "publishTime"])
c = build_comparison(a, f, 9).dropna(subset=["forecast"])

print("Mean actual MW:   ", round(c["actual"].mean()))
print("Mean forecast MW: ", round(c["forecast"].mean()))
print("Share of hours over-forecast: %.0f%%" % (100 * (c["error_mw"] > 0).mean()))

c["day"] = c["startTime"].dt.date
daily = c.groupby("day").agg(
    actual=("actual", "mean"), forecast=("forecast", "mean"), bias=("error_mw", "mean")
)
print("\nDaily bias (MW), first/last 5 days and extremes:")
print(daily.round(0).head(5).to_string())
print("...")
print("days with negative bias:", int((daily["bias"] < 0).sum()), "of", len(daily))
print("min / max daily bias:", round(daily["bias"].min()), "/", round(daily["bias"].max()))

c["wind_level"] = pd.qcut(c["actual"], 3, labels=["low", "medium", "high"])
print("\nBias and MAE by wind level:")
print(c.groupby("wind_level", observed=True)["error_mw"].agg(
    bias="mean", mae=lambda s: s.abs().mean()).round(0))

c["hour"] = c["startTime"].dt.hour
print("\nBias by hour of day (UTC = UK in January):")
print(c.groupby("hour")["error_mw"].mean().round(0).to_string())

# Bias by horizon using ALL forecasts
h = actuals_to_hourly(a)
allf = f.merge(h, on="startTime")
allf["horizon"] = (allf["startTime"] - allf["publishTime"]).dt.total_seconds() / 3600
allf = allf[(allf["horizon"] >= 0) & (allf["horizon"] < 72)]
allf["err"] = allf["generation"] - allf["actual"]
allf["bucket"] = pd.cut(allf["horizon"], [0, 12, 24, 36, 48, 72], right=False)
print("\nBias by horizon bucket (all forecasts):")
print(allf.groupby("bucket", observed=True)["err"].mean().round(0))