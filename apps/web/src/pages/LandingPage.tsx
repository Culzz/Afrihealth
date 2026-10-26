import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  ArrowRight, Database, BrainCircuit, Sparkles, ShieldCheck,
  Droplets, Syringe, Store, GraduationCap, Layers,
} from 'lucide-react'
import { api, Atlas, Forecast, colors, riskFill, riskLevel } from '../api/client'

/** Measured in Release 1 (see MODEL_CARD.md) — locked 2021–24 holdout. */
const MEASURED = { mae: 3.49, naive: 5.06, lift: 31, obs: 14400, forecasts: 162 }

export default function LandingPage() {
  const nav = useNavigate()
  const [atlas, setAtlas] = useState<Atlas[] | null>(null)
  const [nga, setNga] = useState<Forecast | null>(null)

  useEffect(() => {
    api.get<Atlas[]>('/atlas').then(setAtlas).catch(() => setAtlas([]))
    api.get<Forecast[]>('/countries/NGA/forecasts')
      .then(fs => setNga(fs[0] ?? null)).catch(() => {})
  }, [])

  const withData = (atlas ?? []).filter(r => r.u5m != null)
  const critical = [...withData].sort((a, b) => b.u5m! - a.u5m!).slice(0, 4)
  const year = withData[0]?.year ?? 2024

  return (
    <article>
      {/* ---------- hero ---------- */}
      <section className="hero">
        <div>
          <span className="kicker"><Sparkles size={13} /> Population health intelligence</span>
          <h1 style={{ margin: '18px 0 14px', fontSize: 'clamp(2.1rem, 1.3rem + 3.2vw, 3.4rem)' }}>
            Where childhood survival <span className="serif-i" style={{ color: 'var(--accent)' }}>is headed, honestly
            measured.</span>
          </h1>
          <p className="lede">
            AfriHealth forecasts under-five mortality for all 54 African Union countries
            from World Bank evidence — every prediction comes with a 90% interval, an
            explanation of what moved it, and a paper trail back to its source. No imputed
            data. Baselines beaten first, claims second.
          </p>
          <div className="flex" style={{ marginTop: 26 }}>
            <Link to="/atlas" className="btn primary">Explore the Atlas <ArrowRight size={16} /></Link>
            <Link to="/methodology" className="btn ghost">How we know it's true</Link>
          </div>
          <div className="stats4" style={{ marginTop: 30, maxWidth: 560 }}>
            <div className="glass stat"><div className="v num">54</div><div className="l">countries</div></div>
            <div className="glass stat"><div className="v num">{(MEASURED.obs / 1000).toFixed(1)}k</div><div className="l">observations</div></div>
            <div className="glass stat"><div className="v num">{MEASURED.forecasts}</div><div className="l">forecasts 2025–27</div></div>
            <div className="glass stat"><div className="v num">−{MEASURED.lift}%</div><div className="l">MAE vs naive baseline</div></div>
          </div>
        </div>
        <div className="hero-media">
          <div className="img-frame">
            <img src="/img/hero.jpg" alt="A midwife with a mother during a home visit" width="700" height="820" />
          </div>
          <div className="float-card">
            <div className="v num">{MEASURED.mae} <span style={{ color: 'var(--faint)', fontSize: 15 }}>MAE</span></div>
            <div className="l">vs {MEASURED.naive} naive · locked 2021–24 holdout · u5m-lgb-v1</div>
          </div>
        </div>
      </section>

      {/* ---------- how it works ---------- */}
      <section className="section">
        <div className="section-head">
          <h2>Three layers behind every number</h2><div className="rule" />
          <span className="faint" style={{ fontSize: 13 }}>dataset v1__20261019</span>
        </div>
        <div className="grid3">
          <div className="glass">
            <div className="icon-badge"><Database size={20} /></div>
            <h3 style={{ margin: '14px 0 6px' }}>Observed burden</h3>
            <p className="muted" style={{ fontSize: 14, marginTop: 0 }}>
              WHO-scale mortality data joined to nine World Bank driver series. Gaps stay
              visibly flagged — nothing is silently zero-filled or imputed.
            </p>
          </div>
          <div className="glass">
            <div className="icon-badge"><BrainCircuit size={20} /></div>
            <h3 style={{ margin: '14px 0 6px' }}>Predicted risk</h3>
            <p className="muted" style={{ fontSize: 14, marginTop: 0 }}>
              A LightGBM model validated on a holdout it never saw, registered as
              <b> u5m-lgb-v1</b> with {MEASURED.forecasts} calibrated forecasts for 2025–2027.
            </p>
          </div>
          <div className="glass">
            <div className="icon-badge"><Layers size={20} /></div>
            <h3 style={{ margin: '14px 0 6px' }}>Explained, not mystical</h3>
            <p className="muted" style={{ fontSize: 14, marginTop: 0 }}>
              SHAP attributions show which drivers moved each forecast, exceedance
              probabilities quantify the risk of staying above critical thresholds.
            </p>
          </div>
        </div>
      </section>

      {/* ---------- photo mosaic ---------- */}
      <section className="section">
        <div className="section-head">
          <h2>The ground this is built on</h2><div className="rule" />
        </div>
        <div className="mosaic">
          <figure>
            <img src="/img/vaccination.jpg" alt="Immunisation session at a rural health post" loading="lazy" decoding="async" />
            <figcaption><Syringe size={11} style={{ verticalAlign: -1.5, marginRight: 4 }} />Immunisation coverage</figcaption>
          </figure>
          <figure>
            <img src="/img/water.jpg" alt="Women fetching water from a village well" loading="lazy" decoding="async" />
            <figcaption><Droplets size={11} style={{ verticalAlign: -1.5, marginRight: 4 }} />Water access</figcaption>
          </figure>
          <figure>
            <img src="/img/market.jpg" alt="Women selling vegetables at a street market" loading="lazy" decoding="async" />
            <figcaption><Store size={11} style={{ verticalAlign: -1.5, marginRight: 4 }} />Economic conditions</figcaption>
          </figure>
          <figure>
            <img src="/img/school.jpg" alt="Children at a township primary school" loading="lazy" decoding="async" />
            <figcaption><GraduationCap size={11} style={{ verticalAlign: -1.5, marginRight: 4 }} />Urbanisation & services</figcaption>
          </figure>
        </div>
        <p className="faint" style={{ fontSize: 11.5, marginTop: 10 }}>
          Photos: Wikimedia Commons (CC BY-SA) — Vhikman Gee, Marcellin yao, David Oduut/Linkedug, Godot13. See credits below.
        </p>
      </section>

      {/* ---------- the signal, live ---------- */}
      <section className="section">
        <div className="section-head">
          <h2>What the map shows right now</h2>
          <div className="rule" />
          {year && <span className="faint" style={{ fontSize: 13 }}>u5m, per 1,000 live births · {year}</span>}
        </div>
        <div className="grid2">
          <div className="glass">
            {atlas === null ? <div className="skeleton" style={{ height: 240 }} /> : (
              <div>
                <h3 style={{ marginTop: 0 }}>Highest burden, {year}</h3>
                <div style={{ display: 'grid', gap: 10, marginTop: 14 }}>
                  {critical.map(r => (
                    <div key={r.iso3} className="country-card" onClick={() => nav(`/country/${r.iso3}`)}>
                      <span className="flag-dot" style={{ background: riskFill[riskLevel(r.u5m!)] }} />
                      <b style={{ fontSize: 14.5 }}>{r.country}</b>
                      <span className="num muted" style={{ marginLeft: 'auto', fontWeight: 650, fontSize: 18 }}>
                        {r.u5m}
                      </span>
                      <span className={`tag ${riskLevel(r.u5m!) !== 'moderate' && riskLevel(r.u5m!) !== 'elevated' ? 'bad' : 'warn'}`}>
                        {riskLevel(r.u5m!)}
                      </span>
                    </div>
                  ))}
                </div>
                <div className="scale" style={{ marginTop: 18 }}>
                  {(['moderate', 'elevated', 'high', 'critical'] as const).map(k => (
                    <span key={k} className="s"><span className="swatch" style={{ background: colors[k] }} />{k}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
          <div className="glass" style={{ borderRadius: 'var(--r-lg)' }}>
            <h3 style={{ marginTop: 0 }}>Forecast spotlight — Nigeria</h3>
            <p className="muted" style={{ fontSize: 13.5 }}>
              One of {MEASURED.forecasts} registered country-year forecasts, fetched live from the API.
            </p>
            {nga ? (
              <div className="kpi" style={{ background: 'rgba(255,255,255,.55)', borderRadius: 'var(--r-md)', padding: 16 }}>
                <div className="l">under-five mortality, {nga.year}</div>
                <div className="v" style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
                  {nga.yhat}
                  <span className="muted" style={{ fontSize: 14 }}>
                    90% interval {nga.lo90} – {nga.hi90}
                  </span>
                </div>
                <div style={{ marginTop: 10 }}>
                  <b style={{ fontSize: 15 }}>P(stay above 70) = {nga.p_gt_70}</b>
                  <p className="faint" style={{ fontSize: 12, margin: '6px 0 0' }}>
                    driven mainly by its own recent mortality level (SHAP +{nga.top_drivers_shap?.[0]?.shap?.toFixed(1) ?? '—'})
                  </p>
                </div>
              </div>
            ) : <div className="skeleton" style={{ height: 130 }} />}
            <div className="flex" style={{ marginTop: 16 }}>
              <Link to="/country/NGA" className="btn primary" style={{ padding: '10px 18px', fontSize: 14 }}>
                Open Nigeria <ArrowRight size={14} />
              </Link>
              <Link to="/atlas" className="btn ghost" style={{ padding: '10px 18px', fontSize: 14 }}>All 54</Link>
            </div>
          </div>
        </div>
      </section>

      {/* ---------- safeguards + CTA ---------- */}
      <section className="section cta-banner glass">
        <ShieldCheck size={26} style={{ color: 'var(--accent)' }} />
        <h2 style={{ margin: '12px auto 8px', maxWidth: '22em' }}>
          Decision support with the safety rails visible.
        </h2>
        <p className="muted" style={{ maxWidth: '38em', margin: '0 auto 22px' }}>
          Population-level exploration — not clinical guidance, not outbreak surveillance.
          Missing data is flagged, never filled. Attribution explains model behaviour, not
          causation. Every value traces to source → dataset version → model version.
        </p>
        <Link to="/atlas" className="btn primary">Start from the map <ArrowRight size={16} /></Link>
        <p className="faint" style={{ fontSize: 11.5, marginTop: 26 }}>
          Photos (Wikimedia Commons, CC BY-SA 4.0): “African Midwife” © Vhikman Gee ·
          “Séance de vaccination” © Marcellin yao · “Women at work, tomato market” © David Oduut/Linkedug ·
          “School children, Zwelihle” © Godot13 · “Fetching water from the well” © Meritkosy.
        </p>
      </section>
    </article>
  )
}
