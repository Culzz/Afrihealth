import React from 'react'
import ReactDOM from 'react-dom/client'
import { HashRouter, Routes, Route } from 'react-router-dom'
import App from './App'
import LandingPage from './pages/LandingPage'
import AtlasPage from './pages/AtlasPage'
import ForecastPage from './pages/ForecastPage'
import MethodologyPage from './pages/MethodologyPage'
import AlertsPage from './pages/AlertsPage'
import ComparePage from './pages/ComparePage'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <HashRouter>
      <Routes>
        <Route path="/" element={<App />}>
          <Route index element={<LandingPage />} />
          <Route path="atlas" element={<AtlasPage />} />
          <Route path="country/:iso3" element={<ForecastPage />} />
          <Route path="alerts" element={<AlertsPage />} />
          <Route path="compare" element={<ComparePage />} />
          <Route path="methodology" element={<MethodologyPage />} />
        </Route>
      </Routes>
    </HashRouter>
  </React.StrictMode>,
)
