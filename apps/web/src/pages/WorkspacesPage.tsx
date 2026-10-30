import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { FolderOpen, Plus, CheckCircle2, AlertCircle } from 'lucide-react'
import { api, Workspace, ChangesData, Me } from '../api/client'
import { useAuth } from '../hooks/useAuth'

export default function WorkspacesPage() {
  const nav = useNavigate()
  const { me, loading } = useAuth()
  const [ws, setWs] = useState<Workspace[] | null>(null)
  const [changes, setChanges] = useState<ChangesData | null>(null)
  const [name, setName] = useState('')
  const [countries, setCountries] = useState('')
  const [creating, setCreating] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    if (!me) return
    api.get<Workspace[]>('/workspaces').then(setWs).catch(() => setWs([]))
    api.get<ChangesData>('/quality/changes').then(setChanges).catch(() => setChanges(null))
  }, [me?.user?.user_id])

  if (loading) return <div className="skeleton" style={{ height: 200 }} />
  if (!me) {
    return (
      <div className="glass" style={{ padding: 24, borderRadius: 'var(--r-md)' }}>
        <h2 className="serif" style={{ marginTop: 0 }}>Workspaces need an account</h2>
        <p className="muted">Sign in to open your organization's monitoring workspaces, saved analyses, and report runs.</p>
        <div className="flex" style={{ gap: 10 }}>
          <Link className="btn primary" to="/login">Sign in</Link>
          <Link className="btn ghost" to="/join">Create organization</Link>
        </div>
      </div>
    )
  }

  const create = async (e: React.FormEvent) => {
    e.preventDefault()
    setErr(null); setCreating(true)
    try {
      const created = await api.post<Workspace>('/workspaces', {
        name, countries: countries.split(',').map(s => s.trim().toUpperCase()).filter(Boolean),
      })
      setWs(w => [created, ...(w ?? [])])
      setName(''); setCountries('')
    } catch (e2) { setErr(String(e2)) }
    setCreating(false)
  }

  return (
    <div>
      <span className="kicker"><FolderOpen size={13} /> Program monitoring workspaces</span>
      <h1 style={{ marginTop: 14 }}>Your organization's workspaces</h1>
      <p className="muted" style={{ maxWidth: '48em' }}>
        One workspace per program, country portfolio or funding cycle — with
        targets, your own program data, saved analyses and versioned reports.
      </p>

      {changes && (
        <div className="glass flex" style={{ marginTop: 16, padding: '12px 16px', borderRadius: 'var(--r-md)', alignItems: 'center' }}>
          {changes.changed
            ? <AlertCircle size={15} style={{ color: 'var(--danger)' }} />
            : <CheckCircle2 size={15} style={{ color: 'var(--accent)' }} />}
          <span className="muted" style={{ fontSize: 12.5 }}>
            Dataset change monitor — {changes.changed
              ? <>changed since the last check: <b>{changes.what.join(' · ')}</b></>
              : <>no changes since the last check ({changes.current.dataset_version})</>}
          </span>
          <span className="faint" style={{ fontSize: 11.5, marginLeft: 'auto' }}>
            re-checked monthly by cron · v{changes.current.dataset_version}
          </span>
        </div>
      )}

      <form onSubmit={create} className="glass flex" style={{ marginTop: 16, padding: 16, borderRadius: 'var(--r-md)', flexWrap: 'wrap' }}>
        <input required value={name} onChange={e => setName(e.target.value)} placeholder="Workspace name — e.g. Nigeria child health Q1"
               style={{ flex: 2, minWidth: 200, padding: '9px 12px', border: '1px solid var(--line)', borderRadius: 'var(--r-sm)', background: 'rgba(255,255,255,.6)', font: '13.5px var(--sans)' }} />
        <input value={countries} onChange={e => setCountries(e.target.value)} placeholder="ISO3 list — NGA, ETH"
               style={{ flex: 1, minWidth: 150, padding: '9px 12px', border: '1px solid var(--line)', borderRadius: 'var(--r-sm)', background: 'rgba(255,255,255,.6)', font: '13.5px var(--sans)' }} />
        <button className="btn primary" disabled={creating}><Plus size={14} /> {creating ? '…' : 'Create'}</button>
        {err && <span className="muted" style={{ fontSize: 12 }}>{err}</span>}
      </form>

      {ws === null ? <div className="skeleton" style={{ height: 200, marginTop: 18 }} /> : (
        <div style={{ display: 'grid', gap: 12, marginTop: 18 }}>
          {ws.map(w => (
            <div key={w.ws_id} className="glass country-card" onClick={() => nav(`/workspace/${w.ws_id}`)}>
              <b className="serif" style={{ fontSize: 17 }}>{w.name}</b>
              <span className="faint" style={{ fontSize: 12.5, flex: 1, marginLeft: 10 }}>{w.description}</span>
              <span className="tag" style={{ border: '1px solid var(--line)' }}>
                {w.countries.length ? `${w.countries.length} countries` : 'no countries set'}
              </span>
              <span className="faint" style={{ fontSize: 11.5 }}>{w.created_at.slice(0, 10)}</span>
            </div>
          ))}
          {ws.length === 0 && <p className="muted">No workspaces yet — create the first above.</p>}
        </div>
      )}
    </div>
  )
}
