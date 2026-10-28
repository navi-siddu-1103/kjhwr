from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
DAY = {"start": "2026-01-10", "end": "2026-01-10"}


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_series_matches_hand_verified_row():
    rows = client.get("/api/series", params=DAY).json()
    assert len(rows) == 24
    noon = rows[12]  # 12:00 UK/UTC in January
    assert noon["forecast"] == 7945
    assert noon["horizon_hours"] == 28.5


def test_metrics_has_expected_keys():
    m = client.get("/api/metrics", params=DAY).json()
    for key in ("mae_mw", "rmse_mw", "bias_mw", "p90_shortfall_mw"):
        assert key in m


def test_rejects_dates_outside_january():
    r = client.get("/api/series", params={"start": "2026-02-01", "end": "2026-02-02"})
    assert r.status_code == 422


def test_rejects_start_after_end():
    r = client.get("/api/series", params={"start": "2026-01-10", "end": "2026-01-09"})
    assert r.status_code == 422


def test_rejects_bad_cutoff_hour():
    r = client.get("/api/series", params={**DAY, "cutoff_hour": 3})
    assert r.status_code == 422


def test_breakdowns_and_summary_work():
    full = {"start": "2026-01-01", "end": "2026-01-31"}
    assert len(client.get("/api/error-breakdown", params={**full, "by": "hour"}).json()) == 24
    assert len(client.get("/api/error-breakdown", params={**full, "by": "wind_level"}).json()) == 3
    assert len(client.get("/api/daily-summary", params=full).json()) == 31
    assert len(client.get("/api/error-by-horizon", params=full).json()) == 5
    assert "by_hour" in client.get("/api/buffer-recommendation", params=full).json()