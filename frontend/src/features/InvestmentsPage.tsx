import { FormEvent, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Account, api, InvestmentContribution, InvestmentPosition, money, MovementPage,
  NetWorth, NetWorthSnapshot, Settings, todayInTimezone,
} from '../api/client'

type Draft = {
  account_id: string; name: string; symbol: string; units: string
  cost_basis: string; market_value: string; valued_on: string
}
const decimal = (value: string) => value.replace(',', '.')

export default function InvestmentsPage() {
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState<Draft | null>(null)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [transferId, setTransferId] = useState('')
  const [notice, setNotice] = useState('')
  const { data: settings } = useQuery({ queryKey: ['settings'], queryFn: () => api<Settings>('/settings') })
  const { data: accounts = [] } = useQuery({ queryKey: ['accounts'], queryFn: () => api<Account[]>('/accounts') })
  const { data: positions = [] } = useQuery({ queryKey: ['investments', 'positions'], queryFn: () => api<InvestmentPosition[]>('/investments/positions') })
  const { data: contributions = [] } = useQuery({ queryKey: ['investments', 'contributions'], queryFn: () => api<InvestmentContribution[]>('/investments/contributions') })
  const { data: report } = useQuery({ queryKey: ['net-worth'], queryFn: () => api<NetWorth>('/net-worth') })
  const { data: snapshots = [] } = useQuery({ queryKey: ['net-worth', 'snapshots'], queryFn: () => api<NetWorthSnapshot[]>('/net-worth/snapshots') })
  const { data: movements } = useQuery({ queryKey: ['transactions', 'investments'], queryFn: () => api<MovementPage>('/transactions?type=TRANSFER&page_size=100') })
  const investmentAccounts = accounts.filter((item) => item.type === 'INVESTMENT')
  const today = todayInTimezone(settings?.timezone)
  const formatMoney = (value: string | number, currency = settings?.currency || 'EUR') => money(value, currency, settings?.locale)
  const account = (id: number) => accounts.find((item) => item.id === id)
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['investments'] })
    queryClient.invalidateQueries({ queryKey: ['net-worth'] })
  }
  const open = (item?: InvestmentPosition) => {
    setDraft(item ? {
      account_id: String(item.account_id), name: item.name, symbol: item.symbol || '',
      units: item.units, cost_basis: item.cost_basis, market_value: item.market_value,
      valued_on: item.valued_on,
    } : {
      account_id: String(investmentAccounts[0]?.id || ''), name: '', symbol: '', units: '',
      cost_basis: '', market_value: '', valued_on: today,
    })
    setEditingId(item?.id || null)
  }
  const savePosition = useMutation({
    mutationFn: () => api(editingId ? `/investments/positions/${editingId}` : '/investments/positions', {
      method: editingId ? 'PATCH' : 'POST', body: JSON.stringify({
        account_id: Number(draft!.account_id), name: draft!.name.trim(), symbol: draft!.symbol || null,
        units: decimal(draft!.units), cost_basis: decimal(draft!.cost_basis),
        market_value: decimal(draft!.market_value), valued_on: draft!.valued_on,
      }),
    }),
    onSuccess: () => { refresh(); setDraft(null); setNotice('Posición guardada.') },
    onError: (error: Error) => setNotice(error.message),
  })
  const deletePosition = useMutation({
    mutationFn: (id: number) => api(`/investments/positions/${id}`, { method: 'DELETE' }),
    onSuccess: () => { refresh(); setNotice('Posición eliminada.') },
    onError: (error: Error) => setNotice(error.message),
  })
  const link = useMutation({
    mutationFn: () => api('/investments/contributions', {
      method: 'POST', body: JSON.stringify({ transaction_id: Number(transferId) }),
    }),
    onSuccess: () => { refresh(); setTransferId(''); setNotice('Transferencia vinculada a inversión.') },
    onError: (error: Error) => setNotice(error.message),
  })
  const unlink = useMutation({
    mutationFn: (id: number) => api(`/investments/contributions/${id}`, { method: 'DELETE' }),
    onSuccess: () => { refresh(); setNotice('Vínculo retirado; la transferencia se conserva.') },
    onError: (error: Error) => setNotice(error.message),
  })
  const snapshot = useMutation({
    mutationFn: () => api<NetWorthSnapshot[]>('/net-worth/snapshots', { method: 'POST' }),
    onSuccess: () => { refresh(); setNotice('Snapshot de patrimonio guardado.') },
    onError: (error: Error) => setNotice(error.message),
  })
  const transfers = movements?.items.filter((item) =>
    item.status === 'CLEARED' && item.date <= today &&
    investmentAccounts.some((investment) => investment.id === item.destination_account_id) &&
    !contributions.some((link) => link.transaction_id === item.id)
  ) || []
  const submit = (event: FormEvent) => { event.preventDefault(); savePosition.mutate() }
  return <>
    <div className="page-heading"><div><span className="eyebrow">ACTIVOS Y PASIVOS</span><h2>Inversiones y patrimonio</h2></div><button className="button primary" disabled={!investmentAccounts.length} onClick={() => open()}>+ Posición</button></div>
    {notice && <div className="notice" role="status">{notice}</div>}
    {!investmentAccounts.length && <div className="notice">Crea primero una cuenta de tipo «Inversión» en «Cuentas».</div>}
    <section className="panel"><div className="panel-header"><div><span className="eyebrow">PATRIMONIO ACTUAL</span><h3>Activos menos pasivos por moneda</h3></div><button className="button secondary" disabled={!report?.currencies.length || snapshot.isPending || snapshots.some((item) => item.date === today)} onClick={() => snapshot.mutate()}>Guardar snapshot de hoy</button></div>
      {report?.currencies.length ? <div className="cards-grid">{report.currencies.map((item) => <article className="account-card" key={item.currency}><span className="eyebrow">{item.currency}</span><h3>{formatMoney(item.net_worth, item.currency)}</h3><p>Activos: {formatMoney(item.assets, item.currency)}</p><p>Pasivos: {formatMoney(item.liabilities, item.currency)}</p></article>)}</div> : <div className="empty">Añade cuentas para calcular tu patrimonio.</div>}
    </section>
    {draft && <section className="panel form-panel"><div className="panel-header"><h3>{editingId ? 'Editar posición' : 'Nueva posición'}</h3><button className="icon-button" onClick={() => setDraft(null)}>×</button></div><form className="form-grid" onSubmit={submit}>
      <label>Cuenta de inversión<select required value={draft.account_id} onChange={(event) => setDraft({ ...draft, account_id: event.target.value })}><option value="">Selecciona</option>{investmentAccounts.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.currency}</option>)}</select></label>
      <label>Nombre<input required maxLength={120} value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} /></label>
      <label>Símbolo (opcional)<input maxLength={32} value={draft.symbol} onChange={(event) => setDraft({ ...draft, symbol: event.target.value })} /></label>
      <label>Unidades<input required inputMode="decimal" pattern="[0-9]+([.,][0-9]{1,8})?" value={draft.units} onChange={(event) => setDraft({ ...draft, units: event.target.value })} /></label>
      <label>Coste invertido<input required inputMode="decimal" pattern="[0-9]+([.,][0-9]{1,2})?" value={draft.cost_basis} onChange={(event) => setDraft({ ...draft, cost_basis: event.target.value })} /></label>
      <label>Valor de mercado<input required inputMode="decimal" pattern="[0-9]+([.,][0-9]{1,2})?" value={draft.market_value} onChange={(event) => setDraft({ ...draft, market_value: event.target.value })} /></label>
      <label>Fecha de valoración<input required type="date" max={today} value={draft.valued_on} onChange={(event) => setDraft({ ...draft, valued_on: event.target.value })} /></label>
      <div className="form-actions form-full"><button type="button" className="button secondary" onClick={() => setDraft(null)}>Cancelar</button><button className="button primary" disabled={savePosition.isPending}>Guardar</button></div>
    </form></section>}
    <section className="panel"><div className="panel-header"><div><span className="eyebrow">CARTERA</span><h3>Posiciones</h3></div></div>
      {positions.length ? <div className="table-scroll"><table><thead><tr><th>Posición</th><th>Cuenta</th><th className="right">Unidades</th><th className="right">Coste</th><th className="right">Valor</th><th>Fecha</th><th></th></tr></thead><tbody>{positions.map((item) => <tr key={item.id}><td><strong>{item.name}</strong>{item.symbol && <small className="table-note">{item.symbol}</small>}</td><td>{account(item.account_id)?.name || '—'}</td><td className="right">{item.units}</td><td className="right">{formatMoney(item.cost_basis, account(item.account_id)?.currency)}</td><td className="right amount">{formatMoney(item.market_value, account(item.account_id)?.currency)}</td><td>{item.valued_on}</td><td className="row-actions"><button onClick={() => open(item)}>Editar</button><button onClick={() => { if (window.confirm('¿Eliminar esta posición?')) deletePosition.mutate(item.id) }}>Eliminar</button></td></tr>)}</tbody></table></div> : <div className="empty">Todavía no hay posiciones valoradas.</div>}
    </section>
    <section className="panel"><div className="panel-header"><div><span className="eyebrow">FLUJO DE FONDOS</span><h3>Aportaciones desde otras cuentas</h3></div></div>
      <div className="inline-form"><label>Transferencia confirmada<select value={transferId} onChange={(event) => setTransferId(event.target.value)}><option value="">Selecciona</option>{transfers.map((item) => <option key={item.id} value={item.id}>{item.date} · {item.concept} · {formatMoney(item.amount, account(item.destination_account_id || 0)?.currency)}</option>)}</select></label><button className="button primary" disabled={!transferId || link.isPending} onClick={() => link.mutate()}>Vincular</button></div>
      {contributions.length > 0 && <div className="table-scroll"><table><thead><tr><th>Cuenta</th><th>Transferencia</th><th></th></tr></thead><tbody>{contributions.map((item) => <tr key={item.id}><td>{account(item.account_id)?.name || '—'}</td><td>#{item.transaction_id} · {movements?.items.find((movement) => movement.id === item.transaction_id)?.concept || 'Movimiento anterior'}</td><td className="row-actions"><button onClick={() => { if (window.confirm('¿Retirar el vínculo? La transferencia real se conservará.')) unlink.mutate(item.id) }}>Desvincular</button></td></tr>)}</tbody></table></div>}
    </section>
    {report?.accounts.length ? <section className="panel"><div className="panel-header"><div><span className="eyebrow">VALORACIÓN</span><h3>Valor por cuenta</h3></div></div><div className="table-scroll"><table><thead><tr><th>Cuenta</th><th className="right">Saldo contable</th><th className="right">En posiciones</th><th className="right">Valor patrimonial</th></tr></thead><tbody>{report.accounts.map((item) => <tr key={item.id}><td>{item.name}</td><td className="right">{formatMoney(item.book_balance, item.currency)}</td><td className="right">{item.type === 'INVESTMENT' ? formatMoney(item.position_value, item.currency) : '—'}</td><td className="right amount">{formatMoney(item.asset_value, item.currency)}</td></tr>)}</tbody></table></div></section> : null}
    {snapshots.length > 0 && <section className="panel"><div className="panel-header"><div><span className="eyebrow">HISTÓRICO</span><h3>Snapshots de patrimonio</h3></div></div><div className="table-scroll"><table><thead><tr><th>Fecha</th><th>Moneda</th><th className="right">Activos</th><th className="right">Pasivos</th><th className="right">Patrimonio</th></tr></thead><tbody>{snapshots.map((item) => <tr key={item.id}><td>{item.date}</td><td>{item.currency}</td><td className="right">{formatMoney(item.assets, item.currency)}</td><td className="right">{formatMoney(item.liabilities, item.currency)}</td><td className="right amount">{formatMoney(item.net_worth, item.currency)}</td></tr>)}</tbody></table></div></section>}
  </>
}
