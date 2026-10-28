import { useEffect, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import {
  fetchBreakdown, fetchBuffer, fetchDaily, fetchHorizon, fetchMetrics, fetchSeries,
  type BreakdownRow, type Buffer, type DailyRow, type HorizonRow,
  type Metrics, type Query, type SeriesPoint,
} from "./api";

const fmtMW = (v?: number) => (v === undefined ? "–" : `${Math.round(v).toLocaleString()} MW`);
const fmtVal = (v: unknown) =>
  typeof v === "number" ? `${Math.round(v).toLocaleString()} MW` : "–";
const fmtTime = (iso: string) =>
  new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/London", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
  }).format(new Date(iso));

interface Data {
  series: SeriesPoint[];
  metrics: Metrics;
  horizon: HorizonRow[];
  byHour: BreakdownRow[];
  byWind: BreakdownRow[];
  daily: DailyRow[];
  buffer: Buffer;
}

function Card(props: { label: string; value: string; hint: string }) {
  return (
    <div className="card">
      <div className="label">{props.label}</div>
      <div className="value">{props.value}</div>
      <div className="hint">{props.hint}</div>
    </div>
  );
}

function Panel(props: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <div className="panel">
      <h2>{props.title}</h2>
      {props.note && <p className="note">{props.note}</p>}
      {props.children}
    </div>
  );
}

