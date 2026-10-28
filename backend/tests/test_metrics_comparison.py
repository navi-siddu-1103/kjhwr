import numpy as np
import pandas as pd
import pytest

from app.comparison import actuals_to_hourly, build_comparison
from app.metrics import compute_metrics


def utc(s):
    return pd.Timestamp(s, tz="UTC")


def test_actuals_hourly_average_and_incomplete_hour_dropped():
    a = pd.DataFrame({
        "startTime": [utc("2026-01-10T10:00Z"), utc("2026-01-10T10:30Z"),
                      utc("2026-01-10T11:00Z")],  # 11:30 missing
        "generation": [100, 200, 300],
    })
    h = actuals_to_hourly(a)
    assert h["startTime"].tolist() == [utc("2026-01-10T10:00Z")]
    assert h["actual"].tolist() == [150]


def test_build_comparison_error_sign_and_missing_forecast():
    a = pd.DataFrame({
        "startTime": [utc("2026-01-10T10:00Z"), utc("2026-01-10T10:30Z"),
                      utc("2026-01-10T11:00Z"), utc("2026-01-10T11:30Z")],
        "generation": [100, 200, 300, 300],
    })
    f = pd.DataFrame({
        "startTime": [utc("2026-01-10T10:00Z")],
        "publishTime": [utc("2026-01-09T07:30Z")],
        "generation": [180],
    })
    out = build_comparison(a, f, 9)
    assert out.loc[0, "error_mw"] == 30          # 180 forecast - 150 actual
    assert np.isnan(out.loc[1, "forecast"])      # 11:00 has no forecast


def test_compute_metrics_hand_calculated():
    df = pd.DataFrame({
        "actual": [100.0] * 4 + [100.0],
        "forecast": [110.0, 90.0, 120.0, 100.0, np.nan],
    })
    df["error_mw"] = df["forecast"] - df["actual"]
    df["abs_error"] = df["error_mw"].abs()
    m = compute_metrics(df)
    assert m["n_evaluated"] == 4 and m["n_missing_forecast"] == 1
    assert m["mae_mw"] == pytest.approx(10.0)
    assert m["rmse_mw"] == pytest.approx(np.sqrt(150))
    assert m["bias_mw"] == pytest.approx(5.0)
    assert m["relative_mae_pct"] == pytest.approx(10.0)
