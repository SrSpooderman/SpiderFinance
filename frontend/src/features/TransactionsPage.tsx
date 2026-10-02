import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Account, api, Category, money, Movement, MovementPage, Settings, todayInTimezone, TransactionType } from '../api/client'

const schema = z.object({
  date: z.string().min(1), type: z.enum(['INCOME', 'EXPENSE', 'TRANSFER', 'ADJUSTMENT']),
  source_account_id: z.string(), destination_account_id: z.string(), category_id: z.string(),
  concept: z.string().trim().min(1, 'Introduce un concepto'), amount: z.string().regex(/^\d+(?:[.,]\d{1,2})?$/, 'Importe inválido'),
  payment_method: z.string(), is_fixed: z.boolean(), is_necessary: z.boolean(), notes: z.string(), status: z.enum(['CLEARED', 'PENDING']),
})
type Values = z.infer<typeof schema>
const names: Record<TransactionType, string> = { INCOME: 'Ingreso', EXPENSE: 'Gasto', TRANSFER: 'Transferencia', ADJUSTMENT: 'Ajuste' }
const emptyValues = (timezone?: string): Values => ({ date: todayInTimezone(timezone), type: 'EXPENSE', source_account_id: '', destination_account_id: '', category_id: '', concept: '', amount: '', payment_method: '', is_fixed: false, is_necessary: false, notes: '', status: 'CLEARED' })

