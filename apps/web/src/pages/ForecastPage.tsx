import { useEffect, useRef, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api, SeriesRow, Forecast, colors, plotly } from '../api/client'

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
    const P = plotly()
    if (!P || !chart.current || !series) return
    const obs = series.filter(s => s.u5m != null)
    const fill = fc && fc.length
      ? { x: [fc[0].last_observed_year, ...fc.map(f => f.year)],
          y: [obs.length ? obs[obs.length - 1].u5m! : null, ...fc.map(f => f.yhat)],
          name: 'Forecast', mode: 'lines+markers', line: { dash: 'dot', color: '#c9520f' },
          error_y: {
            type: 'data', symmetric: false,
            array: fc.map(f => Math.max(f.hi90 - f.yhat, 0)),
            arrayminus: fc.map(f => Math.max(f.yhat - f.lo90, 0)),
            color: 'rgba(201,82,15,.5)',
          } }
      : null
    const data = [
      { x: obs.map(s => s.year), y: obs.map(s => s.u5m!), name: 'Observed U5M',
        mode: 'lines+markers', line: { color: '#6fd3a8', width: 2.4 }, marker: { size: 5 } },
      ...(fill ? [fill] : []),
    ]
    P.react(data, {
      paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
      font: { color: '#8fa2bd' }, height: 320, margin: { t: 10, b: 34, l: 46, r: 10 },
      legend: { orientation: 'h' }, xaxis: { gridcolor: '#26344b' }, yaxis: { gridcolor: '#26344b' },
      showlegend: data.length > 1,
    })
  }, [series, fc])

  const latest = series?.length ? series[series.length - 1] : null
  const fc1 = fc && fc.length ? fc[0] : null
  const topDrivers = fc1?.top_drivers_shap ?? []
  const maxAbs = Math.max(1e-6, ...topDrivers.map(d => Math.abs(d.shap)))

  return (
    <div>
      <p><Link to="/atlas">← Atlas</Link></p>
      {error && <div className="panel">API error: {error}</div>}
      <h1>{series?.length ? countryName(iso3) : iso3}
        {latest?.u5m != null && (
          <span className="tag" style={{
            marginLeft: 12, verticalAlign: 'middle',
            background: colors[risk(latest.u5m)], color: '#0e1522',
          }}>U5M {latest.u5m} ({latest.year})</span>
        )}
      </h1>
      <div className="grid2">
        <div>
          <div className="panel">
            <h2 style={{ marginTop: 4 }}>Observed series + forecast</h2>
            {series === null
              ? <div className="skeleton" style={{ height: 320 }} />
              : <div ref={chart} style={{ height: 320 }} />}
            {series && !series.some(s => s.u5m != null) && (
              <p className="muted">No observed under-five mortality in the dataset window for this country.</p>
            )}
          </div>
          <div className="panel" style={{ marginTop: 16 }}>
            <h2 style={{ marginTop: 4 }}>Registered forecasts ({fc ? fc.length : 0})</h2>
            {!fc ? <div className="skeleton" style={{ height: 120 }} /> : fc.length === 0
              ? <p className="muted">No forecasts for this country.</p> : (
              <table>
                <thead><tr><th>Year</th><th>Forecast</th><th>90% interval</th><th>P(&gt;70)</th><th>H</th></tr></thead>
                <tbody>
                  {fc.map(f => (
                    <tr key={f.year}>
                      <td>{f.year}</td>
                      <td><b>{f.yhat}</b></td>
                      <td>{f.lo90} – {f.hi90}</td>
                      <td>{f.p_gt_70}</td>
                      <td>{f.horizon}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {fc1?.drivers_default_missing && (
              <p className="muted" style={{ fontSize: 12.5 }}>
                ⚠ Drivers not observed for this horizon — history was carried forward by the model (assumption, not data).
              </p>
            )}
          </div>
        </div>
        <div>
          <div className="panel">
            <h2 style={{ marginTop: 4 }}>What the model thinks drives risk</h2>
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
          <div className="kpi" style={{ marginTop: 16 }}>
            <div className="l">Driver data coverage (latest obs)</div>
            <div className="v">{latest ? latest.q_driver_coverage_pct + '%' : '—'}</div>
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
