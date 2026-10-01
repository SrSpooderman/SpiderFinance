import { useQuery } from '@tanstack/react-query'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { api, Dashboard, Forecast, money, Settings } from '../api/client'

const colors = ['#2d7f71', '#9dc7ad', '#e4b370', '#789aa8', '#c78071', '#9a8bc1']
const labels: Record<string, string> = { INCOME: 'Ingreso', EXPENSE: 'Gasto', TRANSFER: 'Transferencia', ADJUSTMENT: 'Ajuste' }

export default function DashboardPage({ onNavigate }: { onNavigate: (section: 'dashboard' | 'transactions' | 'accounts' | 'planning' | 'forecast' | 'savings' | 'budgets' | 'investments' | 'imports' | 'settings') => void }) {
  const { data, isLoading, error } = useQuery({ queryKey: ['dashboard'], queryFn: () => api<Dashboard>('/dashboard') })
  const { data: forecast } = useQuery({ queryKey: ['forecast'], queryFn: () => api<Forecast>('/forecast') })
  const { data: settings } = useQuery({ queryKey: ['settings'], queryFn: () => api<Settings>('/settings') })
  const formatMoney = (value: string | number, currency = 'EUR') => money(value, currency, settings?.locale)
  if (isLoading) return <div className="panel">Cargando resumen...</div>
  if (error || !data) return <div className="alert error">No se pudo cargar el resumen.</div>
  const primary = data.balances.find((entry) => entry.currency === (settings?.currency || 'EUR')) || data.balances[0]
  const currency = primary?.currency || settings?.currency || 'EUR'
  const spending = data.spending_by_category.filter((item) => item.currency === currency).map((item) => ({ ...item, value: Number(item.amount) }))
  return <>
    <div className="page-heading"><div><span className="eyebrow">VISTA GENERAL</span><h2>Tu panorama financiero</h2><p>Dinero registrado en tus cuentas y actividad real de este mes.</p></div><button className="button primary" onClick={() => onNavigate('transactions')}>+ Nuevo movimiento</button></div>
    <div className="metric-grid">
      <div className="metric-card featured"><div className="metric-icon">◈</div><span>Saldo total · {currency}</span><strong>{formatMoney(primary?.total || '0', currency)}</strong><small>Entre tus cuentas activas</small></div>
      <div className="metric-card"><div className="metric-icon pale">▣</div><span>En ahorro</span><strong>{formatMoney(primary?.savings || '0', currency)}</strong><small>Cuentas de ahorro activas</small></div>
      <div className="metric-card"><div className="metric-icon amber">⇄</div><span>Movimientos recientes</span><strong>{data.recent_transactions.length}</strong><small>Últimos registros</small></div>
    </div>
    {forecast?.salary_cycle.available && <section className="panel"><div className="panel-header"><div><span className="eyebrow">HASTA LA PRÓXIMA NÓMINA</span><h3>Disponibilidad prevista</h3></div><button className="text-button" onClick={() => onNavigate('forecast')}>Ver previsión →</button></div><p>Próximo cobro: {forecast.salary_cycle.next_payday}. Mínimo previsto en {currency}: <strong>{formatMoney(forecast.minimum_until_payday_by_currency?.[currency] || '0', currency)}</strong>.</p></section>}
    {data.balances.length > 1 && <div className="notice">También tienes saldos en otras monedas: {data.balances.filter((item) => item.currency !== currency).map((item) => formatMoney(item.total, item.currency)).join(' · ')}. No se suman sin un tipo de cambio.</div>}
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