export default function TransactionsPage() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [filterType, setFilterType] = useState('')
  const [editing, setEditing] = useState<Movement | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [notice, setNotice] = useState('')
  const { data: accounts = [] } = useQuery({ queryKey: ['accounts'], queryFn: () => api<Account[]>('/accounts') })
  const { data: categories = [] } = useQuery({ queryKey: ['categories'], queryFn: () => api<Category[]>('/categories') })
  const { data: settings } = useQuery({ queryKey: ['settings'], queryFn: () => api<Settings>('/settings') })
  const formatMoney = (value: string | number, currency = 'EUR') => money(value, currency, settings?.locale)
  const params = new URLSearchParams({ page: String(page), page_size: '15' })
  if (search) params.set('search', search)
  if (filterType) params.set('type', filterType)
  const { data, isLoading } = useQuery({ queryKey: ['transactions', page, search, filterType], queryFn: () => api<MovementPage>(`/transactions?${params}`) })
  const { register, handleSubmit, reset, watch, formState: { errors } } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: emptyValues() })
  const kind = watch('type')
  const refresh = () => { queryClient.invalidateQueries({ queryKey: ['transactions'] }); queryClient.invalidateQueries({ queryKey: ['accounts'] }); queryClient.invalidateQueries({ queryKey: ['dashboard'] }); queryClient.invalidateQueries({ queryKey: ['forecast'] }) }
  const save = useMutation({ mutationFn: (values: Values) => {
    if (values.type === 'TRANSFER' && values.source_account_id === values.destination_account_id) throw new Error('Elige dos cuentas distintas.')
    if (['EXPENSE', 'TRANSFER'].includes(values.type) && !values.source_account_id) throw new Error('Elige una cuenta origen.')
    if (['INCOME', 'TRANSFER'].includes(values.type) && !values.destination_account_id) throw new Error('Elige una cuenta destino.')
    if (values.type === 'ADJUSTMENT' && (!!values.source_account_id === !!values.destination_account_id)) throw new Error('Para un ajuste, elige solo origen (resta) o destino (suma).')
    const payload = {
      ...values, amount: values.amount.replace(',', '.'),
      source_account_id: ['EXPENSE', 'TRANSFER', 'ADJUSTMENT'].includes(values.type) && values.source_account_id ? Number(values.source_account_id) : null,
      destination_account_id: ['INCOME', 'TRANSFER', 'ADJUSTMENT'].includes(values.type) && values.destination_account_id ? Number(values.destination_account_id) : null,
      category_id: values.category_id ? Number(values.category_id) : null,
      payment_method: values.payment_method || null, notes: values.notes || null,
    }
    return api<Movement>(editing ? `/transactions/${editing.id}` : '/transactions', { method: editing ? 'PATCH' : 'POST', body: JSON.stringify(payload) })
  }, onSuccess: () => { refresh(); setShowForm(false); setEditing(null); setNotice('Movimiento guardado.') }, onError: (error: Error) => setNotice(error.message) })
  const remove = useMutation({ mutationFn: (id: number) => api<void>(`/transactions/${id}`, { method: 'DELETE' }), onSuccess: () => { refresh(); setNotice('Movimiento eliminado.') }, onError: (error: Error) => setNotice(error.message) })
  const open = (movement?: Movement) => {
    setEditing(movement || null)
    reset(movement ? { date: movement.date, type: movement.type, source_account_id: String(movement.source_account_id || ''), destination_account_id: String(movement.destination_account_id || ''), category_id: String(movement.category_id || ''), concept: movement.concept, amount: movement.amount, payment_method: movement.payment_method || '', is_fixed: movement.is_fixed, is_necessary: movement.is_necessary, notes: movement.notes || '', status: movement.status } : emptyValues(settings?.timezone))
    setShowForm(true)
  }
  const accountName = (id: number | null) => accounts.find((item) => item.id === id)?.name || '—'
  return <><div className="page-heading"><div><span className="eyebrow">REGISTRO</span><h2>Movimientos</h2><p>Ingresos, gastos y transferencias en un mismo lugar.</p></div><button className="button primary" onClick={() => open()}>+ Nuevo movimiento</button></div>
    {notice && <div className="notice" role="status">{notice}</div>}
    {showForm && <section className="panel form-panel"><div className="panel-header"><h3>{editing ? 'Editar movimiento' : 'Nuevo movimiento'}</h3><button className="icon-button" onClick={() => setShowForm(false)}>×</button></div><form className="form-grid" onSubmit={handleSubmit((values) => save.mutate(values))}>
      <label>Tipo<select {...register('type')}><option value="EXPENSE">Gasto</option><option value="INCOME">Ingreso</option><option value="TRANSFER">Transferencia</option><option value="ADJUSTMENT">Ajuste</option></select></label><label>Fecha<input type="date" {...register('date')} /></label>
      {['EXPENSE', 'TRANSFER', 'ADJUSTMENT'].includes(kind) && <label>Cuenta origen<select {...register('source_account_id')}><option value="">Selecciona</option>{accounts.filter((item) => item.active || item.id === editing?.source_account_id).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}
      {['INCOME', 'TRANSFER', 'ADJUSTMENT'].includes(kind) && <label>Cuenta destino<select {...register('destination_account_id')}><option value="">Selecciona</option>{accounts.filter((item) => item.active || item.id === editing?.destination_account_id).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}
      <label>Concepto<input {...register('concept')} /></label><label>Importe<input inputMode="decimal" {...register('amount')} /></label>
      {kind !== 'TRANSFER' && <label>Categoría<select {...register('category_id')}><option value="">Sin categoría</option>{categories.map((item) => <option key={item.id} value={item.id}>{item.parent_id ? '↳ ' : ''}{item.name}</option>)}</select></label>}
      <label>Método de pago<input placeholder="Tarjeta, efectivo..." {...register('payment_method')} /></label><label>Estado<select {...register('status')}><option value="CLEARED">Confirmado</option><option value="PENDING">Pendiente</option></select></label>
      <label className="checkbox"><input type="checkbox" {...register('is_fixed')} /> Fijo</label><label className="checkbox"><input type="checkbox" {...register('is_necessary')} /> Necesario</label>
      <label className="form-full">Notas<textarea rows={2} {...register('notes')} /></label>
      {(errors.concept || errors.amount || errors.date) && <div className="error form-full">{errors.concept?.message || errors.amount?.message || errors.date?.message}</div>}
      <div className="form-actions form-full"><button type="button" className="button secondary" onClick={() => setShowForm(false)}>Cancelar</button><button className="button primary" disabled={save.isPending}>Guardar movimiento</button></div>
    </form></section>}
    <section className="panel"><div className="filters"><input aria-label="Buscar movimientos" placeholder="Buscar por concepto..." value={search} onChange={(event) => { setSearch(event.target.value); setPage(1) }} /><select aria-label="Filtrar por tipo" value={filterType} onChange={(event) => { setFilterType(event.target.value); setPage(1) }}><option value="">Todos los tipos</option>{Object.entries(names).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><span>{data?.total || 0} movimientos</span></div>
      {isLoading ? <div className="empty">Cargando movimientos...</div> : data?.items.length ? <div className="table-scroll"><table><thead><tr><th>Fecha</th><th>Concepto</th><th>Cuenta</th><th>Tipo</th><th className="right">Importe</th><th></th></tr></thead><tbody>{data.items.map((item) => <tr key={item.id}><td>{item.date.split('-').reverse().join('/')}</td><td><strong>{item.concept}</strong>{item.reconciliation && <small className="table-note">Conciliación</small>}{item.status === 'PENDING' && <small className="table-note">Pendiente · no afecta al saldo</small>}</td><td>{item.type === 'TRANSFER' ? `${accountName(item.source_account_id)} → ${accountName(item.destination_account_id)}` : accountName(item.source_account_id || item.destination_account_id)}</td><td><span className={`type-pill ${item.type.toLowerCase()}`}>{names[item.type]}</span></td><td className={`right amount ${item.type === 'INCOME' ? 'positive' : ''}`}>{item.type === 'TRANSFER' ? <><div>−{formatMoney(item.amount, accounts.find((account) => account.id === item.source_account_id)?.currency)}</div><small className="table-note">+{formatMoney(item.amount, accounts.find((account) => account.id === item.destination_account_id)?.currency)} en destino</small></> : <>{item.type === 'EXPENSE' ? '−' : item.type === 'INCOME' ? '+' : ''}{formatMoney(item.amount, accounts.find((account) => account.id === (item.source_account_id || item.destination_account_id))?.currency)}</>}</td><td className="row-actions"><button onClick={() => open(item)}>Editar</button><button onClick={() => { if (window.confirm('¿Eliminar este movimiento?')) remove.mutate(item.id) }}>Eliminar</button></td></tr>)}</tbody></table></div> : <div className="empty">No hay movimientos para estos filtros.</div>}
      {data && data.total > data.page_size && <div className="pagination"><button disabled={page === 1} onClick={() => setPage(page - 1)}>← Anterior</button><span>Página {page} de {Math.ceil(data.total / data.page_size)}</span><button disabled={page * data.page_size >= data.total} onClick={() => setPage(page + 1)}>Siguiente →</button></div>}
    </section>
  </>
}
