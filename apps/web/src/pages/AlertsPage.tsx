import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { BellRing, Info } from 'lucide-react'
import { api, AlertsData } from '../api/client'

export default function AlertsPage() {
  const nav = useNavigate()
  const [data, setData] = useState<AlertsData | null>(null)
  useEffect(() => { api.get<AlertsData>('/alerts').then(setData).catch(() => setData(null)) }, [])

  return (
    <div>
      <span className="kicker"><BellRing size={13} /> Decision-support watchlist</span>
      <h1 style={{ marginTop: 14 }}>Alerts — most likely to stay above critical u5m</h1>
      <p className="muted" style={{ maxWidth: '48em' }}>
        Countries whose <b>registered 2025 forecasts</b> carry the highest
        probability of remaining above the critical under-five-mortality
        threshold of 70 (per 1,000 live births), with the composite-vulnerability
        context that shaped the ranking.
      </p>
      {data === null ? <div className="skeleton" style={{ height: 320 }} /> : (
        <>
          <div className="glass" style={{ marginTop: 18, padding: '14px 18px', borderRadius: 'var(--r-md)' }}>
            <div className="flex" style={{ gap: 8 }}>
              <Info size={15} style={{ color: 'var(--accent)', flexShrink: 0 }} />
              <span className="muted" style={{ fontSize: 13 }}>{data.rule}</span>
            </div>
          </div>
          <div style={{ display: 'grid', gap: 12, marginTop: 18 }}>
            {data.rows.map((r, i) => (
              <div key={r.iso3} className="glass country-card" style={{ alignItems: 'flex-start' }}
                   onClick={() => nav(`/country/${r.iso3}`)}>
                <b className="stat serif-i" style={{ opacity: .35, minWidth: 34 }}>{i + 1}</b>
                <div style={{ minWidth: 120 }}>
                  <div style={{ fontWeight: 650 }}>{r.country}</div>
                  <div className="faint" style={{ fontSize: 12 }}>entry {r.year}</div>
                </div>
                <div style={{ flex: 1, minWidth: 240 }}>
                  <div style={{ marginBottom: 4 }}>
                    <span className="num" style={{ fontWeight: 650, fontSize: 19 }}>{r.yhat}</span>
                    <span className="muted num" style={{ fontSize: 13, marginLeft: 8 }}>
                      {r.lo90} – {r.hi90} · P(&gt;70)={r.p_gt_70} · P(&gt;50)={r.p_gt_50}
                    </span>
                  </div>
                  <div style={{ display: 'grid', gap: 2 }}>
                    {r.reasons.map((x, j) => (
                      <span key={j} className={j === 0 ? 'muted' : 'faint'}
                            style={{ fontSize: 12.5 }}>· {x}</span>
                    ))}
                  </div>
                </div>
                <span className={`tag ${r.p_gt_70 >= 0.9 ? 'bad' : 'warn'}`} style={{ alignSelf: 'center' }}>
                  {r.p_gt_70 >= 0.9 ? 'critical watch' : 'high watch'}
                </span>
              </div>
            ))}
          </div>
          <p className="faint" style={{ fontSize: 12.5, marginTop: 18 }}>{data.honesty_note}</p>
        </>
      )}
    </div>
  )
}
