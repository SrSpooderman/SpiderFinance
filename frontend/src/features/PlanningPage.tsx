import { FormEvent, Fragment, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Account, api, Category, Debt, IncomeSource, money, MovementPage, PlanningLink,
  RecurringExpense, ScheduledExpense, Settings, todayInTimezone, UpcomingEvent,
} from '../api/client'
import './PlanningPage.css'

type Tab = 'income' | 'recurring' | 'scheduled' | 'debt'
type Item = IncomeSource | RecurringExpense | ScheduledExpense | Debt
type Draft = {
  name: string; amount: string; principal: string; installment_amount: string
  account_id: string; category_id: string; day_rule: string; day_of_month: string
  frequency: string; starts_on: string; ends_on: string; due_date: string; due_day: string
  active: boolean; is_primary: boolean
}

const tabs: { id: Tab; label: string; path: string }[] = [
  { id: 'income', label: 'Ingresos', path: 'income-sources' },
  { id: 'recurring', label: 'Recurrentes', path: 'recurring-expenses' },
  { id: 'scheduled', label: 'Gastos únicos', path: 'scheduled-expenses' },
  { id: 'debt', label: 'Deudas', path: 'debts' },
]
const eventLabels = { INCOME: 'Ingreso', RECURRING: 'Gasto recurrente', SCHEDULED: 'Gasto único', DEBT: 'Cuota' }
const emptyDraft = (today: string): Draft => ({
  name: '', amount: '', principal: '', installment_amount: '', account_id: '', category_id: '',
  day_rule: 'FIXED_DAY', day_of_month: '1', frequency: 'MONTHLY',
  starts_on: today, ends_on: '', due_date: today, due_day: '1', active: true, is_primary: false,
})
const normalized = (value: string) => value.replace(',', '.')

