import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Account, AccountType, api, money, Settings, todayInTimezone } from '../api/client'

const accountTypes: { value: AccountType; label: string }[] = [
  { value: 'CHECKING', label: 'Cuenta corriente' }, { value: 'SAVINGS', label: 'Ahorro' },
  { value: 'CASH', label: 'Efectivo' }, { value: 'INVESTMENT', label: 'Inversión' },
  { value: 'CARD', label: 'Tarjeta' }, { value: 'OTHER', label: 'Otro' },
]
const schema = z.object({
  name: z.string().trim().min(1, 'Introduce un nombre'), type: z.enum(['CHECKING', 'SAVINGS', 'CASH', 'INVESTMENT', 'CARD', 'OTHER']),
  institution: z.string(), initial_balance: z.string().regex(/^-?\d+(?:[.,]\d{1,2})?$/, 'Importe inválido'),
  currency: z.string().regex(/^[A-Z]{3}$/, 'Usa un código de tres letras'), notes: z.string(),
})
type Values = z.infer<typeof schema>

export default function AccountsPage() {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState<Account | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [reconciling, setReconciling] = useState<Account | null>(null)
  const [bankBalance, setBankBalance] = useState('')
  const [notice, setNotice] = useState('')
  const { data: accounts = [], isLoading } = useQuery({ queryKey: ['accounts'], queryFn: () => api<Account[]>('/accounts') })
  const { data: settings } = useQuery({ queryKey: ['settings'], queryFn: () => api<Settings>('/settings') })
  const formatMoney = (value: string | number, currency = 'EUR') => money(value, currency, settings?.locale)
  const { register, handleSubmit, reset, formState: { errors } } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { name: '', type: 'CHECKING', institution: '', initial_balance: '0.00', currency: 'EUR', notes: '' } })
  const refresh = () => { queryClient.invalidateQueries({ queryKey: ['accounts'] }); queryClient.invalidateQueries({ queryKey: ['dashboard'] }) }
  const save = useMutation({ mutationFn: (values: Values) => {
    const payload: Record<string, unknown> = { ...values, initial_balance: values.initial_balance.replace(',', '.'), institution: values.institution || null, notes: values.notes || null }
    if (editing && payload.initial_balance === editing.initial_balance) delete payload.initial_balance
    if (editing && payload.currency === editing.currency) delete payload.currency
    return api<Account>(editing ? `/accounts/${editing.id}` : '/accounts', { method: editing ? 'PATCH' : 'POST', body: JSON.stringify(payload) })
  }, onSuccess: () => { refresh(); setShowForm(false); setEditing(null); setNotice('Cuenta guardada.') }, onError: (error: Error) => setNotice(error.message) })
  const toggle = useMutation({ mutationFn: (account: Account) => api<Account>(`/accounts/${account.id}`, { method: 'PATCH', body: JSON.stringify({ active: !account.active }) }), onSuccess: refresh, onError: (error: Error) => setNotice(error.message) })
  const reconcile = useMutation({ mutationFn: () => api<{ difference: string }>(`/accounts/${reconciling!.id}/reconcile`, { method: 'POST', body: JSON.stringify({ date: todayInTimezone(settings?.timezone), observed_balance: bankBalance.replace(',', '.') }) }), onSuccess: (result) => { refresh(); setReconciling(null); setNotice(result.difference === '0.00' ? 'El saldo ya coincide.' : `Ajuste registrado: ${formatMoney(result.difference, reconciling!.currency)}`) }, onError: (error: Error) => setNotice(error.message) })
  const open = (account?: Account) => {
    setEditing(account || null)
    reset(account ? { name: account.name, type: account.type, institution: account.institution || '', initial_balance: account.initial_balance, currency: account.currency, notes: account.notes || '' } : { name: '', type: 'CHECKING', institution: '', initial_balance: '0.00', currency: settings?.currency || 'EUR', notes: '' })
    setShowForm(true)
  }
  return <><div className="page-heading"><div><span className="eyebrow">ORGANIZACIÓN</span><h2>Tus cuentas</h2><p>El saldo se calcula con los movimientos registrados.</p></div><button className="button primary" onClick={() => open()}>+ Añadir cuenta</button></div>
    {notice && <div className="notice" role="status">{notice}</div>}
    {showForm && <section className="panel form-panel"><div className="panel-header"><h3>{editing ? 'Editar cuenta' : 'Nueva cuenta'}</h3><button className="icon-button" onClick={() => setShowForm(false)}>×</button></div><form onSubmit={handleSubmit((values) => save.mutate(values))} className="form-grid">
      <label>Nombre<input {...register('name')} /></label><label>Tipo<select {...register('type')}>{accountTypes.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
      <label>Entidad<input {...register('institution')} /></label><label>Moneda<input maxLength={3} {...register('currency')} /></label>
      <label>Saldo inicial<input inputMode="decimal" disabled={!!editing && accounts.some((item) => item.id === editing.id && item.balance !== item.initial_balance)} {...register('initial_balance')} /></label><label>Notas<input {...register('notes')} /></label>
      {(errors.name || errors.initial_balance || errors.currency) && <div className="error form-full">{errors.name?.message || errors.initial_balance?.message || errors.currency?.message}</div>}
      <div className="form-actions form-full"><button type="button" className="button secondary" onClick={() => setShowForm(false)}>Cancelar</button><button className="button primary" disabled={save.isPending}>Guardar cuenta</button></div>
    </form></section>}
    {reconciling && <section className="panel form-panel"><div className="panel-header"><h3>Conciliar {reconciling.name}</h3><button className="icon-button" onClick={() => setReconciling(null)}>×</button></div><p>Saldo calculado: <strong>{formatMoney(reconciling.balance, reconciling.currency)}</strong>. Indica el saldo observado en el banco; se registrará un ajuste identificable.</p><div className="inline-form"><label>Saldo del banco<input inputMode="decimal" value={bankBalance} onChange={(event) => setBankBalance(event.target.value)} /></label><button className="button primary" disabled={reconcile.isPending || !/^-?\d+(?:[.,]\d{1,2})?$/.test(bankBalance)} onClick={() => reconcile.mutate()}>Conciliar</button></div></section>}
    {isLoading ? <div className="panel">Cargando cuentas...</div> : accounts.length ? <div className="cards-grid">{accounts.map((account) => <article className={`account-card ${account.active ? '' : 'muted'}`} key={account.id}><div className="account-card-top"><div className="account-symbol">{account.type === 'CASH' ? '€' : account.type === 'SAVINGS' ? '◇' : '▣'}</div><span className="chip">{account.active ? 'Activa' : 'Inactiva'}</span></div><span className="eyebrow">{accountTypes.find((item) => item.value === account.type)?.label}</span><h3>{account.name}</h3><p>{account.institution || 'Sin entidad'}</p><div className="account-balance">{formatMoney(account.balance, account.currency)}</div><div className="card-actions"><button onClick={() => open(account)}>Editar</button><button onClick={() => { setReconciling(account); setBankBalance(account.balance) }}>Conciliar</button><button onClick={() => toggle.mutate(account)}>{account.active ? 'Desactivar' : 'Activar'}</button></div></article>)}</div> : <div className="panel empty">Todavía no tienes cuentas. Añade una para empezar.</div>}
  </>
}
