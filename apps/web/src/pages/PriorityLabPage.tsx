import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { SlidersHorizontal } from 'lucide-react'
import { api, VulnerabilityData, riskLevel, riskFill } from '../api/client'

const LABELS: Record<string, string> = {
  u5m_observing: 'current U5M burden',
  u5m_forecast: 'next-year forecast',
  phys_1k: 'physician scarcity',
  nurses_1k: 'nurse scarcity',
  dpt_cov: 'low DPT coverage',
  san_basic: 'no basic sanitation',
  water_basic: 'no basic water',
  chexp_pctgdp: 'low health spend',
}

/**
 * Priority Lab — the honest answer to "which areas first?" (user concern 1 +
 * R3 feature 4). The user moves weight sliders over the SAME published
 * component percentiles as vuln-v1; composite + drop-one sensitivity are
 * recomputed client-side with the identical deterministic maths. A priority
 * score is a planning aid — it is NOT a causal estimate of lives saved, and
 * national data alone cannot rank districts.
 */
export default function PriorityLabPage() {
  const nav = useNavigate()
  const [data, setData] = useState<VulnerabilityData | null>(null)
  const [weights, setWeights] = useState<Record<string, number> | null>(null)

  useEffect(() => {
    api.get<VulnerabilityData>('/vulnerability').then(v => {
      setData(v)
      setWeights({ ...v.weights })
    }).catch(() => setData(null))
  }, [])

  const ranked = useMemo(() => {
    if (!data || !weights) return []
    const W = { ...weights }
    const total = Object.values(W).reduce((a, b) => a + b, 0) || 1
    return data.rows
      .filter(r => r.composite != null)
      .map(r => {
        const avail: [string, number][] = []
        for (const k of Object.keys(LABELS)) {
          const c = r.components[k]
          if (c != null) avail.push([k, c])
        }
        const wsum = avail.reduce((a, [k]) => a + W[k], 0) || 1
        const comp = avail.reduce((a, [k, v]) => a + v * W[k], 0) / wsum
        // client-side jackknife: worst drop-one delta with the user's weights
        let jk = 0
        for (let i = 0; i < avail.length; i++) {
          const sub = avail.filter((_, j) => j !== i)
          if (!sub.length) continue
          const w2 = sub.reduce((a, [k]) => a + W[k], 0) || 1
          const c2 = sub.reduce((a, [k, v]) => a + v * W[k], 0) / w2
          jk = Math.max(jk, Math.abs(c2 - comp))
        }
        return { ...r, custom: Math.round(comp * 10) / 10, customJackknife: Math.round(jk * 10) / 10 }
      })
      .sort((a, b) => b.custom - a.custom)
  }, [data, weights])

  const band = (v: number) => v < 20 ? 'low' : v < 50 ? 'watch' : v < 80 ? 'elevated' : 'high'

  if (data === null) return <div className="skeleton" style={{ height: 300 }} />

  return (
    <div>
      <span className="kicker"><SlidersHorizontal size={13} /> Priority &amp; resource planning</span>
      <h1 style={{ marginTop: 14 }}>Priority Lab</h1>
      <p className="muted" style={{ maxWidth: '50em' }}>
        Move the weights — the ranking recomputes from the same published
        percentiles with the same transparent maths, including a live drop-one
        sensitivity for your chosen weights.
      </p>
      <div className="glass" style={{ padding: '10px 16px', borderRadius: 'var(--r-md)', marginTop: 14, borderLeft: '3px solid var(--accent)' }}>
        <span style={{ fontSize: 12.5 }}>
          <b>A planning aid, not a plan.</b> This score reorders evidence — it is not a
          causal estimate of lives saved, and national data cannot rank districts:
          bring your subnational rows into a workspace for that.
        </span>
      </div>

      <div className="grid2" style={{ marginTop: 18, gridTemplateColumns: '300px 1fr' }}>
        <div className="glass" style={{ padding: 18 }}>
          <h2 style={{ marginTop: 0, fontSize: 15 }}>Your weights</h2>
          {Object.entries(LABELS).map(([k, label]) => (
            <div key={k} style={{ marginBottom: 10 }}>
              <div className="flex" style={{ justifyContent: 'space-between', fontSize: 12 }}>
                <span className="muted">{label}</span>
                <b className="num">{((weights?.[k] ?? 0) * 100).toFixed(0)}%</b>
              </div>
              <input type="range" min={0} max={40} value={Math.round((weights?.[k] ?? 0) * 100)}
                     onChange={e => setWeights(w => ({ ...(w ?? {}), [k]: +e.target.value / 100 }))}
                     style={{ width: '100%', accentColor: 'var(--accent)' }} />
            </div>
          ))}
          <button className="btn ghost" style={{ fontSize: 12, padding: '7px 12px', marginTop: 4 }}
                  onClick={() => setWeights({ ...data.weights })}>
            reset to published vuln-v1 weights
          </button>
          {(() => {
            const sum = Object.values(weights ?? {}).reduce((a, b) => a + b, 0)
            return <p className="faint" style={{ fontSize: 11.5, margin: 0 }}>
              weights are renormalised automatically (current sum {sum.toFixed(2)})
            </p>
          })()}
        </div>

        <div className="glass" style={{ padding: 18 }}>
          <h2 style={{ marginTop: 0, fontSize: 15 }}>Ranked priorities ({ranked.length} countries)</h2>
          <div style={{ display: 'grid', gap: 6, maxHeight: 480, overflow: 'auto' }}>
            {ranked.map((r, i) => {
              const u5mObs = r.components.u5m_observing ?? 0
              return (
              <div key={r.iso3} className="flex" style={{ gap: 10, padding: '7px 10px', borderBottom: '1px solid var(--line)',
                                                              alignItems: 'center', cursor: 'pointer' }}
                   onClick={() => nav(`/country/${r.iso3}`)}>
                <b className="num serif-i" style={{ opacity: .4, minWidth: 26 }}>{i + 1}</b>
                <span className="flag-dot" style={{ background: u5mObs ? riskFill[riskLevel(u5mObs)] : '#c6b99f' }} />
                <span style={{ fontWeight: 650, fontSize: 13.5, flex: 1, minWidth: 90 }}>{r.country}</span>
                <div style={{ flex: 2, minWidth: 80, height: 7, background: 'var(--line)', borderRadius: 99, overflow: 'hidden' }}>
                  <div style={{ width: `${r.custom}%`, height: '100%',
                                background: ['#2e5339', '#ca8a04', '#b45309', '#7c2d12'][Math.min(3, Math.floor(r.custom / 25))] }} />
                </div>
                <b className="num" style={{ minWidth: 40 }}>{r.custom}</b>
                <span className={`tag ${band(r.custom) === 'high' ? 'bad' : band(r.custom) === 'elevated' ? 'warn' : 'ok'}`} style={{ fontSize: 10.5, padding: '2px 8px' }}>
                  {band(r.custom)}
                </span>
                <span className="faint num" style={{ fontSize: 10.5, minWidth: 44 }} title="worst change if any component were dropped with your weights">
                  ±{r.customJackknife}
                </span>
              </div>
              )
            })}
          </div>
          <p className="faint" style={{ fontSize: 11.5, marginTop: 10 }}>
            ± column = drop-one sensitivity under YOUR weights; large numbers mean the
            ranking is fragile for that country — check the components before arguing
            from a rank position.
          </p>
        </div>
      </div>
    </div>
  )
}
