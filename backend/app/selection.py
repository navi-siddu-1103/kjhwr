"""Decision-time forecast selection.

For delivery day D (UK local date), the day-ahead purchase decision is made on D-1
at `cutoff_hour` UK local time. Only forecasts published at or before that cutoff
could be used, and we pick the latest of them for each target hour.
"""
from __future__ import annotations

import pandas as pd

UK_TZ = "Europe/London"
MIN_CUTOFF_HOUR, MAX_CUTOFF_HOUR = 6, 12  # avoids the 01:00-02:00 DST gap


def decision_cutoffs(
    target_times: pd.Series, cutoff_hour: int = 9, tz: str = UK_TZ
) -> pd.Series:
    """Return the UTC decision cutoff for each target time.

    cutoff = (UK local date of target - 1 day) at cutoff_hour:00 UK local time.
    """
    if not MIN_CUTOFF_HOUR <= cutoff_hour <= MAX_CUTOFF_HOUR:
        raise ValueError(
            f"cutoff_hour must be between {MIN_CUTOFF_HOUR} and {MAX_CUTOFF_HOUR}"
        )
    local = target_times.dt.tz_convert(tz)
    delivery_day = local.dt.tz_localize(None).dt.normalize()  # naive local midnight
    cutoff_local = delivery_day - pd.Timedelta(days=1) + pd.Timedelta(hours=cutoff_hour)
    return cutoff_local.dt.tz_localize(tz).dt.tz_convert("UTC")


def select_decision_forecasts(
    forecasts: pd.DataFrame, cutoff_hour: int = 9
) -> pd.DataFrame:
    """For each startTime keep the latest forecast with publishTime <= cutoff.

    Input columns: startTime, publishTime, generation (all UTC-aware timestamps).
    Output columns: startTime, publishTime, forecast, cutoff, horizon_hours.
    Targets with no eligible forecast are absent from the output.
    """
    df = forecasts.copy()
    df["cutoff"] = decision_cutoffs(df["startTime"], cutoff_hour)
    df = df[df["publishTime"] <= df["cutoff"]]
    df = df.sort_values(["startTime", "publishTime"])
    df = df.drop_duplicates("startTime", keep="last")  # latest publish per target
    df["horizon_hours"] = (df["startTime"] - df["publishTime"]).dt.total_seconds() / 3600
    return df.rename(columns={"generation": "forecast"})[
        ["startTime", "publishTime", "forecast", "cutoff", "horizon_hours"]
    ].reset_index(drop=True)
