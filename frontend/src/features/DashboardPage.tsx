import { useQuery } from '@tanstack/react-query'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { AccountType, api, Dashboard, Forecast, money, Settings } from '../api/client'
import './DashboardPage.css'

const colors = ['#2d7f71', '#9dc7ad', '#e4b370', '#789aa8', '#c78071', '#9a8bc1']
const labels: Record<string, string> = { INCOME: 'Ingreso', EXPENSE: 'Gasto', TRANSFER: 'Transferencia', ADJUSTMENT: 'Ajuste' }
const accountTypes: Record<AccountType, string> = {
  CHECKING: 'Corriente', SAVINGS: 'Ahorros', CASH: 'Efectivo',
  INVESTMENT: 'Inversión', CARD: 'Tarjeta', OTHER: 'Otras',
}

const nextMonthEnd = (start: string) => {
  const [year, month] = start.split('-').map(Number)
  return new Date(Date.UTC(year, month + 1, 0)).toISOString().slice(0, 10)
}

export default function DashboardPage({ onNavigate }: { onNavigate: (section: 'dashboard' | 'transactions' | 'accounts' | 'planning' | 'forecast' | 'savings' | 'budgets' | 'investments' | 'imports' | 'settings') => void }) {
  const { data, isLoading, error } = useQuery({ queryKey: ['dashboard'], queryFn: () => api<Dashboard>('/dashboard') })
  const { data: forecast, isLoading: forecastLoading, error: forecastError } = useQuery({ queryKey: ['forecast'], queryFn: () => api<Forecast>('/forecast') })
  const { data: settings } = useQuery({ queryKey: ['settings'], queryFn: () => api<Settings>('/settings') })
  const formatMoney = (value: string | number, currency = 'EUR') => money(value, currency, settings?.locale)
  if (isLoading) return <div className="panel">Cargando resumen...</div>
  if (error || !data) return <div className="alert error">No se pudo cargar el resumen.</div>
  const primary = data.balances.find((entry) => entry.currency === (settings?.currency || 'EUR')) || data.balances[0]
  const currency = primary?.currency || settings?.currency || 'EUR'
  const balancesByType = data.accounts.filter((account) => account.currency === currency).reduce((totals, account) => {
    totals.set(account.type, (totals.get(account.type) || 0) + Math.round(Number(account.balance) * 100))
    return totals
  }, new Map<AccountType, number>())
  const monthEnd = forecast ? nextMonthEnd(forecast.start) : null
  const nextMonth = monthEnd ? forecast?.days.find((day) => day.date === monthEnd) : null
  const monthLabel = monthEnd ? new Intl.DateTimeFormat(settings?.locale || 'es-ES', { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${monthEnd}T12:00:00Z`)) : 'mes siguiente'
  const predictedAvailable = forecast?.salary_cycle.available ? forecast.minimum_until_payday_by_currency?.[currency] : null
  const spending = data.spending_by_category.filter((item) => item.currency === currency).map((item) => ({ ...item, value: Number(item.amount) }))
  return <>
    <div className="page-heading"><div><span className="eyebrow">VISTA GENERAL</span><h2>Tu panorama financiero</h2></div><button className="button primary" onClick={() => onNavigate('transactions')}>+ Nuevo movimiento</button></div>
    <div className="metric-grid">
      <div className="metric-card featured"><div className="metric-icon">◈</div><span>Disponible · {currency}</span><strong>{predictedAvailable != null ? formatMoney(predictedAvailable, currency) : '—'}</strong><small>{forecastLoading ? 'Calculando previsión...' : forecastError ? 'No se pudo calcular la previsión' : forecast?.salary_cycle.available ? 'Mínimo previsto hasta el próximo cobro' : 'Configura un ingreso principal para ver la previsión'}</small><div className="dashboard-current-available">Disponible hoy: <b>{formatMoney(primary?.available || '0', currency)}</b></div></div>
      <div className="metric-card dashboard-balance-card"><div className="metric-icon pale">▣</div><span>Saldo actual · {currency}</span><strong>{formatMoney(primary?.total || '0', currency)}</strong><div className="dashboard-balance-types">{[...balancesByType].map(([type, cents]) => <div key={type}><span>{accountTypes[type]}</span><b>{formatMoney(cents / 100, currency)}</b></div>)}{!balancesByType.size && <small>Sin cuentas en esta moneda</small>}</div></div>
      <div className="metric-card"><div className="metric-icon amber">◇</div><span>Previsión · {monthLabel}</span><strong>{nextMonth ? formatMoney(nextMonth.totals_by_currency[currency] || '0', currency) : '—'}</strong><small>{nextMonth ? `Saldo previsto al ${monthEnd?.split('-').reverse().join('/')}` : forecastLoading ? 'Calculando previsión...' : forecastError ? 'No se pudo calcular la previsión' : 'Previsión no disponible'}</small></div>
    </div>
    <div className="dashboard-grid">
      <section className="panel"><div className="panel-header"><div><span className="eyebrow">ESTE MES</span><h3>Gastos por categoría</h3></div></div>
        {spending.length ? <div className="chart-area"><div className="chart"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={spending} dataKey="value" nameKey="name" innerRadius={74} outerRadius={105} paddingAngle={3} isAnimationActive={false}>{spending.map((_, index) => <Cell key={index} fill={colors[index % colors.length]} />)}</Pie><Tooltip formatter={(value) => formatMoney(String(value), currency)} /></PieChart></ResponsiveContainer></div><div className="legend">{spending.map((item, index) => <div key={item.name}><i style={{ background: colors[index % colors.length] }} /> <span>{item.name}</span><strong>{formatMoney(item.amount, currency)}</strong></div>)}</div></div> : <div className="empty">Aún no hay gastos registrados este mes.</div>}
      </section>
      <section className="panel"><div className="panel-header"><div><span className="eyebrow">ACTIVIDAD</span><h3>Últimos movimientos</h3></div><button className="text-button" onClick={() => onNavigate('transactions')}>Ver todos →</button></div>
        {data.recent_transactions.length ? <div className="activity-list">{data.recent_transactions.map((item) => <div className="activity" key={item.id}><div className={`activity-icon ${item.type.toLowerCase()}`}>{item.type === 'INCOME' ? '↓' : item.type === 'EXPENSE' ? '↑' : '⇄'}</div><div><strong>{item.concept}</strong><small>{labels[item.type]} · {item.date.split('-').reverse().join('/')}</small></div><b className={item.type === 'INCOME' ? 'positive' : ''}>{item.type === 'EXPENSE' ? '−' : item.type === 'INCOME' ? '+' : ''}{formatMoney(item.amount, item.currency)}</b></div>)}</div> : <div className="empty">Tu actividad aparecerá aquí cuando registres un movimiento.</div>}
      </section>
    </div>
    <section className="panel"><div className="panel-header"><div><span className="eyebrow">TUS CUENTAS</span><h3>Dinero por cuenta</h3></div><button className="text-button" onClick={() => onNavigate('accounts')}>Gestionar cuentas →</button></div>
      {data.accounts.length ? <div className="account-summary">{data.accounts.map((item) => <div key={item.id}><span>{item.name}<small>{item.type}</small></span><strong>{formatMoney(item.balance, item.currency)}</strong></div>)}</div> : <div className="empty">Añade tu primera cuenta para empezar.</div>}
    </section>
  </>
}
