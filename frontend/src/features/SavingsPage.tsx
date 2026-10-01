import { FormEvent, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Account, api, GoalContribution, IncomeSource, money, Reservation,
  SavingsGoal, SavingsRecommendation, SavingsRule, Settings, todayInTimezone,
} from '../api/client'

type GoalDraft = { name: string; target_amount: string; currency: string; priority: string; due_date: string }
type RuleDraft = { name: string; income_source_id: string; mode: 'PERCENT' | 'FIXED'; value: string }
const decimal = (value: string) => value.replace(',', '.')

export default function SavingsPage() {
  const queryClient = useQueryClient()
  const [notice, setNotice] = useState('')
  const [goalDraft, setGoalDraft] = useState<GoalDraft | null>(null)
  const [editingGoal, setEditingGoal] = useState<number | null>(null)
  const [ruleDraft, setRuleDraft] = useState<RuleDraft | null>(null)
  const [editingRule, setEditingRule] = useState<number | null>(null)
  const [savingGoal, setSavingGoal] = useState<number | null | undefined>(undefined)
  const [savingAccount, setSavingAccount] = useState('')
  const [savingAmount, setSavingAmount] = useState('')
  const [releaseId, setReleaseId] = useState<number | null>(null)
  const [releaseAmount, setReleaseAmount] = useState('')
  const { data: settings } = useQuery({ queryKey: ['settings'], queryFn: () => api<Settings>('/settings') })
  const { data: accounts = [] } = useQuery({ queryKey: ['accounts'], queryFn: () => api<Account[]>('/accounts') })
  const { data: sources = [] } = useQuery({ queryKey: ['planning', 'income'], queryFn: () => api<IncomeSource[]>('/income-sources') })
  const { data: goals = [] } = useQuery({ queryKey: ['savings', 'goals'], queryFn: () => api<SavingsGoal[]>('/goals') })
  const { data: reservations = [] } = useQuery({ queryKey: ['savings', 'reservations'], queryFn: () => api<Reservation[]>('/reservations') })
  const { data: rules = [] } = useQuery({ queryKey: ['savings', 'rules'], queryFn: () => api<SavingsRule[]>('/savings-rules') })
  const { data: contributions = [] } = useQuery({ queryKey: ['savings', 'contributions'], queryFn: () => api<GoalContribution[]>('/goal-contributions') })
  const { data: recommendation } = useQuery({ queryKey: ['savings', 'recommendation'], queryFn: () => api<SavingsRecommendation>('/savings-recommendations') })
  const today = todayInTimezone(settings?.timezone)
  const formatMoney = (value: string | number, currency = settings?.currency || 'EUR') => money(value, currency, settings?.locale)
  const account = (id: number) => accounts.find((item) => item.id === id)
  const goal = (id: number | null) => goals.find((item) => item.id === id)
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['savings'] })
    queryClient.invalidateQueries({ queryKey: ['forecast'] })
  }
  const openGoal = (item?: SavingsGoal) => {
    setGoalDraft(item ? {
      name: item.name, target_amount: item.target_amount, currency: item.currency,
      priority: String(item.priority), due_date: item.due_date || '',
    } : { name: '', target_amount: '', currency: settings?.currency || 'EUR', priority: '1', due_date: '' })
    setEditingGoal(item?.id || null)
  }
  const openRule = (item?: SavingsRule) => {
    setRuleDraft(item ? {
      name: item.name, income_source_id: String(item.income_source_id), mode: item.mode, value: item.value,
    } : { name: '', income_source_id: '', mode: 'PERCENT', value: '' })
    setEditingRule(item?.id || null)
  }
  const saveGoal = useMutation({
    mutationFn: () => api(editingGoal ? `/goals/${editingGoal}` : '/goals', {
      method: editingGoal ? 'PATCH' : 'POST',
      body: JSON.stringify({
        name: goalDraft!.name.trim(), target_amount: decimal(goalDraft!.target_amount),
        currency: goalDraft!.currency.toUpperCase(), priority: Number(goalDraft!.priority),
        due_date: goalDraft!.due_date || null,
      }),
    }),
    onSuccess: () => { refresh(); setGoalDraft(null); setNotice('Objetivo guardado.') },
    onError: (error: Error) => setNotice(error.message),
  })
  const toggleGoal = useMutation({
    mutationFn: (item: SavingsGoal) => api(`/goals/${item.id}`, {
      method: 'PATCH', body: JSON.stringify({ active: !item.active }),
    }),
    onSuccess: refresh, onError: (error: Error) => setNotice(error.message),
  })
  const saveReservation = useMutation({
    mutationFn: () => api(savingGoal ? `/goals/${savingGoal}/contributions` : '/reservations', {
      method: 'POST', body: JSON.stringify({
        account_id: Number(savingAccount), amount: decimal(savingAmount), date: today,
        ...(!savingGoal ? { goal_id: null } : {}),
      }),
    }),
    onSuccess: () => { refresh(); setSavingGoal(undefined); setSavingAmount(''); setNotice('Dinero reservado. El saldo de la cuenta no ha cambiado.') },
    onError: (error: Error) => setNotice(error.message),
  })
  const release = useMutation({
    mutationFn: () => api(`/reservations/${releaseId}/release`, {
      method: 'POST', body: JSON.stringify({ amount: decimal(releaseAmount), date: today }),
    }),
    onSuccess: () => { refresh(); setReleaseId(null); setReleaseAmount(''); setNotice('Reserva liberada.') },
    onError: (error: Error) => setNotice(error.message),
  })
  const saveRule = useMutation({
    mutationFn: () => api(editingRule ? `/savings-rules/${editingRule}` : '/savings-rules', {
      method: editingRule ? 'PATCH' : 'POST', body: JSON.stringify({
        name: ruleDraft!.name.trim(), income_source_id: Number(ruleDraft!.income_source_id),
        mode: ruleDraft!.mode, value: decimal(ruleDraft!.value),
      }),
    }),
    onSuccess: () => { refresh(); setRuleDraft(null); setEditingRule(null); setNotice('Regla guardada.') },
    onError: (error: Error) => setNotice(error.message),
  })
  const toggleRule = useMutation({
    mutationFn: (item: SavingsRule) => api(`/savings-rules/${item.id}`, {
      method: 'PATCH', body: JSON.stringify({ active: !item.active }),
    }),
    onSuccess: refresh, onError: (error: Error) => setNotice(error.message),
  })
  const submit = (event: FormEvent, action: () => void) => { event.preventDefault(); action() }
  return <>
    <div className="page-heading"><div><span className="eyebrow">DISPONIBILIDAD REAL</span><h2>Ahorro y objetivos</h2><p>Reservar dinero reduce lo disponible; no mueve fondos ni cambia el saldo bancario.</p></div><button className="button primary" onClick={() => openGoal()}>+ Nuevo objetivo</button></div>
    {notice && <div className="notice" role="status">{notice}</div>}
    {goalDraft && <section className="panel form-panel"><div className="panel-header"><h3>{editingGoal ? 'Editar objetivo' : 'Nuevo objetivo'}</h3><button className="icon-button" onClick={() => setGoalDraft(null)}>×</button></div>
      <form className="form-grid" onSubmit={(event) => submit(event, () => saveGoal.mutate())}>
        <label>Nombre<input required maxLength={120} value={goalDraft.name} onChange={(event) => setGoalDraft({ ...goalDraft, name: event.target.value })} /></label>
        <label>Meta<input required inputMode="decimal" pattern="[0-9]+([.,][0-9]{1,2})?" value={goalDraft.target_amount} onChange={(event) => setGoalDraft({ ...goalDraft, target_amount: event.target.value })} /></label>
        <label>Moneda<input required maxLength={3} value={goalDraft.currency} onChange={(event) => setGoalDraft({ ...goalDraft, currency: event.target.value.toUpperCase() })} /></label>
        <label>Prioridad<input required type="number" min={1} max={100} value={goalDraft.priority} onChange={(event) => setGoalDraft({ ...goalDraft, priority: event.target.value })} /></label>
        <label>Fecha objetivo (opcional)<input type="date" value={goalDraft.due_date} onChange={(event) => setGoalDraft({ ...goalDraft, due_date: event.target.value })} /></label>
        <div className="form-actions form-full"><button className="button secondary" type="button" onClick={() => setGoalDraft(null)}>Cancelar</button><button className="button primary" disabled={saveGoal.isPending}>Guardar</button></div>
      </form>
    </section>}
    <section className="panel"><div className="panel-header"><div><span className="eyebrow">METAS</span><h3>Tus objetivos</h3></div></div>
      {goals.length ? <div className="cards-grid">{goals.map((item) => <article className={`account-card ${item.active ? '' : 'muted'}`} key={item.id}><div className="account-card-top"><div className="account-symbol">◇</div><span className="chip">{item.active ? 'Activo' : 'Pausado'}</span></div><span className="eyebrow">Prioridad {item.priority}</span><h3>{item.name}</h3><p>{item.due_date ? `Meta para ${item.due_date}` : 'Sin fecha límite'}</p><div className="account-balance">{formatMoney(item.funded, item.currency)} <small>/ {formatMoney(item.target_amount, item.currency)}</small></div><progress max={Number(item.target_amount)} value={Number(item.funded)} style={{ width: '100%' }} /><div className="card-actions"><button onClick={() => { setSavingGoal(item.id); setSavingAccount(''); setSavingAmount('') }}>Aportar</button><button onClick={() => openGoal(item)}>Editar</button><button onClick={() => toggleGoal.mutate(item)}>{item.active ? 'Pausar' : 'Activar'}</button></div></article>)}</div> : <div className="empty">Añade un objetivo para asignar tus reservas.</div>}
    </section>
    <div className="form-actions" style={{ margin: '1rem 0' }}><button className="button secondary" onClick={() => { setSavingGoal(null); setSavingAccount(''); setSavingAmount('') }}>+ Reserva sin objetivo</button></div>
    {savingGoal !== undefined && <section className="panel form-panel"><div className="panel-header"><h3>{savingGoal ? `Aportar a ${goal(savingGoal)?.name}` : 'Reserva sin objetivo'}</h3><button className="icon-button" onClick={() => setSavingGoal(undefined)}>×</button></div>
      <form className="form-grid" onSubmit={(event) => submit(event, () => saveReservation.mutate())}>
        <label>Cuenta<select required value={savingAccount} onChange={(event) => setSavingAccount(event.target.value)}><option value="">Selecciona</option>{accounts.filter((item) => item.active && (!savingGoal || item.currency === goal(savingGoal)?.currency)).map((item) => <option key={item.id} value={item.id}>{item.name} · {item.currency}</option>)}</select></label>
        <label>Importe<input required inputMode="decimal" pattern="[0-9]+([.,][0-9]{1,2})?" value={savingAmount} onChange={(event) => setSavingAmount(event.target.value)} /></label>
        <div className="form-actions form-full"><button className="button secondary" type="button" onClick={() => setSavingGoal(undefined)}>Cancelar</button><button className="button primary" disabled={saveReservation.isPending}>Reservar</button></div>
      </form>
    </section>}
    <section className="panel"><div className="panel-header"><div><span className="eyebrow">DINERO ASIGNADO</span><h3>Reservas virtuales</h3></div></div>
      {reservations.length ? <div className="table-scroll"><table><thead><tr><th>Cuenta</th><th>Objetivo</th><th className="right">Reservado</th><th></th></tr></thead><tbody>{reservations.map((item) => <tr key={item.id}><td>{account(item.account_id)?.name || '—'}</td><td>{goal(item.goal_id)?.name || 'Reserva libre'}</td><td className="right amount">{formatMoney(item.amount, account(item.account_id)?.currency)}</td><td className="row-actions"><button onClick={() => { setReleaseId(item.id); setReleaseAmount(item.amount) }}>Liberar</button></td></tr>)}</tbody></table></div> : <div className="empty">Todavía no hay dinero reservado.</div>}
    </section>
    {releaseId !== null && <section className="panel form-panel"><div className="panel-header"><h3>Liberar reserva</h3><button className="icon-button" onClick={() => setReleaseId(null)}>×</button></div><form className="inline-form" onSubmit={(event) => submit(event, () => release.mutate())}><label>Importe<input required inputMode="decimal" pattern="[0-9]+([.,][0-9]{1,2})?" value={releaseAmount} onChange={(event) => setReleaseAmount(event.target.value)} /></label><button className="button primary" disabled={release.isPending}>Liberar</button></form></section>}
    <section className="panel"><div className="panel-header"><div><span className="eyebrow">AUTOMATIZACIÓN SUGERIDA</span><h3>Reglas de ahorro</h3></div><button className="button secondary" onClick={() => openRule()}>+ Regla</button></div>
      <p>Las reglas calculan una propuesta a partir del ingreso configurado; no reservan dinero hasta que registres una aportación.</p>
      {ruleDraft && <form className="form-grid" onSubmit={(event) => submit(event, () => saveRule.mutate())}><label>Nombre<input required value={ruleDraft.name} onChange={(event) => setRuleDraft({ ...ruleDraft, name: event.target.value })} /></label><label>Fuente de ingreso<select required value={ruleDraft.income_source_id} onChange={(event) => setRuleDraft({ ...ruleDraft, income_source_id: event.target.value })}><option value="">Selecciona</option>{sources.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Modo<select value={ruleDraft.mode} onChange={(event) => setRuleDraft({ ...ruleDraft, mode: event.target.value as RuleDraft['mode'] })}><option value="PERCENT">Porcentaje</option><option value="FIXED">Cantidad fija</option></select></label><label>Valor<input required inputMode="decimal" pattern="[0-9]+([.,][0-9]{1,2})?" value={ruleDraft.value} onChange={(event) => setRuleDraft({ ...ruleDraft, value: event.target.value })} /></label><div className="form-actions form-full"><button type="button" className="button secondary" onClick={() => setRuleDraft(null)}>Cancelar</button><button className="button primary" disabled={saveRule.isPending}>Guardar regla</button></div></form>}
      {rules.length ? <div className="table-scroll"><table><thead><tr><th>Regla</th><th>Ingreso</th><th>Valor</th><th>Propuesta</th><th></th></tr></thead><tbody>{rules.map((item) => <tr key={item.id}><td>{item.name}</td><td>{sources.find((source) => source.id === item.income_source_id)?.name || '—'}</td><td>{item.mode === 'PERCENT' ? `${item.value} %` : formatMoney(item.value, account(sources.find((source) => source.id === item.income_source_id)?.account_id || 0)?.currency)}</td><td>{formatMoney(recommendation?.rules.find((rule) => rule.rule_id === item.id)?.amount || '0', account(sources.find((source) => source.id === item.income_source_id)?.account_id || 0)?.currency)}</td><td className="row-actions"><button onClick={() => openRule(item)}>Editar</button><button onClick={() => toggleRule.mutate(item)}>{item.active ? 'Pausar' : 'Activar'}</button></td></tr>)}</tbody></table></div> : <div className="empty">Todavía no hay reglas de ahorro.</div>}
      {!!recommendation?.allocations.length && <p>Asignación propuesta: {recommendation.allocations.map((item) => `${goal(item.goal_id)?.name}: ${formatMoney(item.amount, item.currency)}`).join(' · ')}</p>}
    </section>
    {!!contributions.length && <section className="panel"><div className="panel-header"><div><span className="eyebrow">HISTORIAL</span><h3>Aportaciones y liberaciones</h3></div></div><div className="table-scroll"><table><thead><tr><th>Fecha</th><th>Objetivo</th><th>Cuenta</th><th className="right">Importe</th></tr></thead><tbody>{contributions.map((item) => <tr key={item.id}><td>{item.date}</td><td>{goal(item.goal_id)?.name || '—'}</td><td>{account(item.account_id)?.name || '—'}</td><td className="right amount">{formatMoney(item.amount, goal(item.goal_id)?.currency)}</td></tr>)}</tbody></table></div></section>}
  </>
}
