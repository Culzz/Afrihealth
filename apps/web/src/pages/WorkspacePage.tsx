import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft, Target, Upload, FileText, BookMarked, History, Search } from 'lucide-react'
import { api, Workspace, TargetRow, ProgressRow, WsDataRow, AnalysisRow, ReportListItem, ReportFull, AuditRow, Me } from '../api/client'
import { useAuth } from '../hooks/useAuth'

const TABS = ['Program', 'Data', 'Analyses', 'Reports', 'Audit'] as const
const INDICATOR_OPTS = ['u5m', 'dpt_cov', 'meas_cov', 'san_basic', 'water_basic', 'gdp_pc', 'phys_1k', 'nurses_1k', 'chexp_pctgdp', 'urb_pct']

export default function WorkspacePage() {
  const { wsid } = useParams()
  const [params, setParams] = useSearchParams()
  const tab = (params.get('tab') ?? 'Program') as typeof TABS[number]
  const { me } = useAuth()
  const [ws, setWs] = useState<Workspace | null>(null)
  const [targets, setTargets] = useState<TargetRow[]>([])
  const [progress, setProgress] = useState<ProgressRow[] | null>(null)
  const [data, setData] = useState<WsDataRow[] | null>(null)
  const [analyses, setAnalyses] = useState<AnalysisRow[] | null>(null)
  const [reports, setReports] = useState<ReportListItem[] | null>(null)
  const [openReport, setOpenReport] = useState<ReportFull | null>(null)
  const [audit, setAudit] = useState<AuditRow[]>([])
  const [busy, setBusy] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    if (!wsid || !me) return
    api.get<Workspace>(`/workspaces/${wsid}`).then(setWs).catch(() => setWs(null))
    api.get<TargetRow[]>(`/workspaces/${wsid}/targets`).then(setTargets).catch(() => {})
    api.get<ProgressRow[]>(`/workspaces/${wsid}/progress`).then(setProgress).catch(() => setProgress([]))
    api.get<{ rows: WsDataRow[] }>(`/workspaces/${wsid}/data`).then(d => setData(d.rows)).catch(() => setData([]))
    api.get<AnalysisRow[]>(`/workspaces/${wsid}/analyses`).then(setAnalyses).catch(() => setAnalyses([]))
    api.get<ReportListItem[]>(`/workspaces/${wsid}/reports`).then(setReports).catch(() => setReports([]))
    api.get<{ audit: AuditRow[] }>(`/workspaces/${wsid}/audit`).then(a => setAudit(a.audit)).catch(() => {})
  }, [wsid, me?.user?.user_id])

  if (me === null) return <p className="muted">Sign in to open this workspace.</p>
  if (ws === null) return <div className="skeleton" style={{ height: 240 }} />

  const setTab = (t: typeof tab) => setParams({ tab: t })

  return (
    <div>
      <Link to="/workspaces" className="muted" style={{ fontSize: 13, display: 'inline-flex', gap: 6, alignItems: 'center' }}>
        <ArrowLeft size={13} /> workspaces
      </Link>
      <h1 className="serif" style={{ margin: '10px 0 2px', fontSize: 30 }}>{ws.name}</h1>
      <p className="muted" style={{ fontSize: 13 }}>
        {ws.countries.length ? ws.countries.join(' · ') : 'no countries linked'} —
        organization data kept separate from national estimates
      </p>
      <div className="flex" style={{ gap: 6, margin: '14px 0 18px', flexWrap: 'wrap' }}>
        {TABS.map(t => (
          <button key={t} onClick={() => setTab(t)} className="btn ghost"
                  style={{ fontSize: 13, padding: '8px 14px', background: tab === t ? 'var(--accent-dark)' : undefined, color: tab === t ? '#fbf8f2' : undefined }}>
            {t}
          </button>
        ))}
      </div>
      {err && <p className="muted" style={{ fontSize: 12.5, color: 'var(--danger)' }}>{err}</p>}

      {tab === 'Program' && <ProgramTab wsid={wsid!} targets={targets} progress={progress} reload={reloadProgress} setErr={setErr} setBusy={setBusy} busy={busy} />}
      {tab === 'Data' && <DataTab wsid={wsid!} data={data} reload={reloadData} setErr={setErr} />}
      {tab === 'Analyses' && <AnalysesTab wsid={wsid!} analyses={analyses} reload={reloadAnalyses} setErr={setErr} />}
      {tab === 'Reports' && <ReportsTab wsid={wsid!} ws={ws} reports={reports} open={openReport} setOpen={setOpenReport} reload={reloadReports} setErr={setErr} />}
      {tab === 'Audit' && <AuditTable rows={audit} />}

      <p className="faint" style={{ fontSize: 11.5, marginTop: 26 }}>
        Every action here writes to the org audit trail. Program data you upload
        carries source "org-upload" and is never blended into national statistics.
      </p>
    </div>
  )

  /* ---------------- program (targets + progress) ---------------- */
  function ProgramTab(p: any) {
    const [form, setForm] = useState({ iso3: '', indicator: 'u5m', geography: '', baseline_year: '', baseline_value: '', target_value: '', target_year: '', notes: '' })
    const add = async (e: React.FormEvent) => {
      e.preventDefault()
      p.setErr(null)
      try {
        await api.post(`/workspaces/${p.wsid}/targets`, {
          iso3: form.iso3.toUpperCase(), indicator: form.indicator,
          geography: form.geography,
          baseline_year: numOrNull(form.baseline_year), baseline_value: numOrNull(form.baseline_value),
          target_value: numOrNull(form.target_value), target_year: numOrNull(form.target_year),
          notes: form.notes,
        })
        p.setForm({ ...form, iso3: '', geography: '', baseline_value: '', target_value: '', notes: '' })
        const t = await api.get<TargetRow[]>(`/workspaces/${p.wsid}/targets`)
        p.reload()
        setTargets(t)
      } catch (e2) { p.setErr(String(e2)) }
    }
    return (
      <div className="grid2">
        <div>
          <div className="glass" style={{ padding: 18 }}>
            <h2 style={{ display: 'inline-flex', gap: 8, alignItems: 'center', marginTop: 0 }}><Target size={16} /> Add a monitored indicator</h2>
            <form onSubmit={add} style={{ display: 'grid', gap: 8 }}>
              <select value={form.indicator} onChange={e => setForm({ ...form, indicator: e.target.value })} style={inp}>
                {INDICATOR_OPTS.map(o => <option key={o}>{o}</option>)}
              </select>
              <div className="flex" style={{ gap: 8 }}>
                <input required placeholder="ISO3 (NGA)" value={form.iso3} onChange={e => setForm({ ...form, iso3: e.target.value })} style={inp} />
                <input placeholder="Geography (Kano State) — optional" value={form.geography} onChange={e => setForm({ ...form, geography: e.target.value })} style={inp} />
              </div>
              <div className="flex" style={{ gap: 8 }}>
                <input placeholder="baseline year" inputMode="numeric" value={form.baseline_year} onChange={e => setForm({ ...form, baseline_year: e.target.value })} style={inp} />
                <input placeholder="baseline value" inputMode="decimal" value={form.baseline_value} onChange={e => setForm({ ...form, baseline_value: e.target.value })} style={inp} />
              </div>
              <div className="flex" style={{ gap: 8 }}>
                <input placeholder="target value" inputMode="decimal" value={form.target_value} onChange={e => setForm({ ...form, target_value: e.target.value })} style={inp} />
                <input placeholder="target year" inputMode="numeric" value={form.target_year} onChange={e => setForm({ ...form, target_year: e.target.value })} style={inp} />
              </div>
              <input placeholder="notes" value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} style={inp} />
              <button className="btn primary" disabled={p.busy === 't'}>{p.busy === 't' ? '…' : 'Add target'}</button>
            </form>
          </div>
        </div>
        <div>
          <div className="glass" style={{ padding: 18 }}>
            <h2 style={{ display: 'inline-flex', gap: 8, alignItems: 'center', marginTop: 0 }}><Search size={15} /> Progress vs targets</h2>
            {(p.progress as ProgressRow[] | null) === null ? <div className="skeleton" style={{ height: 140 }} /> : (
              (progress ?? []).length === 0 ? <p className="muted">Add a target to start tracking.</p> : (
                (progress ?? []).map(r => (
                  <div key={r.target_id} style={{ borderBottom: '1px solid var(--line)', padding: '10px 0' }}>
                    <div className="flex" style={{ gap: 8, flexWrap: 'wrap' }}>
                      <b>{r.iso3}</b><span className="faint">{r.indicator}</span>
                      {r.geography && <span className="tag" style={{ fontSize: 11 }}>{r.geography}</span>}
                      {r.actual && <span className="tag ok" style={{ fontSize: 11 }}>{r.actual.value} ({r.actual.year}, {r.actual.source})</span>}
                      {r.progress && <span className={`tag ${r.progress.status === 'on-track' ? 'ok' : r.progress.status === 'off-track' ? 'bad' : 'warn'}`} style={{ fontSize: 11 }}>
                        {r.progress.toward_target_pct != null ? `${r.progress.toward_target_pct}% → ` : ''}{r.progress.status}
                      </span>}
                    </div>
                    {r.progress?.note && <p className="faint" style={{ fontSize: 11.5, margin: '3px 0 0' }}>{r.progress.note}</p>}
                  </div>
                ))
              )
            )}
          </div>
        </div>
      </div>
    )
  }

  function DataTab({ wsid, data, reload }: any) {
    const [csv, setCsv] = useState('')
    const handleFile = async (f: File | null) => {
      if (f) setCsv(await f.text())
    }
    const parseAndPost = async (e: React.FormEvent) => {
      e.preventDefault(); setErr(null)
      try {
        const rows: any[] = []
        const lines = csv.trim().split(/\r?\n/).filter(Boolean)
        if (lines.length < 2) throw new Error('csv needs a header row + at least one data row')
        const head = lines[0].split(',').map(s => s.trim().toLowerCase())
        const need = ['iso3', 'indicator', 'year', 'value']
        for (const col of need) if (!head.includes(col)) throw new Error(`csv header missing column "${col}"`)
        for (const ln of lines.slice(1)) {
          const cells = ln.split(',')
          const r: any = { geography: '' }
          head.forEach((h, i) => { r[h] = (cells[i] ?? '').trim() })
          rows.push({ ...r, year: +r.year, value: +r.value, iso3: r.iso3.toUpperCase() })
        }
        const res = await api.post<{ rows_added: number; note: string }>(`/workspaces/${wsid}/data`, { rows })
        setCsv('')
        setErr(`added ${res.rows_added} rows · ${res.note}`)
        reload()
      } catch (e2) { setErr(String(e2).replace(/^Error: /, '')) }
    }
    return (
      <div className="glass" style={{ padding: 18 }}>
        <h2 style={{ display: 'inline-flex', gap: 8, alignItems: 'center', marginTop: 0 }}><Upload size={16} /> Upload your program data (CSV)</h2>
        <p className="muted" style={{ fontSize: 12.5 }}>
          Columns: <code>iso3,indicator,year,value[,geography]</code>. Subnational rows
          go in the geography column. Stored as-is with source "org-upload".
        </p>
        <input type="file" accept=".csv,text/csv" onChange={e => handleFile(e.target.files?.[0] ?? null)} style={{ fontSize: 13 }} />
        <textarea value={csv} onChange={e => setCsv(e.target.value)} rows={5} placeholder={'iso3,indicator,year,value,geography\nNGA,severe_wasting,2026,4.1,Kano State'}
                  style={{ width: '100%', marginTop: 10, font: '12px var(--mono, monospace)', padding: 10, border: '1px solid var(--line)', borderRadius: 'var(--r-sm)', background: 'rgba(255,255,255,.6)' }} />
        <button className="btn primary" onClick={parseAndPost} style={{ marginTop: 10 }}>Upload rows</button>
        {data !== null && (
          <p className="muted" style={{ fontSize: 12.5, marginTop: 12 }}>
            {data.length} rows stored{data.length ? ' — latest ' + (data[0]?.iso3 ?? '') : ''} · sources: {(data?.length ? ['org-upload'] : []).join(', ') || 'none'}
          </p>
        )}
      </div>
    )
  }

  function AnalysesTab({ wsid, analyses, reload }: any) {
    const [title, setTitle] = useState('')
    const [notes, setNotes] = useState('')
    const [view, setView] = useState(JSON.stringify({ mode: 'vuln', countries: ws?.countries ?? [] }, null, 2))
    const save = async (e: React.FormEvent) => {
      e.preventDefault(); setErr(null)
      try {
        JSON.parse(view)                                   // must be valid JSON
        await api.post(`/workspaces/${wsid}/analyses`, { title, view_state: JSON.parse(view), notes })
        setTitle(''); setNotes(''); reload()
      } catch (e2) { setErr('analysis state must be valid JSON: ' + String(e2).replace(/^Error: \d+ /, '')) }
    }
    return (
      <div className="grid2">
        <div className="glass" style={{ padding: 18 }}>
          <h2 style={{ display: 'inline-flex', gap: 8, alignItems: 'center', marginTop: 0 }}><BookMarked size={15} /> Save an analysis</h2>
          <form onSubmit={save} style={{ display: 'grid', gap: 8 }}>
            <input required placeholder="title — e.g. Atlas vuln view Q3" value={title} onChange={e => setTitle(e.target.value)} style={inp} />
            <textarea rows={4} value={view} onChange={e => setView(e.target.value)} style={{ ...inp, font: '11.5px monospace' }} />
            <input placeholder="notes" value={notes} onChange={e => setNotes(e.target.value)} style={inp} />
            <button className="btn primary">Save analysis</button>
          </form>
        </div>
        <div className="glass" style={{ padding: 18 }}>
          <h2 style={{ marginTop: 0 }}>Saved analyses</h2>
          {analyses === null ? <div className="skeleton" style={{ height: 120 }} /> : analyses!.length === 0
            ? <p className="muted">Nothing saved yet.</p> : (
              (analyses ?? []).map(a => (
                <div key={a.analysis_id} style={{ borderBottom: '1px solid var(--line)', padding: '8px 0' }}>
                  <b style={{ fontSize: 13.5 }}>{a.title}</b>
                  <p className="faint" style={{ fontSize: 11.5, margin: '2px 0' }}>{a.notes || '—'} · {a.created_at.slice(0, 10)}</p>
                </div>
              )))}
        </div>
      </div>
    )
  }

  function ReportsTab({ wsid, ws, reports, open, setOpen, reload }: any) {
    const sel = ws.countries.slice(0, 8)
    const [countries, setCountries] = useState(sel.join(','))
    const [period, setPeriod] = useState('')
    const [genBusy, setGenBusy] = useState(false)
    const generate = async () => {
      setGenBusy(true); setErr(null); setOpen(null)
      try {
        const rep = await api.post<ReportFull>(`/workspaces/${wsid}/reports`, {
          countries: countries.split(',').map(s => s.trim().toUpperCase()).filter(Boolean),
          indicators: ['u5m', 'dpt_cov'], period_text: period,
        })
        setOpen(rep); reload()
      } catch (e2) { setErr(String(e2).replace(/^Error: \d+ /, '')) }
      setGenBusy(false)
    }
    return (
      <div className="grid2">
        <div className="glass" style={{ padding: 18 }}>
          <h2 style={{ display: 'inline-flex', gap: 8, alignItems: 'center', marginTop: 0 }}><FileText size={16} /> Evidence-to-Report Engine</h2>
          <p className="muted" style={{ fontSize: 12.5 }}>
            Validate flags → analysis with intervals and disparities → cited narrative
            → versioned report (+ branded PDF). Deterministic: the same selection always
            produces the same numbers, every figure carries its source label.
          </p>
          <label className="muted" style={{ fontSize: 12 }}>Countries (ISO3, comma-separated)
            <input value={countries} onChange={e => setCountries(e.target.value)} style={inp} />
          </label>
          <label className="muted" style={{ fontSize: 12, display: 'block', marginTop: 8 }}>Reporting period label
            <input placeholder="e.g. Quarter 4 2026 review" value={period} onChange={e => setPeriod(e.target.value)} style={inp} />
          </label>
          <button className="btn primary" onClick={generate} disabled={genBusy} style={{ marginTop: 12 }}>
            {genBusy ? 'computing…' : 'Generate report'}
          </button>
        </div>
        <div style={{ display: 'grid', gap: 14 }}>
          <div className="glass" style={{ padding: 18 }}>
            <h2 style={{ marginTop: 0, fontSize: 15 }}>Report runs</h2>
            {reports === null ? <div className="skeleton" style={{ height: 100 }} /> : (reports ?? []).length === 0
              ? <p className="muted">No runs yet.</p> : (reports ?? []).map((r: ReportListItem) => (
                <div key={r.report_id} className="flex" style={{ borderBottom: '1px solid var(--line)', padding: '8px 0', gap: 8 }}>
                  <b style={{ fontSize: 13 }}>v{r.version}</b>
                  <span className="faint" style={{ fontSize: 11.5, flex: 1 }}>{r.created_at.slice(0, 16).replace('T', ' ')}Z</span>
                  <button className="btn ghost" style={{ fontSize: 11.5, padding: '5px 10px' }}
                          onClick={() => api.get<ReportFull>(`/workspaces/${wsid}/reports/${r.report_id}`).then(setOpen).catch(e => setErr(String(e)))}>
                    open
                  </button>
                  <a className="btn ghost" style={{ fontSize: 11.5, padding: '5px 10px' }}
                     href={`${import.meta.env.VITE_API_BASE_URL ?? ''}/api/v1/workspaces/${wsid}/reports/${r.report_id}?format=pdf`}>
                    PDF
                  </a>
                </div>
              ))}
          </div>
          {open && <ReportView rep={open} />}
        </div>
      </div>
    )
  }

  function ReportView({ rep }: { rep: ReportFull }) {
    return (
      <div className="glass" style={{ padding: 18, maxHeight: '70vh', overflow: 'auto' }}>
        <div className="flex" style={{ alignItems: 'center', gap: 8 }}>
          <b className="serif" style={{ fontSize: 16 }}>Report v{rep.version}</b>
          <span className="faint" style={{ fontSize: 11.5 }}>
            {rep.created_at.slice(0, 16).replace('T', ' ')}Z · {rep.computed.validate.length} data flags
          </span>
        </div>
        <p style={{ fontSize: 13, lineHeight: 1.55 }}>{rep.narrative.summary}</p>
        {rep.computed.validate.length > 0 && (
          <div style={{ margin: '10px 0', padding: 10, background: 'rgba(180,83,9,.08)', borderRadius: 'var(--r-sm)' }}>
            <b style={{ fontSize: 12.5 }}>Validate — flagged evidence</b>
            {rep.computed.validate.map(v => (
              <p key={v.iso3} style={{ fontSize: 12, margin: '4px 0' }}>
                <b>{v.iso3}</b>: {v.flags.join(' · ')}
              </p>
            ))}
          </div>
        )}
        <b style={{ fontSize: 12.5 }}>Findings</b>
        {rep.narrative.findings.map((f, i) => (
          <p key={i} style={{ fontSize: 12.5, margin: '5px 0', lineHeight: 1.5 }}>
            {f.kind === 'disparity' ? '★ ' : '· '}{f.text}
          </p>
        ))}
        <b style={{ fontSize: 12.5 }}>Evidence</b>
        {rep.narrative.evidence.map(ev => (
          <p key={ev.id} style={{ fontSize: 11.5, margin: '3px 0' }}>
            <b>[{ev.id}]</b> {ev.country}: {ev.text}
          </p>
        ))}
        <b style={{ fontSize: 12.5 }}>Limitations</b>
        <ul style={{ fontSize: 11.5, margin: '4px 0', paddingLeft: 18 }}>
          {rep.narrative.limitations.map((l, i) => <li key={i}>{l}</li>)}
        </ul>
      </div>
    )
  }

  function AuditTable({ rows }: { rows: AuditRow[] }) {
    return (
      <div className="glass" style={{ padding: 18 }}>
        <h2 style={{ display: 'inline-flex', gap: 8, alignItems: 'center', marginTop: 0 }}><History size={15} /> Audit trail</h2>
        {rows.length === 0 ? <p className="muted">No entries yet.</p> : (
          <table style={{ width: '100%', fontSize: 12 }}>
            <thead><tr><th style={th}>when</th><th style={th}>action</th><th style={th}>detail</th></tr></thead>
            <tbody>
              {rows.map(a => (
                <tr key={a.audit_id}>
                  <td style={td}>{a.ts.slice(0, 16).replace('T', ' ')}</td>
                  <td style={td}><code>{a.action}</code></td>
                  <td style={td}>{a.detail?.slice(0, 90)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    )
  }

  async function reloadProgress() {
    if (!wsid) return
    setProgress(await api.get<ProgressRow[]>(`/workspaces/${wsid}/progress`).catch(() => null))
  }
  async function reloadData() {
    if (!wsid) return
    const d = await api.get<{ rows: WsDataRow[] }>(`/workspaces/${wsid}/data`).catch(() => null)
    setData(d?.rows ?? [])
  }
  async function reloadAnalyses() {
    if (!wsid) return
    setAnalyses(await api.get<AnalysisRow[]>(`/workspaces/${wsid}/analyses`).catch(() => null))
  }
  async function reloadReports() {
    if (!wsid) return
    setReports(await api.get<ReportListItem[]>(`/workspaces/${wsid}/reports`).catch(() => null))
  }
}

const inp = {
  width: '100%', padding: '8px 11px',
  border: '1px solid var(--line)', borderRadius: 'var(--r-sm)',
  background: 'rgba(255,255,255,.65)', font: '13px var(--sans)',
}
function numOrNull(v: string): number | null {
  const t = v.trim()
  return t === '' ? null : (Number.isFinite(+t) ? +t : null)
}
const th: React.CSSProperties = { textAlign: 'left', fontWeight: 600, padding: '4px 8px' }
const td: React.CSSProperties = { padding: '4px 8px', verticalAlign: 'top' }
