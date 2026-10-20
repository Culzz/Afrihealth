import { NavLink, Outlet } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { api, Health } from './api/client'

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  useEffect(() => {
    api.get<Health>('/health').then(setHealth).catch(() => setHealth(null))
  }, [])
  return (
    <div>
      <header className="top">
        <div className="brand">Afri<span>Health</span> · Risk Atlas</div>
        <nav>
          <NavLink to="/atlas" className={({ isActive }) => isActive ? 'active' : ''}>Atlas</NavLink>
          <NavLink to="/methodology" className={({ isActive }) => isActive ? 'active' : ''}>Methodology</NavLink>
        </nav>
        <div className="muted" style={{ marginLeft: 'auto', fontSize: 13 }}>
          {health ? `model ${health.model_version} · data through ${health.data_max_year}` : 'api offline'}
        </div>
      </header>
      <div className="disclaimer">
        Population-level decision support for policy exploration — not individual diagnosis,
        surveillance replacement, or clinical guidance. SHAP attributions describe model behaviour, not causation.
      </div>
      <main><Outlet /></main>
      <div style={{ maxWidth: 1180, margin: '0 auto', padding: '0 26px 40px' }} className="footer-note">
        Built on World Bank WDI (CC BY 4.0). Every value is traceable: dataset version + model version + source URL.
      </div>
    </div>
  )
}
