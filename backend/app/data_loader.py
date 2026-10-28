"""Load the cached CSVs once and build comparison frames per cutoff hour."""
from __future__ import annotations

from functools import lru_cache

import pandas as pd

from app.comparison import actuals_to_hourly, build_comparison
from app.config import DATA_DIR
from app.selection import UK_TZ


@lru_cache(maxsize=1)
def load_raw() -> tuple[pd.DataFrame, pd.DataFrame]:
    actuals = pd.read_csv(DATA_DIR / "actuals_jan2026.csv", parse_dates=["startTime"])
    forecasts = pd.read_csv(
        DATA_DIR / "forecasts_jan2026.csv", parse_dates=["startTime", "publishTime"]
    )
    return actuals, forecasts


@lru_cache(maxsize=16)
def comparison_for(cutoff_hour: int) -> pd.DataFrame:
    """Hourly actual vs decision-time forecast, with UK-local date/hour columns."""
    actuals, forecasts = load_raw()
    c = build_comparison(actuals, forecasts, cutoff_hour)
    local = c["startTime"].dt.tz_convert(UK_TZ)
    c["local_date"] = local.dt.date
    c["local_hour"] = local.dt.hour
    return c


@lru_cache(maxsize=1)
def hourly_actual_frame() -> pd.DataFrame:
    actuals, _ = load_raw()
    h = actuals_to_hourly(actuals)
    h["local_date"] = h["startTime"].dt.tz_convert(UK_TZ).dt.date
    return h