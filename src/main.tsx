import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { RiskDashboard } from './components/RiskDashboard'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RiskDashboard />
  </StrictMode>,
)
