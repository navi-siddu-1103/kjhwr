"""Align half-hourly actuals with hourly forecasts and compute errors."""
from __future__ import annotations

import pandas as pd

from app.selection import select_decision_forecasts


def actuals_to_hourly(actuals: pd.DataFrame) -> pd.DataFrame:
    """Average the two half-hours (hh:00, hh:30) of each hour.

    Hours that do not have both half-hours are dropped rather than guessed.
    """
    df = actuals.copy()
    df["hour"] = df["startTime"].dt.floor("h")
    grouped = df.groupby("hour")["generation"].agg(["mean", "count"])
    grouped = grouped[grouped["count"] == 2]
    return (
        grouped["mean"].rename("actual").rename_axis("startTime").reset_index()
    )


def build_comparison(
    actuals: pd.DataFrame, forecasts: pd.DataFrame, cutoff_hour: int = 9
) -> pd.DataFrame:
    """Hourly actual vs decision-time forecast.

    error_mw = forecast - actual (positive = over-forecast, i.e. wind fell short).
    Hours with no eligible forecast keep NaN so they can be counted, not hidden.
    """
    hourly = actuals_to_hourly(actuals)
    selected = select_decision_forecasts(forecasts, cutoff_hour)
    out = hourly.merge(selected, on="startTime", how="left")
    out["error_mw"] = out["forecast"] - out["actual"]
    out["abs_error"] = out["error_mw"].abs()
    return out
