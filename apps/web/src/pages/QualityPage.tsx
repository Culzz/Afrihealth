import { useEffect, useState } from 'react'
import { ShieldCheck, RefreshCw } from 'lucide-react'
import { api, QualityData, ChangesData } from '../api/client'

export default function QualityPage() {
  const [q, setQ] = useState<QualityData | null>(null)
  const [changes, setChanges] = useState<ChangesData | null>(null)
  const [markBusy, setMarkBusy] = useState(false)

  useEffect(() => {
    api.get<QualityData>('/quality').then(setQ).catch(() => setQ(null))
    api.get<ChangesData>('/quality/changes')
      .then(setChanges)
      .catch(() => setChanges(null))
  }, [])

  const markNow = async () => {
    setMarkBusy(true)
    try {
      setChanges(await api.post<ChangesData>('/quality/changes?mark=1', {}))
    } catch { /* keep previous */ }
    setMarkBusy(false)
  }

  return (
    <div>
      <span className="kicker"><ShieldCheck size={13} /> Data quality &amp; evidence monitor</span>
      <h1 style={{ marginTop: 14 }}>Is the evidence fit for this cycle's reporting?</h1>
      <p className="muted" style={{ maxWidth: '52em' }}>
        Coverage, freshness, missingness and suspicious year-over-year changes per
        indicator — plus artifact-level change tracking against your last check.
        Values are never corrected automatically: flags mean "review before citing".
      </p>

      {changes && (
        <div className="glass flex" style={{ marginTop: 16, padding: '12px 16px', borderRadius: 'var(--r-md)', alignItems: 'center' }}>
          <span className="muted" style={{ fontSize: 12.5, flex: 1 }}>
            Change monitor · dataset <b>{changes.current.dataset_version}</b> · model{' '}
            <b>{changes.current.model_version}</b> —{' '}
            {changes.changed ? changes.what.join(' · ') : 'no changes since the last marked baseline'}
          </span>
          <button className="btn primary" style={{ fontSize: 12, padding: '7px 12px' }} onClick={markNow} disabled={markBusy}>
            <RefreshCw size={12} style={{ verticalAlign: -2 }} /> {markBusy ? '…' : 'Mark as reviewed'}
          </button>
        </div>
      )}

      {q === null ? <div className="skeleton" style={{ height: 320, marginTop: 18 }} /> : (
        <table style={{ width: '100%', marginTop: 18, fontSize: 12.5 }} className="glass" cellPadding={8}>
          <thead>
            <tr>
              <th style={thL}>indicator</th>
              <th style={thL}>coverage {q.window[0]}–{q.window[1]}</th>
              <th style={thL}>missing</th>
              <th style={thL}>stale (&gt; {q.window[1] - 4})</th>
              <th style={thL}>suspicious jumps</th>
            </tr>
          </thead>
          <tbody>
            {q.indicators.map(i => (
              <tr key={i.indicator} style={{ borderTop: '1px solid var(--line)' }}>
                <td style={tdL}><b>{i.indicator}</b></td>
                <td style={tdL}>
                  <span className="tag" style={{ background: i.coverage_pct > 90 ? 'rgba(46,83,57,.12)' : i.coverage_pct > 60 ? 'rgba(202,138,4,.14)' : 'rgba(124,45,18,.12)', border: 'none' }}>
                    {i.coverage_pct}%
                  </span>
                </td>
                <td style={tdL}>{i.missingness_pct}%</td>
                <td style={tdL}>{i.stale_countries === 0 ? '—' : `${i.stale_countries} countries`}</td>
                <td style={tdL}>
                  {i.suspicious_changes === 0 ? '—' : `${i.suspicious_changes} flagged`}
                  {i.suspicious_samples.length > 0 && (
                    <span className="faint" style={{ fontSize: 11, marginLeft: 6 }}>
                      e.g. {i.suspicious_samples[0].iso3} {i.suspicious_samples[0].year}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <p className="faint" style={{ fontSize: 11.5, marginTop: 14 }}>
        {q?.indicators[0]?.definition_note ?? ''} Cross-source reconciliation (WHO vs WB
        revisions) is scoped for a later release.
      </p>
    </div>
  )
}

const thL: React.CSSProperties = { textAlign: 'left', fontWeight: 650, background: 'transparent' }
const tdL: React.CSSProperties = { verticalAlign: 'top' }
