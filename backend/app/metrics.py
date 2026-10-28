"""Accuracy metrics for decision-time wind forecasts."""
from __future__ import annotations

import numpy as np
import pandas as pd

HORIZON_BINS = [0, 12, 24, 36, 48, 72]
HORIZON_LABELS = ["0-12h", "12-24h", "24-36h", "36-48h", "48h+"]


def compute_metrics(df: pd.DataFrame) -> dict:
    """Metrics from a comparison frame (needs actual, forecast, error_mw, abs_error).

    MAPE is deliberately not used: wind output can be near zero.
    p90_shortfall_mw is the 90th percentile of signed error floored at 0: on 10% of
    hours wind fell short of the forecast by at least this many MW.
    """
    n_missing = int(df["forecast"].isna().sum())
    valid = df.dropna(subset=["forecast", "actual"])
    if valid.empty:
        return {"n_evaluated": 0, "n_missing_forecast": n_missing}
    err, abs_err = valid["error_mw"], valid["abs_error"]
    mae = float(abs_err.mean())
    return {
        "n_evaluated": int(len(valid)),
        "n_missing_forecast": n_missing,
        "mae_mw": mae,
        "rmse_mw": float(np.sqrt((err**2).mean())),
        "bias_mw": float(err.mean()),
        "relative_mae_pct": mae / float(valid["actual"].mean()) * 100,
        "p50_abs_error_mw": float(abs_err.quantile(0.50)),
        "p90_abs_error_mw": float(abs_err.quantile(0.90)),
        "p95_abs_error_mw": float(abs_err.quantile(0.95)),
        "p90_shortfall_mw": max(0.0, float(err.quantile(0.90))),
    }


def error_by_horizon(
    forecasts: pd.DataFrame, hourly_actuals: pd.DataFrame
) -> pd.DataFrame:
    """MAE per lead-time bucket using ALL forecasts (not just decision-time ones)."""
    df = forecasts.merge(hourly_actuals, on="startTime", how="inner")
    df["horizon_hours"] = (df["startTime"] - df["publishTime"]).dt.total_seconds() / 3600
    df = df[(df["horizon_hours"] >= 0) & (df["horizon_hours"] < HORIZON_BINS[-1])]
    df["bucket"] = pd.cut(
        df["horizon_hours"], HORIZON_BINS, labels=HORIZON_LABELS, right=False
    )
    df["abs_error"] = (df["generation"] - df["actual"]).abs()
    return (
        df.groupby("bucket", observed=True)["abs_error"]
        .agg(mae_mw="mean", n="count")
        .reset_index()
    )
