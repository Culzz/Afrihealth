import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, Atlas, Country, colors, plotly, riskLevel } from '../api/client'

const YEAR_MIN = 2000
export default function AtlasPage() {
  const nav = useNavigate()
  const [countries, setCountries] = useState<Country[]>([])
  const [rows, setRows] = useState<Atlas[] | null>(null)
  const [year, setYear] = useState<number | null>(null)   // null => latest
  const [mode, setMode] = useState<'observed' | 'forecast'>('observed')
  const divRef = useRef<HTMLDivElement>(null)

  useEffect(() => { api.get<Country[]>('/countries').then(setCountries).catch(() => {}) }, [])
  useEffect(() => {
    const q = year ? `?year=${year}` : ''
    setRows(null)
    api.get<Atlas[]>(`/atlas${q}`).then(setRows).catch(() => setRows([]))
  }, [year])

  const filtered = useMemo(() => {
    if (!rows) return []
    if (mode === 'observed') return rows.filter(r => r.u5m != null)
    return rows                                  // forecast mode colors by coverage of evidence
  }, [rows, mode])

  useEffect(() => {
    const P = plotly()
    if (!P || !divRef.current || !filtered.length) return
    const vals = filtered.map((r: any) =>
      mode === 'observed' ? (r.u5m ?? null) : r.driver_coverage_pct)
    const numberize = (v: any) => (v == null ? 0 : v)
    const data = [{
      type: 'choropleth',
      locations: filtered.map(r => r.iso3),
      z: vals.map(numberize),
      text: filtered.map(r => `${r.country} — ${mode === 'observed'
        ? (r.u5m == null ? 'no data' : `U5M ${r.u5m}`)
        : `driver coverage ${r.driver_coverage_pct}%`}`),
      hoverinfo: 'location+text',
      colorscale: mode === 'observed'
        ? [[0, colors.moderate], [0.4, colors.elevated], [0.7, colors.high], [1, colors.critical]]
        : [[0, '#b3392f'], [1, '#1d7f5c']],
      zmin: mode === 'observed' ? 0 : 50,
      zmax: mode === 'observed' ? 170 : 100,
      marker: { line: { color: '#0e1522', width: 0.6 } },
      showscale: false,
    }]
    const layout = {
      geo: { scope: 'africa', showframe: false, showcoastlines: false,
             bgcolor: 'rgba(0,0,0,0)', landcolor: '#1c2940' },
      paper_bgcolor: 'rgba(0,0,0,0)', margin: { t: 0, b: 0, l: 0, r: 0 },
      height: 430, dragmode: 'pan',
    }
    P.react(data, layout).then(() => {
      // enable country click navigation
      const g = document.getElementById('africamap') as any
    })
  }, [filtered, mode])

  const latest = rows?.length ? rows[0].year : null

  return (
    <div>
      <h1>Atlas {latest ? <span className="muted" style={{ fontSize: 15 }}>({latest})</span> : null}</h1>
      <p className="muted">
        Under-five mortality (per 1,000 live births) across African Union countries.
        Filter toggles show data <i>confidence</i> instead of risk — missing data is visible, never filled.
      </p>
      <div className="grid2">
        <div className="panel">
          <div style={{ display: 'flex', gap: 10, marginBottom: 12 }}>
            <button onClick={() => setMode('observed')}
                    style={mode === 'observed' ? { borderColor: '#1d7f5c' } : {}}>Risk view</button>
            <button onClick={() => setMode('forecast')}
                    style={mode !== 'observed' ? { borderColor: '#1d7f5c' } : {}}>Data-confidence view</button>
            <select value={year ?? ''} onChange={e => setYear(e.target.value ? +e.target.value : null)}>
              <option value="">Latest year</option>
              {Array.from({ length: 2024 - YEAR_MIN + 1 }, (_, i) => 2024 - i)
                .map(y => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
          {rows === null ? <div className="skeleton" /> : (
            <div ref={divRef} id="africamap" style={{ height: 430 }} />
          )}
        </div>
        <div className="panel">
          <h2>Countries ({filtered.length})</h2>
          <table>
            <thead><tr><th>Country</th><th>U5M</th><th>Flags</th></tr></thead>
            <tbody>
              {filtered.slice(0, 14).map(r => (
                <tr key={r.iso3} style={{ cursor: 'pointer' }} onClick={() => nav(`/country/${r.iso3}`)}>
                  <td>{r.country}</td>
                  <td>{mode === 'observed' ? (r.u5m ?? '—') : `${r.driver_coverage_pct}%`}</td>
                  <td>
                    {r.target_missing && <span className="tag warn">no target</span>}
                    {!r.target_missing && r.sparse_hwf_missing && <span className="tag warn">sparse HWF</span>}
                    {!r.target_missing && !r.sparse_hwf_missing && mode === 'observed' &&
                      r.u5m != null && <span className="tag ok">{riskLevel(r.u5m)}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted" style={{ fontSize: 12.5 }}>Click a country for forecasts, intervals, and SHAP drivers.</p>
        </div>
      </div>
    </div>
  )
}
