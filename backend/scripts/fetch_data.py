"""Download Elexon wind actuals (FUELHH) and forecasts (WINDFOR) for Jan 2026.

Saves cleaned CSVs to backend/data/. Run: python backend/scripts/fetch_data.py
"""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

BASE = "https://data.elexon.co.uk/bmrs/api/v1/datasets"
DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Decisions for delivery days 1-31 Jan 2026 are made on 31 Dec - 30 Jan,
# so forecasts published from 30 Dec 2025 to 30 Jan 2026 are relevant.
ACTUALS_START, ACTUALS_END = date(2026, 1, 1), date(2026, 1, 31)
FORECAST_PUB_START, FORECAST_PUB_END = date(2025, 12, 30), date(2026, 1, 30)


def get_json(url: str, params: dict, retries: int = 3) -> list[dict]:
    """GET with simple retry/backoff; raises after the last failed attempt."""
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, params=params, timeout=60)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            print(f"  attempt {attempt}/{retries} failed: {exc}")
            if attempt == retries:
                raise
            time.sleep(2 * attempt)
    return []


def fetch_actuals() -> pd.DataFrame:
    """Wind actuals, half-hourly, fetched in weekly chunks."""
    frames = []
    cur = ACTUALS_START
    while cur <= ACTUALS_END:
        chunk_end = min(cur + timedelta(days=6), ACTUALS_END)
        print(f"FUELHH {cur} -> {chunk_end}")
        rows = get_json(
            f"{BASE}/FUELHH/stream",
            {
                "settlementDateFrom": cur.isoformat(),
                "settlementDateTo": chunk_end.isoformat(),
                "fuelType": "WIND",
            },
        )
        frames.append(pd.DataFrame(rows))
        cur = chunk_end + timedelta(days=1)

    df = pd.concat(frames, ignore_index=True)
    df = df[df["fuelType"] == "WIND"]
    df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
    df = (
        df[["startTime", "settlementDate", "settlementPeriod", "generation"]]
        .drop_duplicates("startTime")
        .sort_values("startTime")  # API returns newest first
        .reset_index(drop=True)
    )
    return df


def fetch_forecasts() -> pd.DataFrame:
    """All WINDFOR forecasts, fetched one publish-day at a time."""
    frames = []
    cur = FORECAST_PUB_START
    while cur <= FORECAST_PUB_END:
        frm = datetime(cur.year, cur.month, cur.day, tzinfo=timezone.utc)
        to = frm + timedelta(days=1)
        print(f"WINDFOR published {cur}")
        rows = get_json(
            f"{BASE}/WINDFOR/stream",
            {
                "publishDateTimeFrom": frm.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "publishDateTimeTo": to.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )
        frames.append(pd.DataFrame(rows))
        cur += timedelta(days=1)

    df = pd.concat(frames, ignore_index=True)
    for col in ("startTime", "publishTime"):
        df[col] = pd.to_datetime(df[col], utc=True)
    df = (
        df[["startTime", "publishTime", "generation"]]
        .drop_duplicates(["startTime", "publishTime"])
        .sort_values(["startTime", "publishTime"])
        .reset_index(drop=True)
    )
    return df


def validate(actuals: pd.DataFrame, forecasts: pd.DataFrame) -> None:
    """Print a short data-quality report."""
    print("\n=== VALIDATION ===")
    expected = pd.date_range(
        "2026-01-01T00:00Z", "2026-01-31T23:30Z", freq="30min"
    )
    missing = expected.difference(pd.DatetimeIndex(actuals["startTime"]))
    print(f"Actuals rows: {len(actuals)} (expected {len(expected)}), missing: {len(missing)}")
    if len(missing):
        print("  first missing:", list(missing[:5]))
    print(f"Actuals null generation: {actuals['generation'].isna().sum()}")
    print(f"Forecast rows: {len(forecasts)}")
    print(f"Distinct publish times: {forecasts['publishTime'].nunique()}")
    print(f"Forecast startTime range: {forecasts['startTime'].min()} -> {forecasts['startTime'].max()}")
    print(f"Forecast non-hourly startTimes: {(forecasts['startTime'].dt.minute != 0).sum()}")
    print(f"Forecast null generation: {forecasts['generation'].isna().sum()}")
    horizon = (forecasts["startTime"] - forecasts["publishTime"]).dt.total_seconds() / 3600
    print(f"Horizon hours: min {horizon.min():.1f}, max {horizon.max():.1f}")


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    actuals = fetch_actuals()
    forecasts = fetch_forecasts()
    validate(actuals, forecasts)
    actuals.to_csv(DATA_DIR / "actuals_jan2026.csv", index=False)
    forecasts.to_csv(DATA_DIR / "forecasts_jan2026.csv", index=False)
    print(f"\nSaved CSVs to {DATA_DIR}")


if __name__ == "__main__":
    main()