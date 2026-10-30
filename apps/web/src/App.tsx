import { NavLink, Outlet } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { Compass, Home, BookOpen, Activity, BellRing, ArrowUpDown,
         FolderOpen, ShieldCheck, SlidersHorizontal, UserRound } from 'lucide-react'
import { api, Health } from './api/client'
import { useAuth } from './hooks/useAuth'

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const { me } = useAuth()
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
          <NavLink to="/alerts" className={({ isActive }) => isActive ? 'active' : ''}>
            <BellRing size={15} strokeWidth={2.2} /> Alerts
          </NavLink>
          <NavLink to="/compare" className={({ isActive }) => isActive ? 'active' : ''}>
            <ArrowUpDown size={15} strokeWidth={2.2} /> Compare
          </NavLink>
          <NavLink to="/quality" className={({ isActive }) => isActive ? 'active' : ''}>
            <ShieldCheck size={15} strokeWidth={2.2} /> Quality
          </NavLink>
          <NavLink to="/priority" className={({ isActive }) => isActive ? 'active' : ''}>
            <SlidersHorizontal size={15} strokeWidth={2.2} /> Priority
          </NavLink>
          <NavLink to="/methodology" className={({ isActive }) => isActive ? 'active' : ''}>
            <BookOpen size={15} strokeWidth={2.2} /> Methodology
          </NavLink>
        </nav>
        {me ? (
          <NavLink to="/workspaces" className="healthchip" style={{ textDecoration: 'none' }}>
            <FolderOpen size={11} style={{ verticalAlign: -1.5, marginRight: 3 }} />
            {me.user.display_name} · {me.user.org_name}
          </NavLink>
        ) : (
          <NavLink to="/login" className="healthchip" style={{ textDecoration: 'none' }}>
            <UserRound size={11} style={{ verticalAlign: -1.5, marginRight: 3 }} />
            Sign in
          </NavLink>
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
