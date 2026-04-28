import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { CreditDashboard } from './components/CreditDashboard'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <CreditDashboard />
  </StrictMode>,
)
