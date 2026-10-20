const BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export const api = {
  async get<T>(path: string): Promise<T> {
    const r = await fetch(`${BASE}/api/v1${path}`)
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}: ${await r.text()}`)
    return r.json()
  },
}

export type Atlas = {
  iso3: string; country: string; region: string; year: number
  u5m: number | null; driver_coverage_pct: number
  target_missing: boolean; sparse_hwf_missing: boolean
}
export type Country = { iso3: string; country: string; region: string }
export type SeriesRow = {
  year: number; u5m: number | null; dpt_cov: number | null; gdp_pc: number | null
  san_basic: number | null; water_basic: number | null; urb_pct: number | null
  q_driver_coverage_pct: number
}
export type ShapDriver = { feature: string; shap: number }
export type Forecast = {
  iso3: string; country: string; year: number; horizon: number
  yhat: number; lo90: number; hi90: number; p_gt_70: number; p_gt_50: number
  last_observed_year: number; drivers_default_missing: boolean
  top_drivers_shap: ShapDriver[]
}
export type Health = {
  status: string; dataset_version: string; data_max_year: number
  model_version: string; countries: number
}

export function riskLevel(u5m: number): 'critical' | 'high' | 'elevated' | 'moderate' {
  if (u5m >= 100) return 'critical'
  if (u5m >= 70) return 'high'
  if (u5m >= 40) return 'elevated'
  return 'moderate'
}
export const colors = {
  critical: '#8f1d1a', high: '#c9520f', elevated: '#d1a30f', moderate: '#1d7f5c',
}

declare global { interface Window { Plotly: any } }
export function plotly(): any { return window.Plotly }
