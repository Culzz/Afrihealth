import { NavLink, Outlet } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { Compass, Home, BookOpen, Activity } from 'lucide-react'
import { api, Health } from './api/client'

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  useEffect(() => {
    api.get<Health>('/health').then(setHealth).catch(() => setHealth(null))
  }, [])
  return (
    <div>
      <header className="top">
        <div className="brand">
          <img src="/favicon.svg" alt="" className="mark" aria-hidden />
          <span>Afri<em>Health</em></span>
        </div>
        <nav>
          <NavLink to="/" end className={({ isActive }) => isActive ? 'active' : ''}>
            <Home size={15} strokeWidth={2.2} /> Home
          </NavLink>
          <NavLink to="/atlas" className={({ isActive }) => isActive ? 'active' : ''}>
            <Compass size={15} strokeWidth={2.2} /> Atlas
          </NavLink>
          <NavLink to="/methodology" className={({ isActive }) => isActive ? 'active' : ''}>
            <BookOpen size={15} strokeWidth={2.2} /> Methodology
          </NavLink>
        </nav>
        {health ? (
          <span className="healthchip"><span className="dot" />{health.model_version} · data through {health.data_max_year}</span>
        ) : (
          <span className="healthchip off"><span className="dot" /> connecting…</span>
        )}
      </header>
      <div className="disclaimer">
        <Activity size={11} style={{ verticalAlign: -1.5, marginRight: 4 }} />
        Population-level decision support for policy exploration — not individual diagnosis,
        surveillance replacement, or clinical guidance. SHAP attributions describe model
        behaviour, not causation.
      </div>
      <main><Outlet /></main>
      <div className="footer-note">
        Built on World Bank WDI (CC BY 4.0). Every value is traceable: dataset version +
        model version + source URL.
      </div>
    </div>
  )
}