function downloadCsv(rows: SeriesPoint[], q: Query) {
  const header = [
    "startTime_utc", "actual_mw", "forecast_mw",
    "forecast_publishTime_utc", "horizon_hours", "error_mw",
  ];
  const lines = rows.map((r) =>
    [r.startTime, r.actual, r.forecast, r.publishTime, r.horizon_hours, r.error_mw]
      .map((v) => v ?? "")
      .join(",")
  );
  const blob = new Blob([[header.join(","), ...lines].join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `wind_${q.start}_${q.end}_cutoff${q.cutoff_hour}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function BiasMaeChart(props: { rows: BreakdownRow[]; xLabel: string }) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={props.rows}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="group" label={{ value: props.xLabel, position: "insideBottom", offset: -4 }} />
        <YAxis tickFormatter={(v: number) => `${Math.round(v)}`} />
        <Tooltip formatter={fmtVal} />
        <Legend verticalAlign="top" />
        <Bar dataKey="mae" name="MAE" fill="#1f77b4" />
        <Bar dataKey="bias" name="Bias" fill="#e8710a" />
      </BarChart>
    </ResponsiveContainer>
  );
}

type SortKey = keyof DailyRow;

export default function App() {
  const [query, setQuery] = useState<Query>({
    start: "2026-01-01", end: "2026-01-31", cutoff_hour: 9,
  });
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>("date");
  const [sortAsc, setSortAsc] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([
      fetchSeries(query), fetchMetrics(query), fetchHorizon(query),
      fetchBreakdown(query, "hour"), fetchBreakdown(query, "wind_level"),
      fetchDaily(query), fetchBuffer(query),
    ])
      .then(([series, metrics, horizon, byHour, byWind, daily, buffer]) => {
        if (!cancelled) setData({ series, metrics, horizon, byHour, byWind, daily, buffer });
      })
      .catch((e: Error) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [query]);

  const set = (patch: Partial<Query>) => setQuery((q) => ({ ...q, ...patch }));

  const sortedDaily = data
    ? [...data.daily].sort((a, b) => {
        const x = a[sortKey], y = b[sortKey];
        const cmp = typeof x === "string" ? x.localeCompare(String(y)) : Number(x) - Number(y);
        return sortAsc ? cmp : -cmp;
      })
    : [];

  const clickSort = (key: SortKey) => {
    if (key === sortKey) setSortAsc(!sortAsc);
    else { setSortKey(key); setSortAsc(true); }
  };

  const m = data?.metrics;

  return (
    <div className="page">
      <h1>Wind Forecast Analyzer</h1>
      <p className="sub">
        GB national wind generation: the forecast available when day-ahead purchase
        decisions are made, versus what was actually generated.
      </p>

      <div className="controls">
        <label>From (delivery day)
          <input type="date" min="2026-01-01" max="2026-01-31" value={query.start}
            onChange={(e) => set({ start: e.target.value })} />
        </label>
        <label>To (delivery day)
          <input type="date" min="2026-01-01" max="2026-01-31" value={query.end}
            onChange={(e) => set({ end: e.target.value })} />
        </label>
        <label>Decision cutoff on the day before (UK time)
          <select value={query.cutoff_hour}
            onChange={(e) => set({ cutoff_hour: Number(e.target.value) })}>
            {[6, 7, 8, 9, 10, 11, 12].map((h) => (
              <option key={h} value={h}>{String(h).padStart(2, "0")}:00</option>
            ))}
          </select>
        </label>
        <button className="btn" disabled={!data} onClick={() => data && downloadCsv(data.series, query)}>
          Export CSV
        </button>
        {loading && <span className="muted">Loading…</span>}
      </div>

      {error && (
        <div className="error">
          Could not load data: {error}{" "}
          <button className="btn" onClick={() => setQuery({ ...query })}>Retry</button>
        </div>
      )}

      {m && (
        <div className="cards">
          <Card label="Mean absolute error" value={fmtMW(m.mae_mw)}
            hint="Typical size of the miss, in either direction" />
          <Card label="RMSE" value={fmtMW(m.rmse_mw)}
            hint="Like MAE but penalises large misses more" />
          <Card label="Bias" value={fmtMW(m.bias_mw)}
            hint="Positive = forecast was too high on average" />
          <Card label="P90 shortfall" value={fmtMW(m.p90_shortfall_mw)}
            hint="On 1 in 10 hours wind fell short of forecast by at least this much" />
          <Card label="Relative MAE"
            value={m.relative_mae_pct === undefined ? "–" : `${m.relative_mae_pct.toFixed(1)}%`}
            hint="MAE as a share of average actual output" />
        </div>
      )}

      {data && (
        <div className="stack">
          <Panel title="Actual vs decision-time forecast"
            note="The forecast shown is the latest one published before the cutoff on the day before delivery.">
            {data.series.length === 0 ? (
              <p className="muted">No data for this selection.</p>
            ) : (
              <ResponsiveContainer width="100%" height={380}>
                <LineChart data={data.series}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="startTime" tickFormatter={fmtTime} minTickGap={60} />
                  <YAxis tickFormatter={(v: number) => `${Math.round(v / 1000)} GW`} />
                  <Tooltip labelFormatter={(l) => fmtTime(String(l))} formatter={fmtVal} />
                  <Legend />
                  <Line type="monotone" dataKey="actual" name="Actual" stroke="#1f77b4"
                    dot={false} strokeWidth={2} />
                  <Line type="monotone" dataKey="forecast" name="Forecast (at cutoff)"
                    stroke="#e8710a" dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </Panel>

          <Panel title="Buffer recommendation"
            note="Suggested MW cushion by hour of day, from the signed forecast error.">
            <div className="callout">
              <strong>{data.buffer.message}</strong>
              <div className="caveat">{data.buffer.caveat}</div>
            </div>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={data.buffer.by_hour}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="local_hour" label={{ value: "Hour of day (UK)", position: "insideBottom", offset: -4 }} />
                <YAxis tickFormatter={(v: number) => `${Math.round(v)}`} />
                <Tooltip formatter={fmtVal} />
                <Bar dataKey="p90_shortfall_mw" name="P90 shortfall" fill="#e8710a" />
              </BarChart>
            </ResponsiveContainer>
          </Panel>

          <div className="grid2">
            <Panel title="Error by forecast lead time"
              note="All forecasts, grouped by how far ahead they were published.">
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={data.horizon}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="bucket" />
                  <YAxis tickFormatter={(v: number) => `${Math.round(v)}`} />
                  <Tooltip formatter={fmtVal} />
                  <Bar dataKey="mae_mw" name="MAE" fill="#1f77b4" />
                </BarChart>
              </ResponsiveContainer>
            </Panel>
            <Panel title="Error by wind level"
              note="Hours split into low / medium / high thirds of actual output.">
              <BiasMaeChart rows={data.byWind} xLabel="Wind level" />
            </Panel>
          </div>

          <Panel title="Error by hour of day (UK)">
            <BiasMaeChart rows={data.byHour} xLabel="Hour of day" />
          </Panel>

          <Panel title="Daily summary" note="Click a column heading to sort.">
            <div className="tablewrap">
              <table>
                <thead>
                  <tr>
                    {([["date", "Date"], ["mean_actual", "Mean actual"], ["mean_forecast", "Mean forecast"],
                      ["mae", "MAE"], ["bias", "Bias"]] as [SortKey, string][]).map(([k, label]) => (
                      <th key={k} onClick={() => clickSort(k)}>
                        {label}{k === sortKey ? (sortAsc ? " ▲" : " ▼") : ""}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sortedDaily.map((d) => (
                    <tr key={d.date}>
                      <td>{d.date}</td>
                      <td>{fmtMW(d.mean_actual)}</td>
                      <td>{fmtMW(d.mean_forecast)}</td>
                      <td>{fmtMW(d.mae)}</td>
                      <td>{fmtMW(d.bias)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>
      )}

      <footer>
        Data: Elexon BMRS (FUELHH, WINDFOR), January 2026. Forecasts are hourly, so
        actuals are averaged to hourly for comparison. Bias = forecast minus actual.
      </footer>
    </div>
  );
}