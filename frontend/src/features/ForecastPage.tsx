import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, Forecast, money, Settings } from '../api/client'

export default function ForecastPage() {
  const [days, setDays] = useState(90)
  const { data: settings } = useQuery({ queryKey: ['settings'], queryFn: () => api<Settings>('/settings') })
  const { data, isLoading, error } = useQuery({ queryKey: ['forecast', days], queryFn: () => api<Forecast>(`/forecast?days=${days}`) })
  if (isLoading) return <div className="panel">Calculando previsión...</div>
  if (error || !data) return <div className="alert error">No se pudo calcular la previsión.</div>
  const currency = settings?.currency || data.accounts[0]?.currency || 'EUR'
  const chart = data.days.map((item) => ({ date: item.date.slice(5), value: Number(item.totals_by_currency[currency] || '0') }))
  const formatMoney = (value: string | number, unit = currency) => money(value, unit, settings?.locale)
  const accountName = (id: number) => data.accounts.find((item) => item.id === id)?.name || '—'
  const currencies = [...new Set(data.accounts.map((item) => item.currency))]
  return <>
    <div className="page-heading"><div><span className="eyebrow">ESCENARIO BASE</span><h2>Previsión de saldos</h2><p>Movimientos pendientes y obligaciones previstas sobre tus saldos actuales. La consulta no crea movimientos.</p></div><label>Horizonte<select value={days} onChange={(event) => setDays(Number(event.target.value))}><option value={30}>30 días</option><option value={90}>90 días</option><option value={180}>180 días</option><option value={365}>365 días</option></select></label></div>
    <div className="metric-grid">
      <div className="metric-card featured"><div className="metric-icon">◷</div><span>Saldo previsto · {currency}</span><strong>{formatMoney(data.days[data.days.length - 1]?.totals_by_currency[currency] || '0')}</strong><small>Al {data.end}</small></div>
      <div className="metric-card"><div className="metric-icon pale">▣</div><span>Hasta la próxima nómina</span><strong>{data.minimum_until_payday_by_currency ? formatMoney(data.minimum_until_payday_by_currency[currency] || '0') : 'Sin ciclo disponible'}</strong><small>{data.salary_cycle.next_payday ? `Próximo cobro: ${data.salary_cycle.next_payday}` : 'Configura un ingreso principal'}</small></div>
      <div className="metric-card"><div className="metric-icon amber">⇄</div><span>Sucesos previstos</span><strong>{data.events.length}</strong><small>En este horizonte</small></div>
    </div>
    {currencies.length > 1 && <div className="notice">La gráfica muestra {currency}. Los saldos de otras monedas no se suman sin conversión.</div>}
    <section className="panel"><div className="panel-header"><div><span className="eyebrow">EVOLUCIÓN</span><h3>Saldo total en {currency}</h3></div></div>
      <div style={{ height: 280, width: '100%' }}><ResponsiveContainer width="100%" height="100%"><LineChart data={chart}><CartesianGrid stroke="#e5eee9" /><XAxis dataKey="date" minTickGap={25} /><YAxis tickFormatter={(value) => String(value)} width={70} /><Tooltip formatter={(value) => formatMoney(String(value))} /><Line type="stepAfter" dataKey="value" stroke="#2d7f71" strokeWidth={3} dot={false} name="Saldo" /></LineChart></ResponsiveContainer></div>
    </section>
    {data.salary_cycle.available && <div className="notice">Ciclo de nómina actual: {data.salary_cycle.current_start} a {data.salary_cycle.current_end}. El siguiente cobro inicia un nuevo ciclo.</div>}
    <section className="panel"><div className="panel-header"><div><span className="eyebrow">CUENTAS</span><h3>Del saldo actual al previsto</h3></div></div>
      {data.accounts.length ? <div className="table-scroll"><table><thead><tr><th>Cuenta</th><th>Moneda</th><th className="right">Actual</th><th className="right">Al final del horizonte</th></tr></thead><tbody>{data.accounts.map((item) => <tr key={item.id}><td>{item.name}</td><td>{item.currency}</td><td className="right">{formatMoney(item.current, item.currency)}</td><td className="right amount">{formatMoney(item.projected, item.currency)}</td></tr>)}</tbody></table></div> : <div className="empty">Añade una cuenta para ver su previsión.</div>}
    </section>
    <section className="panel"><div className="panel-header"><div><span className="eyebrow">CALENDARIO</span><h3>Sucesos previstos</h3></div></div>
      {data.events.length ? <div className="table-scroll"><table><thead><tr><th>Fecha</th><th>Concepto</th><th>Cuenta</th><th className="right">Efecto</th></tr></thead><tbody>{data.events.map((item) => {
        const unit = data.accounts.find((account) => account.id === item.account_id)?.currency || currency
        return <tr key={item.key}><td>{item.date}</td><td>{item.label}</td><td>{accountName(item.account_id)}</td><td className={`right amount ${Number(item.amount) > 0 ? 'positive' : ''}`}>{Number(item.amount) > 0 ? '+' : ''}{formatMoney(item.amount, unit)}</td></tr>
      })}</tbody></table></div> : <div className="empty">No hay sucesos previstos en este horizonte.</div>}
    </section>
  </>
}
