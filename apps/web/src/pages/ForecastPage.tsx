import { useEffect, useRef, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, TrendingUp, Sigma, AlertTriangle, FlaskConical, FileText } from 'lucide-react'
import { api, SeriesRow, Forecast, colors, riskFill, riskLevel, loadPlotly,
         ScenarioResponse, ScenarioRequest, IntervenableDrivers } from '../api/client'

export default function ForecastPage() {
  const { iso3 } = useParams()
  const [series, setSeries] = useState<SeriesRow[] | null>(null)
  const [fc, setFc] = useState<Forecast[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const chart = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setSeries(null); setFc(null); setError(null)
    api.get<SeriesRow[]>(`/countries/${iso3}/series`)
      .then(setSeries).catch(e => setError(String(e)))
    api.get<Forecast[]>(`/countries/${iso3}/forecasts`)
      .then(setFc).catch(() => setFc([]))
  }, [iso3])

  useEffect(() => {
    let alive = true
    loadPlotly().then(P => {
      if (!alive || !chart.current || !series) return
      const obs = series.filter(s => s.u5m != null)
      const fill = fc && fc.length
        ? { x: [fc[0].last_observed_year, ...fc.map(f => f.year)],
            y: [obs.length ? obs[obs.length - 1].u5m! : null, ...fc.map(f => f.yhat)],
            name: 'Forecast', mode: 'lines+markers', line: { dash: 'dot', color: '#b45309' },
            error_y: {
              type: 'data', symmetric: false,
              array: fc.map(f => Math.max(f.hi90 - f.yhat, 0)),
              arrayminus: fc.map(f => Math.max(f.yhat - f.lo90, 0)),
              color: 'rgba(180, 83, 9, .45)',
            } }
        : null
      const data = [
        { x: obs.map(s => s.year), y: obs.map(s => s.u5m!), name: 'Observed U5M',
          mode: 'lines+markers', line: { color: '#2e5339', width: 2.4 }, marker: { size: 5 } },
        ...(fill ? [fill] : []),
      ]
      P.react(chart.current, data, {
        paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#6f6455' }, height: 320, margin: { t: 10, b: 34, l: 46, r: 10 },
        legend: { orientation: 'h' },
        xaxis: { gridcolor: '#e2d8c6', zerolinecolor: '#e2d8c6' },
        yaxis: { gridcolor: '#e2d8c6', zerolinecolor: '#e2d8c6' },
        showlegend: data.length > 1,
      })
    }).catch(e => console.error('[plotly] chart render failed:', e))
    return () => { alive = false }
  }, [series, fc])

  const latest = series?.length ? series[series.length - 1] : null
  const fc1 = fc && fc.length ? fc[0] : null
  const topDrivers = fc1?.top_drivers_shap ?? []
  const maxAbs = Math.max(1e-6, ...topDrivers.map(d => Math.abs(d.shap)))

  // ---- scenario simulator + auto-brief (R2) ----
  const [ivDriver, setIvDriver] = useState<string>('dpt_cov')
  const [ivDelta, setIvDelta] = useState<number>(10)
  const [scenario, setScenario] = useState<ScenarioResponse | null>(null)
  const [scenErr, setScenErr] = useState<string | null>(null)
  const [brief, setBrief] = useState<string | null>(null)
  useEffect(() => {
    setScenario(null); setScenErr(null)
    api.get('/countries/' + iso3 + '/brief').then((t: string) => setBrief(t)).catch(() => setBrief(''))
  }, [iso3])
  const runScenario = () => {
    setScenErr(null); setScenario(null)
    api.post<ScenarioResponse>('/scenarios', {
      iso3: String(iso3 || '').toUpperCase(),
      interventions: [{ driver: ivDriver, delta: ivDelta }],
    } as ScenarioRequest)
      .then(setScenario)
      .catch(e => setScenErr(String(e).includes('422') ? 'not interventable: that driver has no observed value in the scenario year' : String(e)))
  }

  return (
    <div>
      <p><Link to="/atlas" className="btn ghost" style={{ padding: '8px 14px', fontSize: 13 }}>
        <ArrowLeft size={14} /> Atlas</Link></p>
      {error && <div className="panel">API error: {error}</div>}
      <h1>{series?.length ? countryName(iso3) : iso3}
        {latest?.u5m != null && (
          <span className="tag" style={{
            marginLeft: 12, verticalAlign: 'middle', fontSize: 13,
            background: riskFill[risk(latest.u5m)],
            color: '#fbf8f2',
          }}>U5M {latest.u5m} ({latest.year})</span>
        )}
      </h1>
      <div className="grid2">
        <div>
          <div className="glass">
            <h2 style={{ display: 'inline-flex', alignItems: 'center', gap: 8, marginTop: 0 }}>
              <TrendingUp size={17} /> Observed series + forecast</h2>
            {series === null
              ? <div className="skeleton" style={{ height: 320 }} />
              : <div ref={chart} style={{ height: 320 }} />}
            {series && !series.some(s => s.u5m != null) && (
              <p className="muted">No observed under-five mortality in the dataset window for this country.</p>
            )}
          </div>
          <div className="glass" style={{ marginTop: 16 }}>
            <h2 style={{ marginTop: 0 }}>Registered forecasts ({fc ? fc.length : 0})</h2>
            {!fc ? <div className="skeleton" style={{ height: 120 }} /> : fc.length === 0
              ? <p className="muted">No forecasts for this country.</p> : (
              <table>
                <thead><tr><th>Year</th><th>Forecast</th><th>90% interval</th><th>P(&gt;70)</th><th>H</th></tr></thead>
                <tbody>
                  {fc.map(f => (
                    <tr key={f.year}>
                      <td>{f.year}</td>
                      <td><b className="num">{f.yhat}</b></td>
                      <td className="num">{f.lo90} – {f.hi90}</td>
                      <td className="num">{f.p_gt_70}</td>
                      <td>{f.horizon}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {fc1?.drivers_default_missing && (
              <p className="muted" style={{ fontSize: 12.5 }}>
                <AlertTriangle size={13} style={{ verticalAlign: -2, marginRight: 4 }} />
                Drivers not observed for this horizon — history was carried forward by the model (assumption, not data).
              </p>
            )}
          </div>
        </div>
        <div>
          <div className="glass">
            <h2 style={{ display: 'inline-flex', alignItems: 'center', gap: 8, marginTop: 0 }}>
              <Sigma size={17} /> What drives this risk</h2>
            <p className="muted" style={{ fontSize: 12.5, marginTop: 0 }}>
              SHAP contributions to the latest forecast (sum ≈ forecast − baseline).
              Model behaviour, <b>not causation</b>.
            </p>
            {topDrivers.map(d => (
              <div key={d.feature} className={`bar-row${d.shap < 0 ? ' neg' : ''}`}>
                <span>{pretty(d.feature)}</span>
                <div className="track">
                  <div className="fill" style={{
                    width: `${Math.abs(d.shap) / maxAbs * 100}%`,
                    marginLeft: d.shap < 0 ? `${100 - Math.abs(d.shap) / maxAbs * 100}%` : 0,
                  }} />
                </div>
                <span className="muted">{d.shap > 0 ? '+' : ''}{d.shap.toFixed(1)}</span>
              </div>
            ))}
            {!fc1 && <div className="skeleton" style={{ height: 140 }} />}
          </div>
          <div className="kpi glass" style={{ marginTop: 16, borderRadius: 'var(--r-md)' }}>
            <div className="l">Driver data coverage (latest obs)</div>
            <div className="v num">{latest ? latest.q_driver_coverage_pct + '%' : '—'}</div>
          </div>

          <div className="glass" style={{ marginTop: 16 }}>
            <h2 style={{ display: 'inline-flex', alignItems: 'center', gap: 8, marginTop: 0 }}>
              <FlaskConical size={17} /> What-if: nudge a driver</h2>
            <p className="muted" style={{ fontSize: 12.5, marginTop: 0 }}>
              Runs the registered model on a counterfactual
              {' '}{(((series?.filter(s => s.u5m != null) ?? []).slice(-1)[0])?.year ?? 2024) + 1} forecast
              with one driver changed for its t−1 year. Model behaviour, not a causal
              estimate — single horizon.
            </p>
            <div className="flex" style={{ marginTop: 10 }}>
              <select value={ivDriver} onChange={e => setIvDriver(e.target.value)}>
                {IntervenableDrivers.map(d =>
                  <option key={d} value={d}>{pretty(d + '_p1').replace(' (t-1)', '')}</option>)}
              </select>
              <input type="range" min={-30} max={40} step={1} value={ivDelta}
                     onChange={e => setIvDelta(+e.target.value)} style={{ flex: 1, accentColor: 'var(--accent)' }} />
              <b className="num" style={{ minWidth: 46 }}>{ivDelta > 0 ? '+' : ''}{ivDelta}</b>
              <button className="btn primary" style={{ padding: '9px 16px', fontSize: 13.5 }} onClick={runScenario}>
                Run</button>
            </div>
            {scenErr && <p className="muted" style={{ fontSize: 12.5, marginTop: 8 }}>{scenErr}</p>}
            {scenario && (
              <div className="kpi num" style={{ marginTop: 12, background: 'rgba(255,255,255,.5)',
                                              borderRadius: 'var(--r-md)', padding: 14 }}>
                <div className="l">{pretty(ivDriver + '_p1')} → {scenario.interventions_applied?.[ivDriver] ?
                  `${(+scenario.interventions_applied[ivDriver].base).toFixed(1)} → ${(+scenario.interventions_applied[ivDriver].scenario_value).toFixed(1)}` : ''}</div>
                <div className="v" style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
                  {scenario.yhat_scenario}
                  <span style={{ color: scenario.delta < 0 ? 'var(--accent)' : 'var(--danger)', fontSize: 15, fontWeight: 650 }}>
                    {scenario.delta > 0 ? '+' : ''}{scenario.delta} vs {scenario.yhat_registered_replay}
                  </span>
                </div>
                <div className="faint num" style={{ fontSize: 12, marginTop: 4 }}>
                  90% interval {scenario.interval_90_scenario[0]} – {scenario.interval_90_scenario[1]} ·
                  {(scenario.honesty_note.split('—')[1] ?? 'model behaviour, not causation')}
                </div>
              </div>
            )}
          </div>

          <div className="glass" style={{ marginTop: 16 }}>
            <h2 style={{ display: 'inline-flex', alignItems: 'center', gap: 8, marginTop: 0 }}>
              <FileText size={16} /> Auto-brief</h2>
            {brief === null ? <div className="skeleton" style={{ height: 130 }} /> : (
              <pre className="muted" style={{ whiteSpace: 'pre-wrap', font: '12.5px/1.6 var(--sans)', margin: 8 }}>
                {brief || 'Briefing unavailable.'}
              </pre>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function countryName(iso3?: string) { return iso3 }
function risk(u: number): keyof typeof colors {
  if (u >= 100) return 'critical'
  if (u >= 70) return 'high'
  if (u >= 40) return 'elevated'
  return 'moderate'
}
function pretty(f: string) {
  const map: Record<string, string> = {
    'u5m_lag1': 'U5M last year', 'u5m_lag2': 'U5M 2y ago', 'u5m_lag3': 'U5M 3y ago',
    'year': 'Trend (year)', 'region_afr': 'Sub-Saharan region',
    'region_mena': 'North Africa', 'gdp_pc_p1': 'GDP per capita (t-1)',
    'chexp_pctgdp_p1': 'Health spend % GDP (t-1)', 'phys_1k_p1': 'Physicians (t-1)',
    'nurses_1k_p1': 'Nurses/midwives (t-1)', 'dpt_cov_p1': 'DPT coverage (t-1)',
    'meas_cov_p1': 'Measles coverage (t-1)', 'san_basic_p1': 'Sanitation (t-1)',
    'water_basic_p1': 'Water access (t-1)', 'urb_pct_p1': 'Urbanization (t-1)',
  }
  return map[f] ?? f
}