export default function PlanningPage() {
  const queryClient = useQueryClient()
  const [tab, setTab] = useState<Tab>('income')
  const [draft, setDraft] = useState<Draft | null>(null)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [payingEvent, setPayingEvent] = useState<UpcomingEvent | null>(null)
  const [openMonths, setOpenMonths] = useState<Record<string, boolean>>({})
  const [transactionId, setTransactionId] = useState('')
  const [notice, setNotice] = useState('')
  const { data: settings } = useQuery({ queryKey: ['settings'], queryFn: () => api<Settings>('/settings') })
  const { data: accounts = [] } = useQuery({ queryKey: ['accounts'], queryFn: () => api<Account[]>('/accounts') })
  const { data: categories = [] } = useQuery({ queryKey: ['categories'], queryFn: () => api<Category[]>('/categories') })
  const { data: income = [] } = useQuery({ queryKey: ['planning', 'income'], queryFn: () => api<IncomeSource[]>('/income-sources') })
  const { data: recurring = [] } = useQuery({ queryKey: ['planning', 'recurring'], queryFn: () => api<RecurringExpense[]>('/recurring-expenses') })
  const { data: scheduled = [] } = useQuery({ queryKey: ['planning', 'scheduled'], queryFn: () => api<ScheduledExpense[]>('/scheduled-expenses') })
  const { data: debts = [] } = useQuery({ queryKey: ['planning', 'debt'], queryFn: () => api<Debt[]>('/debts') })
  const { data: upcoming = [] } = useQuery({ queryKey: ['upcoming'], queryFn: () => api<UpcomingEvent[]>('/upcoming') })
  const { data: links = [] } = useQuery({ queryKey: ['planning-links'], queryFn: () => api<PlanningLink[]>('/planning-links') })
  const { data: movements } = useQuery({ queryKey: ['transactions', 'planning'], queryFn: () => api<MovementPage>('/transactions?page_size=100') })
  const today = todayInTimezone(settings?.timezone)
  const formatMoney = (amount: string, currency = 'EUR') => money(amount, currency, settings?.locale)
  const account = (id: number) => accounts.find((item) => item.id === id)
  const selected = { income, recurring, scheduled, debt: debts }[tab] as Item[]
  const path = tabs.find((item) => item.id === tab)!.path
  const monthlyEvents = upcoming.reduce((months, event) => {
    const month = event.date.slice(0, 7)
    months.set(month, [...(months.get(month) || []), event])
    return months
  }, new Map<string, UpcomingEvent[]>())
  const firstOpenMonth = monthlyEvents.has(today.slice(0, 7)) ? today.slice(0, 7) : monthlyEvents.keys().next().value
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['planning'] })
    queryClient.invalidateQueries({ queryKey: ['upcoming'] })
    queryClient.invalidateQueries({ queryKey: ['planning-links'] })
  }

  const open = (item?: Item) => {
    const next = emptyDraft(today)
    if (item) {
      next.name = item.name
      next.account_id = String(item.account_id)
      if ('amount' in item) next.amount = item.amount
      if ('starts_on' in item) next.starts_on = item.starts_on
      if ('active' in item) next.active = item.active
      if ('category_id' in item) next.category_id = String(item.category_id || '')
      if ('ends_on' in item) next.ends_on = item.ends_on || ''
      if ('day_rule' in item) {
        next.day_rule = item.day_rule
        next.day_of_month = String(item.day_of_month || 1)
        next.is_primary = item.is_primary
      }
      if ('frequency' in item) next.frequency = item.frequency
      if ('due_date' in item) next.due_date = item.due_date
      if ('principal' in item) {
        next.principal = item.principal
        next.installment_amount = item.installment_amount
        next.due_day = String(item.due_day)
      }
    }
    setEditingId(item?.id ?? null)
    setDraft(next)
    setNotice('')
  }

  const save = useMutation({
    mutationFn: async () => {
      if (!draft) throw new Error('Formulario vacío')
      const common = { name: draft.name.trim(), account_id: Number(draft.account_id) }
      let payload: Record<string, unknown>
      if (tab === 'income') payload = {
        ...common, amount: normalized(draft.amount), day_rule: draft.day_rule,
        day_of_month: draft.day_rule === 'FIXED_DAY' ? Number(draft.day_of_month) : null,
        starts_on: draft.starts_on, ends_on: draft.ends_on || null,
        active: draft.active, is_primary: draft.is_primary,
      }
      else if (tab === 'recurring') payload = {
        ...common, amount: normalized(draft.amount), category_id: draft.category_id ? Number(draft.category_id) : null,
        frequency: draft.frequency, starts_on: draft.starts_on, ends_on: draft.ends_on || null, active: draft.active,
      }
      else if (tab === 'scheduled') payload = {
        ...common, amount: normalized(draft.amount), category_id: draft.category_id ? Number(draft.category_id) : null,
        due_date: draft.due_date,
      }
      else payload = {
        ...common, principal: normalized(draft.principal), installment_amount: normalized(draft.installment_amount),
        starts_on: draft.starts_on, due_day: Number(draft.due_day), active: draft.active,
      }
      return api(`/${path}${editingId ? `/${editingId}` : ''}`, {
        method: editingId ? 'PATCH' : 'POST', body: JSON.stringify(payload),
      })
    },
    onSuccess: () => { refresh(); setDraft(null); setEditingId(null); setNotice('Plan guardado.') },
    onError: (error: Error) => setNotice(error.message),
  })
  const changeStatus = useMutation({
    mutationFn: ({ item, next }: { item: Item; next: boolean }) =>
      api(`/${path}/${item.id}`, {
        method: 'PATCH', body: JSON.stringify(tab === 'scheduled' ? { status: next ? 'PLANNED' : 'CANCELLED' } : { active: next }),
      }),
    onSuccess: () => { refresh(); setNotice('Estado actualizado.') },
    onError: (error: Error) => setNotice(error.message),
  })
  const remove = useMutation({
    mutationFn: ({ section, id }: { section: Tab; id: number }) =>
      api<void>(`/${tabs.find((item) => item.id === section)!.path}/${id}`, { method: 'DELETE' }),
    onSuccess: (_, deleted) => {
      refresh()
      queryClient.invalidateQueries({ queryKey: ['savings'] })
      queryClient.invalidateQueries({ queryKey: ['forecast'] })
      if (tab === deleted.section && editingId === deleted.id) { setDraft(null); setEditingId(null) }
      setPayingEvent(null)
      setNotice('Regla eliminada. Los movimientos reales se conservan.')
    },
    onError: (error: Error) => setNotice(error.message),
  })
  const link = useMutation({
    mutationFn: async () => {
      if (!payingEvent || !transactionId) throw new Error('Selecciona un movimiento confirmado')
      const routes = {
        INCOME: `/income-sources/${payingEvent.source_id}/receipts`,
        RECURRING: `/recurring-expenses/${payingEvent.source_id}/payments`,
        SCHEDULED: `/scheduled-expenses/${payingEvent.source_id}/pay`,
        DEBT: `/debts/${payingEvent.source_id}/payments`,
      }
      return api(routes[payingEvent.kind], {
        method: 'POST', body: JSON.stringify({
          transaction_id: Number(transactionId),
          ...(['INCOME', 'RECURRING'].includes(payingEvent.kind) ? { due_date: payingEvent.date } : {}),
        }),
      })
    },
    onSuccess: () => { refresh(); setPayingEvent(null); setTransactionId(''); setNotice('Movimiento vinculado al vencimiento.') },
    onError: (error: Error) => setNotice(error.message),
  })
  const unlink = useMutation({
    mutationFn: (item: PlanningLink) => {
      const routes = {
        INCOME: `/income-sources/${item.source_id}/receipts/${item.id}`,
        RECURRING: `/recurring-expenses/${item.source_id}/payments/${item.id}`,
        SCHEDULED: `/scheduled-expenses/${item.source_id}/pay`,
        DEBT: `/debts/${item.source_id}/payments/${item.id}`,
      }
      return api(routes[item.kind], { method: 'DELETE' })
    },
    onSuccess: () => { refresh(); setNotice('Vínculo retirado. El movimiento real se conserva.') },
    onError: (error: Error) => setNotice(error.message),
  })
  const submit = (event: FormEvent) => { event.preventDefault(); save.mutate() }
  const set = (key: keyof Draft, value: string | boolean) => setDraft((current) => current && ({ ...current, [key]: value }))
  const availableMovements = movements?.items.filter((item) =>
    payingEvent && item.status === 'CLEARED' &&
    (payingEvent.kind === 'INCOME' ? item.type === 'INCOME' && item.destination_account_id === payingEvent.account_id
      : item.type === 'EXPENSE' && item.source_account_id === payingEvent.account_id)
  ) || []

  return <>
    <div className="page-heading"><div><span className="eyebrow">PRÓXIMOS COMPROMISOS</span><h2>Planificación</h2></div></div>
    {notice && <div className="notice" role="status">{notice}</div>}
    <section className="panel">
      <div className="panel-header"><div><span className="eyebrow">CALENDARIO</span><h3>Próximos 90 días</h3></div></div>
      {upcoming.length ? [...monthlyEvents].map(([month, events]) =>
        <details className="planning-month" key={month} open={openMonths[month] ?? month === firstOpenMonth} onToggle={(event) => {
          const isOpen = event.currentTarget.open
          setOpenMonths((current) => current[month] === isOpen ? current : { ...current, [month]: isOpen })
        }}>
          <summary><span className="planning-month-name">{new Intl.DateTimeFormat(settings?.locale || 'es-ES', { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${month}-01T12:00:00Z`))}</span><span className="planning-month-count">{events.length} {events.length === 1 ? 'vencimiento' : 'vencimientos'}</span></summary>
          <div className="table-scroll"><table><thead><tr><th>Fecha</th><th>Concepto</th><th>Cuenta</th><th>Tipo</th><th className="right">Importe previsto</th><th></th></tr></thead><tbody>
            {events.map((event) => {
              const isPaying = payingEvent?.kind === event.kind && payingEvent.source_id === event.source_id && payingEvent.date === event.date
              return <Fragment key={`${event.kind}-${event.source_id}-${event.date}`}>
                <tr><td>{event.date.split('-').reverse().join('/')}{event.overdue && <small className="table-note">Vencido</small>}</td><td><strong>{event.name}</strong></td><td>{account(event.account_id)?.name || '—'}</td><td>{eventLabels[event.kind]}</td><td className="right amount">{event.kind === 'INCOME' ? '+' : '−'}{formatMoney(event.amount, event.currency)}</td><td className="row-actions"><button aria-expanded={isPaying} onClick={() => { setPayingEvent(isPaying ? null : event); setTransactionId('') }}>{event.kind === 'INCOME' ? 'Vincular cobro' : 'Vincular pago'}</button></td></tr>
                {isPaying && <tr className="planning-link-row"><td colSpan={6}><div className="planning-link-form"><div className="panel-header"><h3>Vincular {event.name}</h3><button className="icon-button" aria-label="Cerrar vínculo" onClick={() => setPayingEvent(null)}>×</button></div>
                  <p>Selecciona un movimiento confirmado de la cuenta {account(event.account_id)?.name}. El importe real puede diferir del previsto.</p>
                  <div className="inline-form"><label>Movimiento<select value={transactionId} onChange={(selection) => setTransactionId(selection.target.value)}><option value="">Selecciona un movimiento</option>{availableMovements.map((item) => <option key={item.id} value={item.id}>{item.date} · {item.concept} · {formatMoney(item.amount, event.currency)}</option>)}</select></label><button className="button primary" disabled={!transactionId || link.isPending} onClick={() => link.mutate()}>Vincular</button></div>
                  {!availableMovements.length && <p className="table-note">Registra primero el movimiento real en «Movimientos» y vuelve aquí.</p>}
                </div></td></tr>}
              </Fragment>
            })}
          </tbody></table></div>
        </details>) : <div className="empty">No hay vencimientos previstos en este periodo.</div>}
    </section>
    <div className="panel-header planning-header"><div><span className="eyebrow">TUS REGLAS</span><h3>Ingresos y obligaciones</h3></div><button className="button primary" onClick={() => open()}>+ Añadir</button></div>
    <div className="planning-tabs" role="tablist" aria-label="Tipo de planificación">{tabs.map((item) => <button key={item.id} role="tab" aria-selected={tab === item.id} className={tab === item.id ? 'active' : ''} onClick={() => { setTab(item.id); setDraft(null); setEditingId(null) }}>{item.label}</button>)}</div>
    {draft && <section className="panel form-panel"><div className="panel-header"><h3>{editingId ? 'Editar' : 'Añadir'} {tabs.find((item) => item.id === tab)?.label.toLowerCase()}</h3><button className="icon-button" onClick={() => setDraft(null)}>×</button></div>
      <form className="form-grid" onSubmit={submit}>
        <label>Nombre<input required maxLength={120} value={draft.name} onChange={(event) => set('name', event.target.value)} /></label>
        <label>Cuenta<select required value={draft.account_id} onChange={(event) => set('account_id', event.target.value)}><option value="">Selecciona</option>{accounts.filter((item) => item.active || String(item.id) === draft.account_id).map((item) => <option key={item.id} value={item.id}>{item.name} · {item.currency}</option>)}</select></label>
        {tab !== 'debt' && <label>Importe previsto<input required inputMode="decimal" pattern="[0-9]+([.,][0-9]{1,2})?" value={draft.amount} onChange={(event) => set('amount', event.target.value)} /></label>}
        {(tab === 'recurring' || tab === 'scheduled') && <label>Categoría<select value={draft.category_id} onChange={(event) => set('category_id', event.target.value)}><option value="">Sin categoría</option>{categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}
        {tab === 'income' && <><label>Regla de cobro<select value={draft.day_rule} onChange={(event) => set('day_rule', event.target.value)}><option value="FIXED_DAY">Día fijo</option><option value="LAST_DAY_OF_MONTH">Último día del mes</option><option value="FIRST_BUSINESS_DAY">Primer día laborable</option></select></label>{draft.day_rule === 'FIXED_DAY' && <label>Día del mes<input required type="number" min={1} max={31} value={draft.day_of_month} onChange={(event) => set('day_of_month', event.target.value)} /></label>}</>}
        {tab === 'recurring' && <label>Frecuencia<select value={draft.frequency} onChange={(event) => set('frequency', event.target.value)}><option value="MONTHLY">Mensual</option><option value="WEEKLY">Semanal</option></select></label>}
        {tab === 'debt' && <><label>Principal pendiente al empezar<input required inputMode="decimal" pattern="[0-9]+([.,][0-9]{1,2})?" value={draft.principal} onChange={(event) => set('principal', event.target.value)} /></label><label>Cuota prevista<input required inputMode="decimal" pattern="[0-9]+([.,][0-9]{1,2})?" value={draft.installment_amount} onChange={(event) => set('installment_amount', event.target.value)} /></label><label>Día de pago<input required type="number" min={1} max={31} value={draft.due_day} onChange={(event) => set('due_day', event.target.value)} /></label></>}
        {tab === 'scheduled' ? <label>Vencimiento<input required type="date" value={draft.due_date} onChange={(event) => set('due_date', event.target.value)} /></label> : <><label>Desde<input required type="date" value={draft.starts_on} onChange={(event) => set('starts_on', event.target.value)} /></label>{tab !== 'debt' && <label>Hasta (opcional)<input type="date" value={draft.ends_on} onChange={(event) => set('ends_on', event.target.value)} /></label>}</>}
        {tab === 'income' && <label className="checkbox"><input type="checkbox" checked={draft.is_primary} onChange={(event) => set('is_primary', event.target.checked)} /> Ingreso principal</label>}
        <div className="form-actions form-full"><button type="button" className="button secondary" onClick={() => setDraft(null)}>Cancelar</button><button className="button primary" disabled={save.isPending}>Guardar</button></div>
      </form>
    </section>}
    <section className="panel">{selected.length ? <div className="table-scroll"><table><thead><tr><th>Nombre</th><th>Cuenta</th><th>Detalle</th><th className="right">Importe</th><th>Estado</th><th></th></tr></thead><tbody>
      {selected.map((item) => {
        const isDebt = 'principal' in item
        const isScheduled = 'status' in item
        const active = isScheduled ? item.status === 'PLANNED' : item.active
        const detail = 'day_rule' in item ? (item.day_rule === 'FIXED_DAY' ? `Día ${item.day_of_month} de cada mes` : item.day_rule === 'LAST_DAY_OF_MONTH' ? 'Fin de mes' : 'Primer laborable')
          : 'frequency' in item ? (item.frequency === 'WEEKLY' ? 'Semanal' : 'Mensual')
            : isScheduled ? item.due_date : `Día ${item.due_day} de cada mes`
        return <tr key={item.id}><td><strong>{item.name}</strong>{'is_primary' in item && item.is_primary && <small className="table-note">Principal</small>}</td><td>{account(item.account_id)?.name || '—'}</td><td>{detail}</td><td className="right amount">{formatMoney(isDebt ? item.remaining : item.amount, account(item.account_id)?.currency)}{isDebt && <small className="table-note">Pendiente · cuota {formatMoney(item.installment_amount, account(item.account_id)?.currency)}</small>}</td><td>{isScheduled ? item.status === 'PAID' ? 'Pagado' : active ? 'Previsto' : 'Cancelado' : active ? 'Activo' : 'Inactivo'}</td><td className="row-actions"><button disabled={isScheduled && item.status === 'PAID'} onClick={() => open(item)}>Editar</button><button disabled={isScheduled && item.status === 'PAID'} onClick={() => changeStatus.mutate({ item, next: !active })}>{active ? 'Pausar' : 'Activar'}</button><button disabled={remove.isPending} onClick={() => { if (window.confirm(`¿Eliminar «${item.name}»? Se eliminarán sus vínculos${tab === 'income' ? ' y sus reglas de ahorro asociadas' : ''}. Los movimientos reales se conservarán.`)) remove.mutate({ section: tab, id: item.id }) }}>Eliminar</button></td></tr>
      })}
    </tbody></table></div> : <div className="empty">Todavía no has añadido elementos en esta sección.</div>}</section>
    {links.length > 0 && <section className="panel"><div className="panel-header"><div><span className="eyebrow">TRAZABILIDAD</span><h3>Movimientos vinculados</h3></div></div>
      <div className="table-scroll"><table><thead><tr><th>Tipo</th><th>Vencimiento</th><th>Movimiento real</th><th></th></tr></thead><tbody>{links.map((item) => {
        const movement = movements?.items.find((entry) => entry.id === item.transaction_id)
        return <tr key={`${item.kind}-${item.id}`}><td>{eventLabels[item.kind]}</td><td>{item.due_date || '—'}</td><td>{movement ? `${movement.date} · ${movement.concept}` : `#${item.transaction_id}`}</td><td className="row-actions"><button disabled={unlink.isPending} onClick={() => { if (window.confirm('¿Retirar el vínculo? El movimiento real se conservará.')) unlink.mutate(item) }}>Desvincular</button></td></tr>
      })}</tbody></table></div>
    </section>}
  </>
}
