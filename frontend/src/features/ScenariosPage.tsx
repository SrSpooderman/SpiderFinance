import { FormEvent, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, Forecast, money, Scenario, ScenarioDraft, Settings, Simulation, todayInTimezone } from '../api/client'

const emptyDraft = (): ScenarioDraft => ({ name: '', notes: null, overrides: [], events: [], savings_percent: null })

export default function ScenariosPage() {
  const queryClient = useQueryClient()
  const [days, setDays] = useState(90)
  const [currency, setCurrency] = useState('')
  const [chartMode, setChartMode] = useState<'balance' | 'available'>('balance')
  const [targetAmount, setTargetAmount] = useState('')
  const [editingId, setEditingId] = useState<number | null>(null)
  const [draft, setDraft] = useState<ScenarioDraft>(emptyDraft)
  const [extra, setExtra] = useState({ date: '', account_id: '', amount: '', label: '' })
  const [override, setOverride] = useState({ key: '', amount: '' })
  const [result, setResult] = useState<Simulation | null>(null)
  const [notice, setNotice] = useState('')
  const { data: settings } = useQuery({ queryKey: ['settings'], queryFn: () => api<Settings>('/settings') })
  const { data: base } = useQuery({ queryKey: ['forecast', days], queryFn: () => api<Forecast>(`/forecast?days=${days}`) })
  const { data: saved = [] } = useQuery({ queryKey: ['scenarios'], queryFn: () => api<Scenario[]>('/scenarios') })
  const update = (next: ScenarioDraft) => { setDraft(next); setResult(null) }
  const load = (item: Scenario) => {
    setEditingId(item.id)
    update({ name: item.name, notes: item.notes, overrides: item.overrides, events: item.events, savings_percent: item.savings_percent })
    setNotice('')
  }
  const save = useMutation({
    mutationFn: () => api<Scenario>(editingId ? `/scenarios/${editingId}` : '/scenarios', {
      method: editingId ? 'PATCH' : 'POST', body: JSON.stringify(draft),
    }),
    onSuccess: (item) => { setEditingId(item.id); queryClient.invalidateQueries({ queryKey: ['scenarios'] }); setNotice('Escenario guardado.') },
    onError: (error: Error) => setNotice(error.message),
  })
  const compare = useMutation({
    mutationFn: () => api<Simulation>(`/scenarios/simulate?days=${days}`, { method: 'POST', body: JSON.stringify(draft) }),
    onSuccess: (data) => { setResult(data); setNotice('') },
    onError: (error: Error) => { setResult(null); setNotice(error.message) },
  })
  const remove = useMutation({
    mutationFn: (id: number) => api(`/scenarios/${id}`, { method: 'DELETE' }),
    onSuccess: (_, removedId) => { if (editingId === removedId) { setEditingId(null); update(emptyDraft()) }; queryClient.invalidateQueries({ queryKey: ['scenarios'] }); setNotice('Escenario eliminado.') },
    onError: (error: Error) => setNotice(error.message),
  })
  const addExtra = (event: FormEvent) => {
    event.preventDefault()
    update({ ...draft, events: [...draft.events, {
      date: extra.date, account_id: Number(extra.account_id), amount: extra.amount.replace(',', '.'), label: extra.label.trim(),
    }] })
    setExtra({ date: '', account_id: '', amount: '', label: '' })
  }
  const addOverride = (event: FormEvent) => {
    event.preventDefault()
    if (draft.overrides.some((item) => item.key === override.key)) { setNotice('Ese suceso ya está modificado.'); return }
    update({ ...draft, overrides: [...draft.overrides, { key: override.key, amount: override.amount.replace(',', '.') }] })
    setOverride({ key: '', amount: '' })
    setNotice('')
  }
  const units = [...new Set(base?.accounts.map((item) => item.currency) || [])]
  const selectedCurrency = units.includes(currency) ? currency : units.includes(settings?.currency || '') ? settings!.currency : units[0] || 'EUR'
  const formatMoney = (value: string | number, unit = selectedCurrency) => money(value, unit, settings?.locale)
  const accountName = (id: number) => base?.accounts.find((item) => item.id === id)?.name || `Cuenta ${id}`
  const eventName = (key: string) => base?.events.find((item) => item.key === key)?.label || `${key} (fuera del horizonte)`
  const chart = result?.days.map((item) => ({
    date: item.date.slice(5),
    base: Number((chartMode === 'available' ? item.baseline_available_by_currency : item.baseline_by_currency)[selectedCurrency] || '0'),
    scenario: Number((chartMode === 'available' ? item.scenario_available_by_currency : item.scenario_by_currency)[selectedCurrency] || '0'),
  })) || []
  const reached = result && Number(targetAmount.replace(',', '.')) > 0
    ? result.days.find((item) => Number((chartMode === 'available' ? item.scenario_available_by_currency : item.scenario_by_currency)[selectedCurrency] || '0') >= Number(targetAmount.replace(',', '.')))?.date
    : null
  return <>
    <div className="page-heading"><div><span className="eyebrow">QUÉ PASARÍA SI...</span><h2>Simulador</h2></div></div>
    {notice && <div className="notice" role="status">{notice}</div>}
    <section className="panel"><div className="inline-form"><label>Horizonte<select value={days} onChange={(event) => { setDays(Number(event.target.value)); setResult(null) }}><option value={30}>30 días</option><option value={90}>90 días</option><option value={180}>180 días</option><option value={365}>365 días</option></select></label>{units.length > 1 && <label>Moneda<select value={selectedCurrency} onChange={(event) => setCurrency(event.target.value)}>{units.map((unit) => <option key={unit}>{unit}</option>)}</select></label>}</div></section>
    <section className="panel"><div className="panel-header"><div><span className="eyebrow">MIS ESCENARIOS</span><h3>Guardados</h3></div><button className="button secondary" onClick={() => { setEditingId(null); update(emptyDraft()); setNotice('') }}>Nuevo escenario</button></div>
      {saved.length ? <div className="table-scroll"><table><thead><tr><th>Nombre</th><th>Cambios</th><th></th></tr></thead><tbody>{saved.map((item) => <tr key={item.id}><td>{item.name}</td><td>{item.events.length} sucesos · {item.overrides.length} ajustes</td><td className="row-actions"><button onClick={() => load(item)}>Abrir</button><button onClick={() => { if (window.confirm(`¿Eliminar el escenario «${item.name}»?`)) remove.mutate(item.id) }}>Eliminar</button></td></tr>)}</tbody></table></div> : <div className="empty">Aún no hay escenarios guardados. Puedes simular sin guardar.</div>}
    </section>
    <section className="panel form-panel"><div className="panel-header"><div><span className="eyebrow">HIPÓTESIS</span><h3>{editingId ? `Editando escenario ${editingId}` : 'Nuevo escenario'}</h3></div></div>
      <div className="form-grid"><label>Nombre<input required maxLength={120} value={draft.name} onChange={(event) => update({ ...draft, name: event.target.value })} placeholder="Compra de diciembre" /></label><label>Notas<input maxLength={500} value={draft.notes || ''} onChange={(event) => update({ ...draft, notes: event.target.value || null })} /></label></div>
      <h3>Suceso hipotético</h3><p className="hint">Usa un importe negativo para un gasto y positivo para un ingreso. La fecha debe estar dentro del horizonte para afectar el resultado.</p>
      <form className="form-grid" onSubmit={addExtra}><label>Fecha<input required type="date" min={todayInTimezone(settings?.timezone)} value={extra.date} onChange={(event) => setExtra({ ...extra, date: event.target.value })} /></label><label>Cuenta<select required value={extra.account_id} onChange={(event) => setExtra({ ...extra, account_id: event.target.value })}><option value="">Selecciona una cuenta</option>{base?.accounts.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.currency}</option>)}</select></label><label>Importe con signo<input required inputMode="decimal" pattern="-?[0-9]+([.,][0-9]{1,2})?" value={extra.amount} onChange={(event) => setExtra({ ...extra, amount: event.target.value })} placeholder="-200,00" /></label><label>Concepto<input required maxLength={120} value={extra.label} onChange={(event) => setExtra({ ...extra, label: event.target.value })} /></label><div className="form-actions form-full"><button className="button secondary">Añadir suceso</button></div></form>
      {draft.events.length > 0 && <div className="table-scroll"><table><thead><tr><th>Fecha</th><th>Concepto</th><th>Cuenta</th><th className="right">Efecto</th><th></th></tr></thead><tbody>{draft.events.map((item, index) => <tr key={`${index}-${item.date}`}><td>{item.date}</td><td>{item.label}</td><td>{accountName(item.account_id)}</td><td className="right">{formatMoney(item.amount, base?.accounts.find((account) => account.id === item.account_id)?.currency)}</td><td className="row-actions"><button onClick={() => update({ ...draft, events: draft.events.filter((_, position) => position !== index) })}>Quitar</button></td></tr>)}</tbody></table></div>}
      <h3>Modificar un suceso previsto</h3><p className="hint">El importe con signo reemplaza el importe previsto. Introduce 0 para cancelar ese suceso en la simulación.</p>
      <form className="form-grid" onSubmit={addOverride}><label>Suceso<select required value={override.key} onChange={(event) => setOverride({ ...override, key: event.target.value })}><option value="">Selecciona un suceso</option>{base?.events.map((item) => <option key={item.key} value={item.key}>{item.date} · {item.label} · {formatMoney(item.amount, base.accounts.find((account) => account.id === item.account_id)?.currency)}</option>)}</select></label><label>Nuevo importe con signo<input required inputMode="decimal" pattern="-?[0-9]+([.,][0-9]{1,2})?" value={override.amount} onChange={(event) => setOverride({ ...override, amount: event.target.value })} placeholder="0" /></label><div className="form-actions form-full"><button className="button secondary">Añadir ajuste</button></div></form>
      {draft.overrides.length > 0 && <div className="table-scroll"><table><thead><tr><th>Suceso</th><th className="right">Nuevo efecto</th><th></th></tr></thead><tbody>{draft.overrides.map((item) => <tr key={item.key}><td>{eventName(item.key)}</td><td className="right">{item.amount}</td><td className="row-actions"><button onClick={() => update({ ...draft, overrides: draft.overrides.filter((entry) => entry.key !== item.key) })}>Quitar</button></td></tr>)}</tbody></table></div>}
      <h3>Ahorro hipotético</h3><p className="hint">Reserva virtualmente un porcentaje de cada ingreso planificado en este horizonte. Reduce el dinero disponible, pero no el saldo bancario ni crea aportaciones.</p>
      <div className="form-grid"><label>Porcentaje de ingresos previstos<input type="number" min="0" max="100" step="0.01" value={draft.savings_percent ?? ''} onChange={(event) => update({ ...draft, savings_percent: event.target.value || null })} placeholder="40" /></label></div>
      <div className="form-actions"><button className="button secondary" disabled={!draft.name.trim() || save.isPending} onClick={() => save.mutate()}>Guardar</button><button className="button primary" disabled={!draft.name.trim() || compare.isPending} onClick={() => compare.mutate()}>Comparar con previsión base</button></div>
    </section>
    {result && <>
      {(result.ignored_events > 0 || result.ignored_overrides.length > 0) && <div className="notice">{result.ignored_events} sucesos adicionales y {result.ignored_overrides.length} ajustes quedan fuera de este horizonte o ya no existen en la previsión.</div>}
      <div className="metric-grid"><div className="metric-card featured"><span>Saldo base · {selectedCurrency}</span><strong>{formatMoney(result.days[result.days.length - 1]?.baseline_by_currency[selectedCurrency] || '0')}</strong><small>Al {result.end}</small></div><div className="metric-card"><span>Saldo simulado · {selectedCurrency}</span><strong>{formatMoney(result.days[result.days.length - 1]?.scenario_by_currency[selectedCurrency] || '0')}</strong><small>Mínimo: {formatMoney(result.minimum_scenario_by_currency[selectedCurrency] || '0')}</small></div><div className="metric-card"><span>Diferencia · {selectedCurrency}</span><strong>{formatMoney(result.final_difference_by_currency[selectedCurrency] || '0')}</strong><small>Respecto a la previsión base</small></div></div>
      {draft.savings_percent !== null && <div className="metric-grid"><div className="metric-card"><span>Reserva hipotética · {selectedCurrency}</span><strong>{formatMoney(result.simulated_savings_by_currency[selectedCurrency] || '0')}</strong><small>Por ingresos planificados</small></div><div className="metric-card"><span>Disponible simulado · {selectedCurrency}</span><strong>{formatMoney(result.days[result.days.length - 1]?.scenario_available_by_currency[selectedCurrency] || '0')}</strong><small>Mínimo: {formatMoney(result.minimum_scenario_available_by_currency[selectedCurrency] || '0')}</small></div></div>}
      <section className="panel"><div className="panel-header"><div><span className="eyebrow">COMPARACIÓN</span><h3>Evolución en {selectedCurrency}</h3></div></div><div className="inline-form"><label>Mostrar<select value={chartMode} onChange={(event) => setChartMode(event.target.value as 'balance' | 'available')}><option value="balance">Saldo bancario</option><option value="available">Disponible tras reservas</option></select></label><label>Objetivo de {chartMode === 'available' ? 'disponible' : 'saldo'}<input inputMode="decimal" value={targetAmount} onChange={(event) => setTargetAmount(event.target.value)} placeholder="3000" /></label></div>{Number(targetAmount.replace(',', '.')) > 0 && <p className="notice">{reached ? `El escenario alcanza ${formatMoney(targetAmount.replace(',', '.'))} el ${reached}.` : `El escenario no alcanza ${formatMoney(targetAmount.replace(',', '.'))} en este horizonte.`}</p>}<div style={{ height: 300, width: '100%' }}><ResponsiveContainer width="100%" height="100%"><LineChart data={chart}><CartesianGrid stroke="var(--line)" /><XAxis dataKey="date" minTickGap={25} /><YAxis width={70} /><Tooltip formatter={(value) => formatMoney(String(value))} /><Legend /><Line type="stepAfter" dataKey="base" name="Base" stroke="var(--muted)" strokeWidth={2} dot={false} /><Line type="stepAfter" dataKey="scenario" name="Escenario" stroke="var(--chart-1)" strokeWidth={3} dot={false} /></LineChart></ResponsiveContainer></div></section>
      {units.length > 1 && <section className="panel"><div className="panel-header"><h3>Diferencia final por moneda</h3></div><div className="table-scroll"><table><thead><tr><th>Moneda</th><th className="right">Diferencia</th></tr></thead><tbody>{units.map((unit) => <tr key={unit}><td>{unit}</td><td className="right">{formatMoney(result.final_difference_by_currency[unit] || '0', unit)}</td></tr>)}</tbody></table></div></section>}
    </>}
  </>
}
