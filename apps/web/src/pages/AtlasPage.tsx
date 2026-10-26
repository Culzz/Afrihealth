import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Map, Table2, Layers } from 'lucide-react'
import { api, Atlas, Country, colors, VulnerabilityData, loadPlotly, riskLevel } from '../api/client'

const YEAR_MIN = 2000
export default function AtlasPage() {
  const nav = useNavigate()
  const [countries, setCountries] = useState<Country[]>([])
  const [rows, setRows] = useState<Atlas[] | null>(null)
  const [year, setYear] = useState<number | null>(null)   // null => latest
  const [mode, setMode] = useState<'observed' | 'forecast' | 'vuln'>('observed')
  const [vuln, setVuln] = useState<VulnerabilityData | null>(null)
  const divRef = useRef<HTMLDivElement>(null)

  useEffect(() => { api.get<Country[]>('/countries').then(setCountries).catch(() => {}) }, [])
  useEffect(() => {
    const q = year ? `?year=${year}` : ''
    setRows(null)
    api.get<Atlas[]>(`/atlas${q}`).then(setRows).catch(() => setRows([]))
  }, [year])
  useEffect(() => {
    if (mode === 'vuln' && !vuln) api.get<VulnerabilityData>('/vulnerability').then(setVuln).catch(() => setVuln(null))
  }, [mode])

  const filtered = useMemo(() => {
    if (!rows) return []
    if (mode === 'observed') return rows.filter(r => r.u5m != null)
    return rows                                  // forecast mode colors by coverage of evidence
  }, [rows, mode])

  useEffect(() => {
    let alive = true
    loadPlotly().then(P => {
      if (!alive || !divRef.current) return
      if (mode === 'vuln') {
        if (!vuln) return
        const r = vuln.rows.filter(x => x.composite != null)
        const data = [{
          type: 'choropleth',
          locations: r.map(x => x.iso3),
          z: r.map((x: any) => x.composite),
          text: r.map(x => `${x.country} — vulnerability ${x.composite} (${x.band})`),
          hoverinfo: 'location+text',
          colorscale: [[0, '#2e5339'], [0.5, '#ca8a04'], [1, '#7c2d12']],
          zmin: 0, zmax: 100,
          marker: { line: { color: '#c9b99a', width: 0.7 } },
          showscale: false,
        }]
        const layout = {
          geo: { scope: 'africa', showframe: false, showcoastlines: false,
                 bgcolor: 'rgba(0,0,0,0)', landcolor: '#e5dcc9', showland: true },
          paper_bgcolor: 'rgba(0,0,0,0)', margin: { t: 0, b: 0, l: 0, r: 0 },
          height: 430, dragmode: 'pan',
        }
        P.react(data, layout)
        return
      }
      if (!filtered.length) return
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
          : [[0, '#7c2d12'], [1, '#2e5339']],
        zmin: mode === 'observed' ? 0 : 50,
        zmax: mode === 'observed' ? 170 : 100,
        marker: { line: { color: '#c9b99a', width: 0.7 } },
        showscale: false,
      }]
      const layout = {
        geo: { scope: 'africa', showframe: false, showcoastlines: false,
               bgcolor: 'rgba(0,0,0,0)', landcolor: '#e5dcc9', showland: true },
        paper_bgcolor: 'rgba(0,0,0,0)', margin: { t: 0, b: 0, l: 0, r: 0 },
        height: 430, dragmode: 'pan',
      }
      P.react(data, layout)
    }).catch(() => {})
    return () => { alive = false }
  }, [filtered, mode, vuln])

  const latest = rows?.length ? rows[0].year : null

  return (
    <div>
      <span className="kicker"><Map size={13} /> Risk atlas</span>
      <h1 style={{ marginTop: 14 }}>
        The Atlas {latest ? <span className="faint" style={{ fontSize: '0.5em', fontWeight: 400 }}>({latest})</span> : null}
      </h1>
      <p className="muted" style={{ maxWidth: '46em' }}>
        Under-five mortality (per 1,000 live births) across African Union countries.
        The data-confidence view shows how well-sourced each country is — missing data
        is visible, never filled.
      </p>
      <div className="grid2">
        <div className="panel">
          <div style={{ display: 'flex', gap: 10, marginBottom: 12, flexWrap: 'wrap' }}>
            <button onClick={() => setMode('observed')} className={mode === 'observed' ? 'active' : ''}>
              Risk view
            </button>
            <button onClick={() => setMode('vuln')} className={mode === 'vuln' ? 'active' : ''}>
              <Layers size={13} style={{ verticalAlign: -2 }} /> Vulnerability
            </button>
            <button onClick={() => setMode('forecast')} className={mode !== 'observed' && mode !== 'vuln' ? 'active' : ''}>
              Data-confidence view
            </button>
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
          <h2 style={{ display: 'inline-flex', alignItems: 'center', gap: 8, margin: '0 0 10px' }}>
            <Table2 size={17} /> Countries ({filtered.length})</h2>
          {mode === 'vuln' ? (
            <table>
              <thead><tr><th>Country</th><th>Vulnerability</th><th>Data</th></tr></thead>
              <tbody>
                {(vuln?.rows ?? []).slice(0, 14).map(v => (
                  <tr key={v.iso3} style={{ cursor: 'pointer' }} onClick={() => nav(`/country/${v.iso3}`)}>
                    <td>{v.country}</td>
                    <td><b className="num">{v.composite}</b>
                      <span className={`tag ${v.band === 'high' ? 'bad' : v.band === 'elevated' ? 'warn' : 'ok'}`}
                            style={{ marginLeft: 8 }}>{v.band}</span></td>
                    <td className="faint num" style={{ fontSize: 12 }}>
                      {v.complete ? 'complete' : `${v.missing_components.length} missing`}
                      {v.jackknife_max_delta != null && v.jackknife_max_delta > 6 &&
                        <span className="tag warn" style={{ marginLeft: 6 }}>±{v.jackknife_max_delta}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
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
          )}
          <p className="muted" style={{ fontSize: 12.5 }}>Click a country for forecasts, intervals, and SHAP drivers.</p>
        </div>
      </div>
    </div>
  )
}
