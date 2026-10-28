# Wind Forecast Analyzer

A pilot web app for a UK energy utility's day-ahead power purchasing team. It shows the
wind generation forecast that was actually available when the purchase decision had to be
made, and quantifies how accurate those forecasts were.

- **Live app:** PASTE_FRONTEND_URL
- **Live API docs:** https://backend-kappa-seven-84.vercel.app/docs

## The problem

Power for delivery day D is bought on day D-1, before the day-ahead auction closes. The
buyer needs to know how much to procure beyond wind generation, so they must rely on the
wind forecast available *at that moment*, and they need to know how wrong it tends to be.

## Key idea: decision-time forecast

For every target hour, the app selects the **latest forecast published at or before the
decision cutoff** on D-1 (default 09:00 UK time, configurable from 06:00 to 12:00). Later
forecasts are ignored, because the buyer could not have seen them. This logic lives in
`backend/app/selection.py` and is unit tested, including the cutoff boundary and BST/GMT cases.

## Data

Elexon BMRS only, national-level wind, January 2026 delivery days:

- Actuals: `FUELHH` (filtered to `fuelType == WIND`), half-hourly.
- Forecasts: `WINDFOR`, hourly targets, published irregularly (about every 2-3 hours).

The data was downloaded once with `backend/scripts/fetch_data.py` and the CSVs are committed
in `backend/data/`, so the deployed API does not call Elexon at request time.

## Repository layout

```
backend/
  app/
    main.py          FastAPI app and endpoints
    config.py        date limits and defaults
    data_loader.py   loads the cached CSVs, builds per-cutoff comparison frames
    selection.py     decision-time forecast selection (core logic)
    comparison.py    hourly alignment of actuals and forecasts, error calculation
    metrics.py       MAE, RMSE, bias, percentiles, error by lead time
  scripts/
    fetch_data.py       downloads and validates Elexon data
    check_real_data.py  prints metrics from the real data for manual checking
    diagnose_bias.py    breaks the forecast bias down by day, wind level, hour, horizon
  data/              cached actuals and forecasts (CSV)
  tests/             pytest unit and API tests
  Dockerfile, requirements.txt, pytest.ini
frontend/
  src/               React + TypeScript (App.tsx, api.ts, index.css)
  nginx.conf         serves the build and proxies /api to the backend in Docker
  Dockerfile, vite.config.ts
docker-compose.yml   runs both services
```

## How to run

### With Docker

```bash
docker compose up --build
```

Open http://localhost:3000 (the API is on http://localhost:8000, docs at `/docs`).

### Without Docker

Backend (Python 3.12):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

Frontend (Node 22):

```bash
cd frontend
npm install
npm run dev
```

The dev server proxies `/api` to `http://127.0.0.1:8000`. For a deployed build, set
`VITE_API_URL` to the backend URL at build time.

### Tests

```bash
cd backend
python -m pytest -q
```

### Refreshing the data

```bash
python backend/scripts/fetch_data.py
```

## API

| Endpoint | Purpose |
| --- | --- |
| `GET /api/series` | hourly actual vs decision-time forecast |
| `GET /api/metrics` | MAE, RMSE, bias, relative MAE, P90/P95 error, P90 shortfall |
| `GET /api/error-by-horizon` | MAE by forecast lead time (all forecasts) |
| `GET /api/error-breakdown?by=hour\|wind_level` | bias and MAE by hour of day or wind level |
| `GET /api/daily-summary` | per-day actual, forecast, MAE, bias |
| `GET /api/buffer-recommendation` | P90 shortfall by hour, with a plain-English message |

Common query parameters: `start`, `end` (delivery dates, 2026-01-01 to 2026-01-31) and
`cutoff_hour` (6 to 12).

## Definitions and assumptions

- **Error** = forecast minus actual. Positive means over-forecast: wind delivered less than
  predicted, so the buyer under-bought.
- **Hourly alignment:** forecasts are hourly and actuals are half-hourly, so each pair of
  half-hours is averaged. Hours missing one half-hour are dropped, not filled.
- **MAPE is not used:** wind output can be near zero, which makes percentage errors unstable.
  Relative MAE (MAE divided by mean actual) is shown instead.
- **P90 shortfall:** the 90th percentile of the signed error, floored at zero. On 10% of
  hours, wind fell short of the forecast by at least this much.
- **Cutoff default of 09:00 UK time** is an assumption about when the day-ahead decision is
  made. It is adjustable in the UI.
- **Timezones:** all timestamps are UTC internally and converted with `Europe/London` for
  delivery dates and hours of day.

## Findings and limitations

- In January 2026 the decision-time forecast was on average higher than actual output
  (about 16%), and about 85% of hours were over-forecast. This held at every lead time.
  I have not established why. Possible explanations include differences in what the two
  datasets measure, curtailment, or genuine forecast bias; this needs checking against
  Elexon's dataset documentation.
- Only one month of data is used, so the buffer recommendation is indicative.
- The frontend has no automated tests and there is no CI pipeline yet.
- CORS is open (`*`) because the API serves read-only public data.

## AI tools disclosure

AI tools (Claude by Anthropic) were used to assist in developing this application, including
planning, code generation, debugging and documentation. I reviewed the code and verified the
core selection logic against the raw Elexon data by hand.