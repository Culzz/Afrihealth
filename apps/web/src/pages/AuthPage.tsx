import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { KeyRound, ArrowLeft } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'

export default function AuthPage({ mode }: { mode: 'login' | 'join' }) {
  const nav = useNavigate()
  const { login, register, error } = useAuth()
  const [email, setEmail] = useState('')
  const [pw, setPw] = useState('')
  const [org, setOrg] = useState('')
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true); setMsg(null)
    let ok: boolean
    if (mode === 'login') ok = await login(email, pw)
    else ok = await register(org, name, email, pw)
    setBusy(false)
    if (ok) nav('/workspaces')
    else if (mode === 'join') setMsg('Check the fields — passwords need 10+ characters.')
  }

  return (
    <div style={{ maxWidth: 430, margin: '3vh auto 0' }}>
      <Link to="/" className="muted" style={{ fontSize: 13, display: 'inline-flex', gap: 6, alignItems: 'center' }}>
        <ArrowLeft size={13} /> back to atlas
      </Link>
      <span className="kicker" style={{ marginTop: 18 }}><KeyRound size={13} /> {mode === 'login' ? 'Sign in' : 'Create organization'}</span>
      <h1 className="serif" style={{ margin: '12px 0 4px', fontSize: 30 }}>
        {mode === 'login' ? 'Welcome back' : 'Start your evidence workspace'}
      </h1>
      <p className="muted" style={{ fontSize: 13.5 }}>
        {mode === 'join'
          ? 'One account per organization. Passwords are stored salted and PBKDF2-hashed; sessions are random tokens — only their SHA-256 is kept.'
          : null}
      </p>
      <form onSubmit={submit} className="glass" style={{ display: 'grid', gap: 10, padding: 20, borderRadius: 'var(--r-md)' }}>
        {mode === 'join' && (
          <>
            <label className="muted" style={{ fontSize: 12 }}>Organization name
              <input required value={org} onChange={e => setOrg(e.target.value)} style={inp} placeholder="e.g. Baobab Health Partners" />
            </label>
            <label className="muted" style={{ fontSize: 12 }}>Your name
              <input required value={name} onChange={e => setName(e.target.value)} style={inp} placeholder="Display name" />
            </label>
          </>
        )}
        <label className="muted" style={{ fontSize: 12 }}>Email
          <input required type="email" value={email} onChange={e => setEmail(e.target.value)} style={inp} placeholder="you@organization.org" />
        </label>
        <label className="muted" style={{ fontSize: 12 }}>Password
          <input required type="password" minLength={10} value={pw} onChange={e => setPw(e.target.value)} style={inp}
                 placeholder="10+ characters" />
        </label>
        {(error || msg) && <p className="muted" style={{ fontSize: 12.5, color: 'var(--danger)' }}>{error || msg}</p>}
        <button className="btn primary" disabled={busy} style={{ marginTop: 4 }}>
          {busy ? '…' : mode === 'login' ? 'Sign in' : 'Create organization'}
        </button>
        <p className="muted" style={{ fontSize: 12, textAlign: 'center', margin: 0 }}>
          {mode === 'login'
            ? <>No account? <Link to="/join">Create one</Link></>
            : <>Already have one? <Link to="/login">Sign in</Link></>}
        </p>
      </form>
      <p className="faint" style={{ fontSize: 11.5, marginTop: 14 }}>
        Recorded in the model card: no email verification yet — registration trusts the address you enter.
        An email provider is an explicit R3+ add-on before this layer is offered for real bookings.
      </p>
    </div>
  )
}

const inp = {
  width: '100%', marginTop: 4, padding: '9px 12px',
  border: '1px solid var(--line)', borderRadius: 'var(--r-sm)',
  background: 'rgba(255,255,255,.6)', font: '13.5px var(--sans)',
}
