import { useEffect, useState } from 'react'
import { api } from '../api/client'

export default function MethodologyPage() {
  const [card, setCard] = useState<string | null>(null)
  useEffect(() => {
    fetch(`${import.meta.env.VITE_API_BASE_URL ?? ''}/api/v1/model-card`)
      .then(r => r.text()).then(setCard)
      .catch(() => setCard('Model card unavailable — API offline.'))
  }, [])
  return (
    <div>
      <h1>Methodology & evidence</h1>
      <div className="grid2">
        <div className="panel">
          <h2 style={{ marginTop: 4 }}>Model card (served by the API)</h2>
          {card === null
            ? <div className="skeleton" style={{ height: 380 }} />
            : <pre style={{ whiteSpace: 'pre-wrap', font: '13px/1.55 Consolas,monospace', margin: 0,
                            fontFamily: 'Consolas, monospace' }}>{card}</pre>}
        </div>
        <div className="panel">
          <h2 style={{ marginTop: 4 }}>The three-layer framework</h2>
          <ol>
            <li><b>Observed burden</b> — reported/modelled values with source, unit, coverage flags.</li>
            <li><b>Predicted risk</b> — validated forecasts with uncertainty + SHAP explanations.</li>
            <li><b>Vulnerability</b> — where burden overlaps weak capacity (Release 2).</li>
          </ol>
          <h2>Evaluation invariants</h2>
          <ul>
            <li>No random splits on panel data — expanding-window only (tested).</li>
            <li>Baselines first: models must beat naive_last by evidence.</li>
            <li>Missing data is flagged, never zero-filled (tested).</li>
            <li>Every number traceable: source → dataset version → model version.</li>
          </ul>
          <a className="muted" href="/api/v1/exports/panel.csv">⬇ Download the full dataset (CSV)</a>
        </div>
      </div>
    </div>
  )
}
