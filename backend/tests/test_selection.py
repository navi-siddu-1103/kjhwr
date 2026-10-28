import pandas as pd
import pytest

from app.selection import decision_cutoffs, select_decision_forecasts


def fc(rows):
    df = pd.DataFrame(rows, columns=["startTime", "publishTime", "generation"])
    df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
    df["publishTime"] = pd.to_datetime(df["publishTime"], utc=True)
    return df


def ts(s):
    return pd.Timestamp(s, tz="UTC")


T = "2026-01-10T12:00:00Z"


def test_picks_latest_published_before_cutoff():
    f = fc([
        (T, "2026-01-09T02:30:00Z", 100),
        (T, "2026-01-09T07:30:00Z", 200),
        (T, "2026-01-09T09:30:00Z", 300),  # after the 09:00 cutoff
    ])
    out = select_decision_forecasts(f, cutoff_hour=9)
    assert out["forecast"].tolist() == [200]
    assert out["horizon_hours"].iloc[0] == pytest.approx(28.5)


def test_changing_cutoff_changes_selection():
    f = fc([
        (T, "2026-01-09T07:30:00Z", 200),
        (T, "2026-01-09T09:30:00Z", 300),
    ])
    assert select_decision_forecasts(f, 10)["forecast"].tolist() == [300]


def test_publish_exactly_at_cutoff_is_included():
    f = fc([
        (T, "2026-01-09T08:00:00Z", 1),
        (T, "2026-01-09T09:00:00Z", 2),
    ])
    assert select_decision_forecasts(f, 9)["forecast"].tolist() == [2]


def test_forecast_after_cutoff_is_ignored():
    f = fc([(T, "2026-01-09T09:30:00Z", 300)])
    assert select_decision_forecasts(f, 9).empty


def test_target_without_eligible_forecast_is_absent():
    f = fc([
        (T, "2026-01-09T07:30:00Z", 200),
        ("2026-01-10T13:00:00Z", "2026-01-09T09:30:00Z", 999),  # too late
    ])
    out = select_decision_forecasts(f, 9)
    assert out["startTime"].tolist() == [ts(T)]


def test_bst_cutoff_is_one_hour_earlier_in_utc():
    # 11:00 BST on 1 Apr -> D = 1 Apr, cutoff = 31 Mar 09:00 BST = 08:00 UTC
    t = "2026-04-01T10:00:00Z"
    f = fc([(t, "2026-03-31T08:00:00Z", 1), (t, "2026-03-31T08:30:00Z", 2)])
    assert select_decision_forecasts(f, 9)["forecast"].tolist() == [1]


def test_uk_local_date_differs_from_utc_date():
    # 23:00 UTC on 31 Mar is 00:00 BST on 1 Apr -> delivery day is 1 Apr
    s = pd.Series([ts("2026-03-31T23:00:00Z"), ts("2026-03-31T22:00:00Z")])
    c = decision_cutoffs(s, 9)
    assert c.iloc[0] == ts("2026-03-31T08:00:00Z")  # D = 1 Apr
    assert c.iloc[1] == ts("2026-03-30T08:00:00Z")  # D = 31 Mar


def test_clocks_change_day_cutoff():
    # 29 Mar 2026 is the GMT->BST day. D-1 (28 Mar) is still GMT.
    s = pd.Series([ts("2026-03-29T11:00:00Z")])
    assert decision_cutoffs(s, 9).iloc[0] == ts("2026-03-28T09:00:00Z")


def test_invalid_cutoff_hour_raises():
    s = pd.Series([ts(T)])
    with pytest.raises(ValueError):
        decision_cutoffs(s, 3)