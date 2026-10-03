import { FormEvent, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, Budget, BudgetStatus, Category, money, Settings, Statistics, todayInTimezone } from '../api/client'

type Period = Budget['period']
type Draft = { category_id: string; period: Period; currency: string; amount: string }

export default function BudgetsPage() {
  const queryClient = useQueryClient()
  const [period, setPeriod] = useState<Period>('MONTH')
  const [asOf, setAsOf] = useState('')
  const [draft, setDraft] = useState<Draft | null>(null)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [notice, setNotice] = useState('')
  const { data: settings } = useQuery({ queryKey: ['settings'], queryFn: () => api<Settings>('/settings') })
  const { data: categories = [] } = useQuery({ queryKey: ['categories'], queryFn: () => api<Category[]>('/categories') })
  const day = asOf || todayInTimezone(settings?.timezone)
  const { data: statuses = [] } = useQuery({ queryKey: ['budget-status', day], queryFn: () => api<BudgetStatus[]>(`/budget-status?as_of=${day}`) })
  const { data: statistics, error: statisticsError } = useQuery({
    queryKey: ['statistics', period, day],
    queryFn: () => api<Statistics>(`/statistics?period=${period}&as_of=${day}`),
  })
  const currency = settings?.currency || 'EUR'
  const formatMoney = (value: string | number, unit = currency) => money(value, unit, settings?.locale)
  const categoryName = (id: number | null) => categories.find((item) => item.id === id)?.name || 'Todos los gastos'
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['budgets'] })
    queryClient.invalidateQueries({ queryKey: ['budget-status'] })
  }
  const open = (item?: Budget) => {
    setDraft(item ? {
      category_id: String(item.category_id || ''), period: item.period,
      currency: item.currency, amount: item.amount,
    } : { category_id: '', period, currency, amount: '' })
    setEditingId(item?.id || null)
  }
  const save = useMutation({
    mutationFn: () => api(editingId ? `/budgets/${editingId}` : '/budgets', {
      method: editingId ? 'PATCH' : 'POST',
      body: JSON.stringify({
        category_id: draft!.category_id ? Number(draft!.category_id) : null,
        period: draft!.period, currency: draft!.currency.toUpperCase(),
        amount: draft!.amount.replace(',', '.'),
      }),
    }),
    onSuccess: () => { refresh(); setDraft(null); setNotice('Presupuesto guardado.') },
    onError: (error: Error) => setNotice(error.message),
  })
  const toggle = useMutation({
    mutationFn: (item: Budget) => api(`/budgets/${item.id}`, {
      method: 'PATCH', body: JSON.stringify({ active: !item.active }),
    }),
    onSuccess: refresh,
    onError: (error: Error) => setNotice(error.message),
  })
  const submit = (event: FormEvent) => { event.preventDefault(); save.mutate() }
  const chart = statistics?.expenses_by_category.filter((item) => item.currency === currency)
    .map((item) => ({ name: item.name, amount: Number(item.amount) })) || []
  const visible = statuses.filter((item) => item.period === period)
  return <>
    <div className="page-heading"><div><span className="eyebrow">CONTROL DE GASTOS</span><h2>Presupuestos y estadísticas</h2></div><button className="button primary" onClick={() => open()}>+ Presupuesto</button></div>
    {notice && <div className="notice" role="status">{notice}</div>}
    <section className="panel"><div className="inline-form"><label>Periodo<select value={period} onChange={(event) => setPeriod(event.target.value as Period)}><option value="MONTH">Mes natural</option><option value="SALARY_CYCLE">Ciclo de nómina</option></select></label><label>Fecha de referencia<input type="date" value={day} onChange={(event) => setAsOf(event.target.value)} /></label></div></section>
    {draft && <section className="panel form-panel"><div className="panel-header"><h3>{editingId ? 'Editar presupuesto' : 'Nuevo presupuesto'}</h3><button className="icon-button" onClick={() => setDraft(null)}>×</button></div><form className="form-grid" onSubmit={submit}>
      <label>Categoría<select value={draft.category_id} onChange={(event) => setDraft({ ...draft, category_id: event.target.value })}><option value="">Todos los gastos</option>{categories.map((item) => <option key={item.id} value={item.id}>{item.parent_id ? '↳ ' : ''}{item.name}</option>)}</select></label>
      <label>Periodo<select value={draft.period} onChange={(event) => setDraft({ ...draft, period: event.target.value as Period })}><option value="MONTH">Mes natural</option><option value="SALARY_CYCLE">Ciclo de nómina</option></select></label>
      <label>Moneda<input required maxLength={3} value={draft.currency} onChange={(event) => setDraft({ ...draft, currency: event.target.value.toUpperCase() })} /></label>
      <label>Límite<input required inputMode="decimal" pattern="[0-9]+([.,][0-9]{1,2})?" value={draft.amount} onChange={(event) => setDraft({ ...draft, amount: event.target.value })} /></label>
      <div className="form-actions form-full"><button className="button secondary" type="button" onClick={() => setDraft(null)}>Cancelar</button><button className="button primary" disabled={save.isPending}>Guardar</button></div>
    </form></section>}
    <section className="panel"><div className="panel-header"><div><span className="eyebrow">LÍMITES</span><h3>{period === 'MONTH' ? 'Presupuestos mensuales' : 'Presupuestos del ciclo'}</h3></div></div>
      {visible.length ? <div className="table-scroll"><table><thead><tr><th>Categoría</th><th>Periodo</th><th className="right">Límite</th><th className="right">Gastado</th><th className="right">Restante</th><th></th></tr></thead><tbody>{visible.map((item) => <tr key={item.id}><td><strong>{categoryName(item.category_id)}</strong>{!item.active && <small className="table-note">Pausado</small>}</td><td>{item.start && item.end ? `${item.start} a ${item.end}` : 'Configura un ingreso principal'}</td><td className="right">{formatMoney(item.amount, item.currency)}</td><td className="right">{item.spent === null ? '—' : formatMoney(item.spent, item.currency)}</td><td className={`right amount ${Number(item.remaining) < 0 ? 'error' : ''}`}>{item.remaining === null ? '—' : formatMoney(item.remaining, item.currency)}</td><td className="row-actions"><button onClick={() => open(item)}>Editar</button><button onClick={() => toggle.mutate(item)}>{item.active ? 'Pausar' : 'Activar'}</button></td></tr>)}</tbody></table></div> : <div className="empty">No hay presupuestos para este tipo de periodo.</div>}
    </section>
    {statisticsError ? <div className="notice">Configura una fuente de ingreso principal para consultar estadísticas por ciclo de nómina.</div> : statistics && <>
      <div className="metric-grid"><div className="metric-card featured"><div className="metric-icon">↓</div><span>Ingresos confirmados · {currency}</span><strong>{formatMoney(statistics.income_by_currency[currency] || '0')}</strong><small>{statistics.start} a {statistics.end}</small></div><div className="metric-card"><div className="metric-icon amber">↑</div><span>Gastos confirmados · {currency}</span><strong>{formatMoney(statistics.expense_by_currency[currency] || '0')}</strong><small>Transferencias excluidas</small></div></div>
      <section className="panel"><div className="panel-header"><div><span className="eyebrow">DESGLOSE</span><h3>Gastos por categoría en {currency}</h3></div></div>{chart.length ? <div style={{ height: 300 }}><ResponsiveContainer width="100%" height="100%"><BarChart data={chart} layout="vertical" margin={{ left: 25, right: 20 }}><CartesianGrid stroke="#e5eee9" /><XAxis type="number" /><YAxis dataKey="name" type="category" width={130} /><Tooltip formatter={(value) => formatMoney(String(value))} /><Bar dataKey="amount" fill="#2d7f71" name="Gasto" /></BarChart></ResponsiveContainer></div> : <div className="empty">Sin gastos confirmados en esta moneda.</div>}</section>
      {Object.keys(statistics.expense_by_currency).some((unit) => unit !== currency) && <div className="notice">También hay gastos en otras monedas: {Object.entries(statistics.expense_by_currency).filter(([unit]) => unit !== currency).map(([unit, value]) => formatMoney(value, unit)).join(' · ')}. No se mezclan con {currency}.</div>}
    </>}
    <p className="table-note">Los presupuestos de una categoría padre incluyen sus subcategorías. Los movimientos pendientes no cuentan como gasto realizado.</p>
  </>
}
