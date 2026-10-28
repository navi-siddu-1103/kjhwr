// In dev, "/api" is proxied to the backend. In production set VITE_API_URL.
const BASE: string = import.meta.env.VITE_API_URL ?? "";

export interface SeriesPoint {
  startTime: string;
  actual: number | null;
  forecast: number | null;
  publishTime: string | null;
  horizon_hours: number | null;
  error_mw: number | null;
}

export interface Metrics {
  n_evaluated: number;
  n_missing_forecast: number;
  mae_mw?: number;
  rmse_mw?: number;
  bias_mw?: number;
  relative_mae_pct?: number;
  p90_abs_error_mw?: number;
  p90_shortfall_mw?: number;
}

export interface HorizonRow { bucket: string; mae_mw: number; n: number }
export interface BreakdownRow { group: string | number; bias: number; mae: number; n: number }
export interface DailyRow {
  date: string; mean_actual: number; mean_forecast: number; mae: number; bias: number;
}
export interface BufferRow { local_hour: number; p90_shortfall_mw: number; n: number }
export interface Buffer {
  overall_p90_shortfall_mw: number;
  message: string;
  caveat: string;
  by_hour: BufferRow[];
}

export interface Query {
  start: string;
  end: string;
  cutoff_hour: number;
}

async function get<T>(path: string, params: Record<string, string | number>): Promise<T> {
  const qs = new URLSearchParams(
    Object.entries(params).map(([k, v]) => [k, String(v)])
  ).toString();
  const res = await fetch(`${BASE}${path}?${qs}`);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ? JSON.stringify(body.detail) : `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const fetchSeries = (q: Query) => get<SeriesPoint[]>("/api/series", { ...q });
export const fetchMetrics = (q: Query) => get<Metrics>("/api/metrics", { ...q });
export const fetchHorizon = (q: Query) => get<HorizonRow[]>("/api/error-by-horizon", { ...q });
export const fetchBreakdown = (q: Query, by: "hour" | "wind_level") =>
  get<BreakdownRow[]>("/api/error-breakdown", { ...q, by });
export const fetchDaily = (q: Query) => get<DailyRow[]>("/api/daily-summary", { ...q });
export const fetchBuffer = (q: Query) => get<Buffer>("/api/buffer-recommendation", { ...q });