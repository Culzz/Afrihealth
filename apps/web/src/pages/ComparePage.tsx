import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowUpDown, X } from 'lucide-react'
import { api, Atlas, Country, ComparisonColumn, colors, riskFill, riskLevel } from '../api/client'

const DEFAULT = ['NGA', 'ETH', 'ZAF', 'TUN']

export default function ComparePage() {
  const nav = useNavigate()
  const [countries, setCountries] = useState<Country[]>([])
  const [pick, setPick] = useState<string[]>(DEFAULT)
  const [data, setData] = useState<ComparisonColumn[] | null>(null)
  const [atlasRows, setAtlasRows] = useState<Atlas[]>([])
  const [q, setQ] = useState('')

  useEffect(() => { api.get<Country[]>('/countries').then(setCountries).catch(() => {}) }, [])
  useEffect(() => { api.get<Atlas[]>('/atlas').then(setAtlasRows).catch(() => {}) }, [])
  useEffect(() => {
    setData(null)
    api.get<{ columns: ComparisonColumn[] }>(`/comparisons?iso3=${pick.join(',')}`)
      .then(d => setData(d.columns)).catch(() => setData([]))
  }, [pick])

  const suggestions = useMemo(() => {
    const used = new Set(pick)
    return countries.filter(c =>
      !used.has(c.iso3) &&
      (q === '' || c.country.toLowerCase().includes(q.toLowerCase()) ||
       c.iso3.toLowerCase() === q.toLowerCase()))
  }, [countries, pick, q])

  const metaByIso = useMemo(() =>
    Object.fromEntries(atlasRows.map(r => [r.iso3, r])), [atlasRows])

  return (
    <div>
      <span className="kicker"><ArrowUpDown size={13} /> Side-by-side</span>
      <h1 style={{ marginTop: 14 }}>Compare countries</h1>
      <p className="muted" style={{ maxWidth: '46em' }}>
        One row per observation thread: current burden, the direction of the last
        decade, the forecasted near-term trajectory, and the vulnerability composite.
      </p>
      <div className="glass flex" style={{ marginTop: 16, borderRadius: 'var(--r-md)' }}>
        {pick.map(p => (
          <span key={p} className="tag ok" style={{ fontSize: 12.5, padding: '5px 12px' }}>
            {p}
            <button onClick={() => setPick(cur => cur.filter(x => x !== p))}
                    style={{ border: 'none', background: 'none', padding: 0, marginLeft: 4, color: 'inherit' }}
                    aria-label={`remove ${p}`}>
              <X size={12} style={{ verticalAlign: -1.5 }} />
            </button>
          </span>
        ))}
        <input value={q} onChange={e => setQ(e.target.value)}
               placeholder="add country…"
               style={{ border: '1px solid var(--line)', borderRadius: 999, padding: '6px 12px',
                        font: '13px var(--sans)', background: 'var(--paper-card)', minWidth: 130 }} />
      </div>
      {q !== '' && (
        <div className="glass flex" style={{ marginTop: 10, borderRadius: 'var(--r-md)', maxHeight: 200, overflow: 'auto' }}>
          {suggestions.slice(0, 14).map(c => (
            <button key={c.iso3} className="btn ghost" style={{ padding: '6px 12px', fontSize: 13 }}
                    onClick={() => { setPick(cur => [...cur, c.iso3].slice(0, 4)); setQ('') }}>
              {c.country}
            </button>
          ))}
        </div>
      )}

      {data === null ? <div className="skeleton" style={{ height: 300, marginTop: 20 }} /> : (
        <div className="grid2" style={{ marginTop: 20, gridTemplateColumns: '1fr' }}>
          {data.map(c => {
            const meta = metaByIso[c.iso3]
            const lvl = c.u5m_latest != null ? riskLevel(c.u5m_latest) : null
            return (
            <div key={c.iso3} className="glass" style={{ cursor: 'pointer' }} onClick={() => nav(`/country/${c.iso3}`)}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                <span className="flag-dot" style={{ background: (lvl && c.u5m_latest != null) ? riskFill[lvl] : '#c6b99f' }} />
                <b style={{ fontFamily: 'var(--serif)', fontSize: 19 }}>{c.country}</b>
                <span className="faint" style={{ fontSize: 12 }}>{c.region}</span>
                {c.vulnerability_band &&
                  <span className={`tag ${c.vulnerability_band === 'high' ? 'bad' : c.vulnerability_band === 'elevated' ? 'warn' : 'ok'}`}>
                    vuln: {c.vulnerability_band}</span>}
                {meta?.driver_coverage_pct != null &&
                  <span className="tag" style={{ border: '1px solid var(--line)', color: 'var(--muted)' }}>
                    coverage {meta.driver_coverage_pct}%</span>}
              </div>
              <div className="stats4" style={{ marginTop: 14 }}>
                <div className="kpi"><div className="l">u5m {c.u5m_year}</div>
                  <div className="v num">{c.u5m_latest ?? '—'}</div></div>
                <div className="kpi"><div className="l">10-yr trend</div>
                  <div className="v num" style={{ color: (c.trend_10y_pp ?? 0) < 0 ? 'var(--accent)' : 'var(--danger)' }}>
                    {c.trend_10y_pp != null ? `${c.trend_10y_pp > 0 ? '+' : ''}${c.trend_10y_pp}` : '—'}</div></div>
                <div className="kpi"><div className="l">2025 forecast</div>
                  <div className="v num">{c.forecast_2025 ?? '—'}</div></div>
                <div className="kpi"><div className="l">2027 forecast</div>
                  <div className="v num">{c.forecast_2027 ?? '—'}</div></div>
              </div>
              {c.p_gt_70_2025 != null && (
                <p className="faint" style={{ fontSize: 12.5, marginTop: 10 }}>
                  P(u5m stays above 70 in 2025) = <b>{c.p_gt_70_2025}</b> · modeled behavior, not a measured event risk.
                </p>
              )}
            </div>
          )})}
        </div>
      )}
    </div>
  )
}
