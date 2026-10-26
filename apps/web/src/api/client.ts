const BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export const api = {
  async get<T>(path: string): Promise<T> {
    const r = await fetch(`${BASE}/api/v1${path}`)
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}: ${await r.text()}`)
    return r.json()
  },
  async post<T>(path: string, body: unknown): Promise<T> {
    const r = await fetch(`${BASE}/api/v1${path}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}: ${await r.text()}`)
    return r.json()
  },
}

/** Drivers the scenario simulator accepts (from the v2 contract). */
export const IntervenableDrivers = [
  'dpt_cov', 'san_basic', 'water_basic', 'gdp_pc', 'chexp_pctgdp',
  'phys_1k', 'nurses_1k', 'meas_cov', 'urb_pct',
] as const

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

export type VulnerabilityRow = {
  iso3: string; country: string; region: string
  composite: number | null; band: string | null
  components: Record<string, number | null>
  component_vintages: Record<string, number | null>
  missing_components: string[]; complete: boolean
  jackknife_max_delta: number | null
}
export type VulnerabilityData = {
  composite_version: string; dataset_version: string; year: number
  weights: Record<string, number>; bands: Record<string, string>
  framework_note: string; rows: VulnerabilityRow[]
}
export type AlertRow = {
  iso3: string; country: string; year: number
  p_gt_70: number; p_gt_50: number; yhat: number
  lo90: number; hi90: number; reasons: string[]
}
export type AlertsData = {
  as_of_year: number; rule: string; honesty_note: string; rows: AlertRow[]
}
export type ComparisonColumn = {
  iso3: string; country: string; region: string
  u5m_latest: number | null; u5m_year: number
  trend_10y_pp: number | null
  forecast_2025: number | null; forecast_2027: number | null
  interval_2025: number[] | null; p_gt_70_2025: number | null
  driver_coverage_pct: number | null
  vulnerability_band: string | null
  vulnerabilities: Record<string, number | null>
}
export type ScenarioRequest = {
  iso3: string
  interventions: { driver: string; delta: number }[]
}
export type ScenarioResponse = {
  iso3: string; target_year: number; model_version: string | null
  baseline_registered: number | null; yhat_registered_replay: number
  yhat_scenario: number; delta: number
  interval_90_scenario: number[]; interval_note: string
  interventions_applied: Record<string, { base: number; delta: number; scenario_value: number }>
  interventions_unit_note: string; honesty_note: string
}

export function riskLevel(u5m: number): 'critical' | 'high' | 'elevated' | 'moderate' {
  if (u5m >= 100) return 'critical'
  if (u5m >= 70) return 'high'
  if (u5m >= 40) return 'elevated'
  return 'moderate'
}

/** Warm risk ramp on the vintage paper theme. */
export const colors = {
  critical: '#7c2d12', high: '#b45309', elevated: '#ca8a04', moderate: '#2e5339',
}
export const riskFill: Record<keyof typeof colors, string> = {
  critical: 'rgba(124, 45, 18, .85)',
  high: 'rgba(180, 83, 9, .85)',
  elevated: 'rgba(202, 138, 4, .8)',
  moderate: 'rgba(46, 83, 57, .82)',
}

declare global { interface Window { Plotly: any } }
export function plotly(): any { return window.Plotly }

/** Load Plotly on demand (map/forecast pages only) — keeps the landing page fast. */
let plotlyPromise: Promise<any> | null = null
export function loadPlotly(): Promise<any> {
  if (window.Plotly) return Promise.resolve(window.Plotly)
  if (plotlyPromise) return plotlyPromise
  plotlyPromise = new Promise((resolve, reject) => {
    const s = document.createElement('script')
    s.src = 'https://cdn.plot.ly/plotly-2.35.2.min.js'
    s.charset = 'utf-8'
    s.onload = () => resolve(window.Plotly)
    s.onerror = () => { plotlyPromise = null; reject(new Error('Plotly failed to load')) }
    document.head.appendChild(s)
  })
  return plotlyPromise
}
