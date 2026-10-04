import { useEffect, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api, clearToken, getToken, Settings } from './api/client'
import AuthPage from './features/AuthPage'
import DashboardPage from './features/DashboardPage'
import AccountsPage from './features/AccountsPage'
import TransactionsPage from './features/TransactionsPage'
import SettingsPage from './features/SettingsPage'
import PlanningPage from './features/PlanningPage'
import ForecastPage from './features/ForecastPage'
import SavingsPage from './features/SavingsPage'
import BudgetsPage from './features/BudgetsPage'
import InvestmentsPage from './features/InvestmentsPage'
import ImportExportPage from './features/ImportExportPage'
import ScenariosPage from './features/ScenariosPage'

type Section = 'dashboard' | 'transactions' | 'accounts' | 'planning' | 'forecast' | 'savings' | 'budgets' | 'investments' | 'imports' | 'scenarios' | 'settings'
const sections: { id: Section; label: string; icon: string }[] = [
  { id: 'dashboard', label: 'Resumen', icon: '◫' },
  { id: 'transactions', label: 'Movimientos', icon: '⇄' },
  { id: 'accounts', label: 'Cuentas', icon: '▣' },
  { id: 'planning', label: 'Planificación', icon: '▤' },
  { id: 'forecast', label: 'Previsión', icon: '◷' },
  { id: 'savings', label: 'Ahorro', icon: '◇' },
  { id: 'budgets', label: 'Presupuestos', icon: '▥' },
  { id: 'investments', label: 'Inversiones', icon: '◈' },
  { id: 'imports', label: 'Importar y exportar', icon: '⇅' },
  { id: 'scenarios', label: 'Simulador', icon: '◎' },
  { id: 'settings', label: 'Configuración', icon: '⚙' },
]

export default function App() {
  const queryClient = useQueryClient()
  const [token, updateToken] = useState(getToken())
  const [section, setSection] = useState<Section>('dashboard')
  const me = useQuery({ queryKey: ['me'], queryFn: () => api<{ id: number; email: string }>('/auth/me'), enabled: !!token })
  const settings = useQuery({ queryKey: ['settings'], queryFn: () => api<Settings>('/settings'), enabled: !!token })
  useEffect(() => { document.documentElement.dataset.theme = token ? settings.data?.theme || 'light-teal' : 'light-teal' }, [token, settings.data?.theme])
  if (!token) return <AuthPage onAuthenticated={(newToken) => updateToken(newToken)} />

  const logout = () => {
    clearToken()
    queryClient.clear()
    updateToken(null)
  }
  const title = sections.find((item) => item.id === section)?.label
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark">S</span><span>Spider<span className="brand-accent">Finance</span></span></div>
      <div className="nav-caption">ESPACIO PERSONAL</div>
      <nav aria-label="Principal">
        {sections.map((item) => <button key={item.id} className={`nav-item ${section === item.id ? 'active' : ''}`} onClick={() => setSection(item.id)}>
          <span className="nav-icon" aria-hidden="true">{item.icon}</span>{item.label}
        </button>)}
      </nav>
      <div className="sidebar-bottom"><div className="avatar">{me.data?.email?.[0]?.toUpperCase() || 'U'}</div>
        <div className="account-label"><strong>Mi espacio</strong><small>{me.data?.email || 'Cargando...'}</small></div>
        <button className="icon-button" title="Cerrar sesión" onClick={logout}>↪</button>
      </div>
    </aside>
    <div className="main-shell">
      <header className="topbar"><div><span className="eyebrow">FINANZAS PERSONALES</span><h1>{title}</h1></div><div className="topbar-date">{new Intl.DateTimeFormat(settings.data?.locale || 'es-ES', { timeZone: settings.data?.timezone || 'Europe/Madrid', day: 'numeric', month: 'long', year: 'numeric' }).format(new Date())}</div></header>
      <main className="content">
        {section === 'dashboard' && <DashboardPage onNavigate={setSection} />}
        {section === 'transactions' && <TransactionsPage />}
        {section === 'accounts' && <AccountsPage />}
        {section === 'planning' && <PlanningPage />}
        {section === 'forecast' && <ForecastPage />}
        {section === 'savings' && <SavingsPage />}
        {section === 'budgets' && <BudgetsPage />}
        {section === 'investments' && <InvestmentsPage />}
        {section === 'imports' && <ImportExportPage />}
        {section === 'scenarios' && <ScenariosPage />}
        {section === 'settings' && <SettingsPage />}
      </main>
    </div>
  </div>
}
