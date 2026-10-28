"""Wind Forecast Analyzer API."""
from __future__ import annotations

import json
from datetime import date
from typing import Literal

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.config import DEFAULT_CUTOFF_HOUR, MAX_DATE, MIN_DATE
from app.data_loader import comparison_for, hourly_actual_frame, load_raw
from app.metrics import compute_metrics, error_by_horizon

app = FastAPI(title="Wind Forecast Analyzer API", version="0.1.0")
# Read-only public data, so a permissive CORS policy is acceptable for this pilot.
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"]
)


def date_range(
    start: date = Query(..., description="First delivery date (UK), 2026-01-01 or later"),
    end: date = Query(..., description="Last delivery date (UK), 2026-01-31 or earlier"),
) -> tuple[date, date]:
    if start > end:
        raise HTTPException(422, "start must be on or before end")
    if start < MIN_DATE or end > MAX_DATE:
        raise HTTPException(422, f"dates must be within {MIN_DATE} and {MAX_DATE}")
    return start, end


def records(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> JSON-safe list of dicts (NaN becomes null, times become ISO)."""
    return json.loads(df.to_json(orient="records", date_format="iso"))


def comparison_slice(rng: tuple[date, date], cutoff_hour: int) -> pd.DataFrame:
    start, end = rng
    c = comparison_for(cutoff_hour)
    return c[(c["local_date"] >= start) & (c["local_date"] <= end)]


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/series")
def series(
    rng: tuple[date, date] = Depends(date_range),
    cutoff_hour: int = Query(DEFAULT_CUTOFF_HOUR, ge=6, le=12),
) -> list[dict]:
    """Hourly actual vs the forecast that was available at the decision cutoff."""
    cols = ["startTime", "actual", "forecast", "publishTime", "horizon_hours", "error_mw"]
    return records(comparison_slice(rng, cutoff_hour)[cols])


@app.get("/api/metrics")
def metrics(
    rng: tuple[date, date] = Depends(date_range),
    cutoff_hour: int = Query(DEFAULT_CUTOFF_HOUR, ge=6, le=12),
) -> dict:
    return compute_metrics(comparison_slice(rng, cutoff_hour))


@app.get("/api/error-by-horizon")
def horizon(rng: tuple[date, date] = Depends(date_range)) -> list[dict]:
    """MAE by lead time, using ALL forecasts for targets in the range."""
    start, end = rng
    h = hourly_actual_frame()
    h = h[(h["local_date"] >= start) & (h["local_date"] <= end)]
    _, forecasts = load_raw()
    return records(error_by_horizon(forecasts, h[["startTime", "actual"]]))


@app.get("/api/error-breakdown")
def breakdown(
    by: Literal["hour", "wind_level"],
    rng: tuple[date, date] = Depends(date_range),
    cutoff_hour: int = Query(DEFAULT_CUTOFF_HOUR, ge=6, le=12),
) -> list[dict]:
    c = comparison_slice(rng, cutoff_hour).dropna(subset=["forecast"]).copy()
    if by == "hour":
        key = c["local_hour"].rename("group")
    else:
        if len(c) < 3:
            raise HTTPException(422, "not enough data to split by wind level")
        # rank first so tied values never break the tercile edges
        key = pd.qcut(
            c["actual"].rank(method="first"), 3, labels=["low", "medium", "high"]
        ).rename("group")
    g = c.groupby(key, observed=True).agg(
        bias=("error_mw", "mean"), mae=("abs_error", "mean"), n=("error_mw", "count")
    )
    return records(g.reset_index())


@app.get("/api/daily-summary")
def daily_summary(
    rng: tuple[date, date] = Depends(date_range),
    cutoff_hour: int = Query(DEFAULT_CUTOFF_HOUR, ge=6, le=12),
) -> list[dict]:
    c = comparison_slice(rng, cutoff_hour).dropna(subset=["forecast"])
    g = c.groupby("local_date").agg(
        mean_actual=("actual", "mean"),
        mean_forecast=("forecast", "mean"),
        mae=("abs_error", "mean"),
        bias=("error_mw", "mean"),
    )
    g.index = g.index.astype(str)
    return records(g.rename_axis("date").reset_index())


def _p90_shortfall(errors: pd.Series) -> float:
    return max(0.0, float(errors.quantile(0.90)))


@app.get("/api/buffer-recommendation")
def buffer_recommendation(
    rng: tuple[date, date] = Depends(date_range),
    cutoff_hour: int = Query(DEFAULT_CUTOFF_HOUR, ge=6, le=12),
) -> dict:
    """Per hour of day: MW by which wind fell short of forecast on 1 in 10 days."""
    c = comparison_slice(rng, cutoff_hour).dropna(subset=["forecast"])
    g = c.groupby("local_hour")["error_mw"].agg(
        p90_shortfall_mw=_p90_shortfall, n="count"
    )
    overall = _p90_shortfall(c["error_mw"]) if len(c) else 0.0
    return {
        "overall_p90_shortfall_mw": overall,
        "message": (
            f"On 10% of hours, wind fell short of the forecast by at least "
            f"{overall:,.0f} MW."
        ),
        "caveat": "Based on one month of data (January 2026); treat as indicative.",
        "by_hour": records(g.reset_index()),
    }