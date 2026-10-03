import { ChangeEvent, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Account, api, getToken, ImportJob } from '../api/client'

const fields = [
  { id: 'date', label: 'Fecha *' }, { id: 'concept', label: 'Concepto *' },
  { id: 'amount', label: 'Importe *' }, { id: 'type', label: 'Tipo' },
  { id: 'account_id', label: 'Cuenta' }, { id: 'source_account_id', label: 'Cuenta origen' },
  { id: 'destination_account_id', label: 'Cuenta destino' }, { id: 'category_id', label: 'Categoría ID' },
  { id: 'status', label: 'Estado' }, { id: 'notes', label: 'Notas' },
  { id: 'payment_method', label: 'Método de pago' }, { id: 'external_id', label: 'ID externo' },
]
const aliases: Record<string, string[]> = {
  date: ['fecha', 'date', 'fecha operacion'],
  concept: ['concepto', 'description', 'descripcion', 'detalle', 'concept'],
  amount: ['importe', 'amount', 'cantidad', 'monto'],
  type: ['tipo', 'type'], account_id: ['cuenta', 'account_id'],
  external_id: ['id externo', 'external_id', 'reference', 'referencia'],
}

export default function ImportExportPage() {
  const queryClient = useQueryClient()
  const [jobId, setJobId] = useState<number | null>(null)
  const [sheet, setSheet] = useState('')
  const [mapping, setMapping] = useState<Record<string, string>>({})
  const [accountId, setAccountId] = useState('')
  const [positiveIsIncome, setPositiveIsIncome] = useState(true)
  const [previewDirty, setPreviewDirty] = useState(false)
  const [notice, setNotice] = useState('')
  const { data: accounts = [] } = useQuery({ queryKey: ['accounts'], queryFn: () => api<Account[]>('/accounts') })
  const { data: jobs = [] } = useQuery({ queryKey: ['imports'], queryFn: () => api<ImportJob[]>('/imports') })
  const { data: job } = useQuery({
    queryKey: ['imports', jobId], queryFn: () => api<ImportJob>(`/imports/${jobId}`), enabled: jobId !== null,
  })
  const { data: sheetHeaders = {} } = useQuery({
    queryKey: ['imports', jobId, 'sheets'],
    queryFn: () => api<Record<string, string[]>>(`/imports/${jobId}/sheets`),
    enabled: jobId !== null,
  })
  const selectedSheet = sheet || job?.selected_sheet || ''
  const headers = sheetHeaders[selectedSheet] || job?.headers || []
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['imports'] })
  }
  const selectJob = (item: ImportJob) => {
    setJobId(item.id)
    setSheet(item.selected_sheet || item.sheet_names[0] || '')
    setMapping(item.mapping || {})
    setAccountId(item.default_account_id ? String(item.default_account_id) : '')
    setPositiveIsIncome(item.positive_is_income)
    setPreviewDirty(false)
  }
  const upload = useMutation({
    mutationFn: async (file: File) => {
      const body = new FormData()
      body.append('file', file)
      const response = await fetch('/api/v1/imports', {
        method: 'POST', headers: { Authorization: `Bearer ${getToken()}` }, body,
      })
      if (!response.ok) {
        const error = await response.json().catch(() => ({}))
        throw new Error(typeof error.detail === 'string' ? error.detail : `Error ${response.status}`)
      }
      return response.json() as Promise<ImportJob>
    },
    onSuccess: (item) => { refresh(); selectJob(item); setNotice('Archivo cargado. Asigna las columnas y previsualiza.') },
    onError: (error: Error) => setNotice(error.message),
  })
  const preview = useMutation({
    mutationFn: () => api<ImportJob>(`/imports/${jobId}/preview`, {
      method: 'POST', body: JSON.stringify({
        sheet_name: selectedSheet, mapping, default_account_id: accountId ? Number(accountId) : null,
        positive_is_income: positiveIsIncome,
      }),
    }),
    onSuccess: () => { refresh(); setPreviewDirty(false); setNotice('Previsualización lista. Revisa los errores antes de confirmar.') },
    onError: (error: Error) => setNotice(error.message),
  })
  const confirm = useMutation({
    mutationFn: () => api<ImportJob>(`/imports/${jobId}/confirm`, { method: 'POST' }),
    onSuccess: (item) => {
      refresh()
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      queryClient.invalidateQueries({ queryKey: ['accounts'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      queryClient.invalidateQueries({ queryKey: ['forecast'] })
      setNotice(`Importación finalizada: ${item.imported_rows} movimientos creados; ${item.skipped_rows} filas omitidas.`)
    },
    onError: (error: Error) => setNotice(error.message),
  })
  const remove = useMutation({
    mutationFn: (id: number) => api(`/imports/${id}`, { method: 'DELETE' }),
    onSuccess: (_result, id) => { refresh(); if (jobId === id) { setJobId(null); setMapping({}) }; setNotice('Historial de importación eliminado. Los movimientos importados se conservan.') },
    onError: (error: Error) => setNotice(error.message),
  })
  const onFile = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) upload.mutate(file)
    event.target.value = ''
  }
  const autoMap = () => {
    const detected: Record<string, string> = {}
    for (const [field, names] of Object.entries(aliases)) {
      const header = headers.find((value) => names.includes(value.toLowerCase().trim()))
      if (header) detected[field] = header
    }
    setMapping(detected)
    setPreviewDirty(true)
  }
  const download = async (format: 'json' | 'csv' | 'xlsx') => {
    try {
      const response = await fetch(`/api/v1/exports/transactions?format=${format}`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      })
      if (!response.ok) throw new Error(`Error ${response.status}`)
      const url = URL.createObjectURL(await response.blob())
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `spiderfinance-movimientos.${format}`
      anchor.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (error) {
      setNotice(error instanceof Error ? error.message : 'No se pudo exportar')
    }
  }
  return <>
    <div className="page-heading"><div><span className="eyebrow">PORTABILIDAD</span><h2>Importar y exportar</h2></div></div>
    {notice && <div className="notice" role="status">{notice}</div>}
    <section className="panel"><div className="panel-header"><div><span className="eyebrow">NUEVA IMPORTACIÓN</span><h3>Seleccionar archivo</h3></div></div><p>Máximo 5 MB y 5000 filas. Se admiten CSV UTF-8 y XLSX.</p><input type="file" accept=".csv,.xlsx" aria-label="Archivo para importar" disabled={upload.isPending} onChange={onFile} /></section>
    {!!jobs.length && <section className="panel"><div className="panel-header"><div><span className="eyebrow">HISTORIAL</span><h3>Importaciones</h3></div></div><div className="table-scroll"><table><thead><tr><th>Archivo</th><th>Estado</th><th>Filas</th><th></th></tr></thead><tbody>{jobs.map((item) => <tr key={item.id}><td>{item.filename}</td><td>{item.status}</td><td>{item.total_rows}</td><td className="row-actions"><button onClick={() => selectJob(item)}>Abrir</button><button disabled={remove.isPending} onClick={() => { if (window.confirm('¿Eliminar el historial de este archivo? Los movimientos importados seguirán en la cuenta.')) remove.mutate(item.id) }}>Eliminar</button></td></tr>)}</tbody></table></div></section>}
    {job && <section className="panel"><div className="panel-header"><div><span className="eyebrow">MAPEO</span><h3>{job.filename}</h3></div></div>
      <div className="form-grid"><label>Hoja<select value={selectedSheet} onChange={(event) => { setSheet(event.target.value); setMapping({}); setPreviewDirty(true) }}>{job.sheet_names.map((name) => <option key={name} value={name}>{name}</option>)}</select></label><label>Cuenta predeterminada<select value={accountId} onChange={(event) => { setAccountId(event.target.value); setPreviewDirty(true) }}><option value="">Sin cuenta</option>{accounts.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.currency}</option>)}</select></label></div>
      <p>Si no hay columna de tipo, el signo del importe determina ingreso o gasto. El importe negativo se guarda como gasto positivo.</p>
      <label className="checkbox"><input type="checkbox" checked={positiveIsIncome} onChange={(event) => { setPositiveIsIncome(event.target.checked); setPreviewDirty(true) }} /> Importe positivo = ingreso</label>
      <div className="form-actions"><button className="button secondary" onClick={autoMap}>Detectar columnas comunes</button></div>
      <div className="form-grid">{fields.map((field) => <label key={field.id}>{field.label}<select value={mapping[field.id] || ''} onChange={(event) => { const next = { ...mapping }; if (event.target.value) next[field.id] = event.target.value; else delete next[field.id]; setMapping(next); setPreviewDirty(true) }}><option value="">Sin asignar</option>{headers.map((header) => <option key={header} value={header}>{header}</option>)}</select></label>)}</div>
      <div className="form-actions"><button className="button primary" disabled={job.status === 'CONFIRMED' || preview.isPending || !mapping.date || !mapping.concept || !mapping.amount} onClick={() => preview.mutate()}>Previsualizar</button>{job.status === 'PREVIEWED' && <button className="button secondary" disabled={previewDirty || confirm.isPending || job.rows.some((row) => row.status === 'UPLOADED')} onClick={() => { if (window.confirm('¿Importar las filas válidas? Las filas con error o duplicadas se omitirán.')) confirm.mutate() }}>Confirmar importación</button>}</div>
      <p>{job.total_rows} filas · {job.error_rows} con error · {job.skipped_rows} duplicadas u omitidas · {job.imported_rows} importadas</p>
      {!!job.rows.length && <div className="table-scroll"><table><thead><tr><th>Fila</th><th>Estado</th><th>Fecha</th><th>Concepto</th><th>Importe</th><th>Error</th></tr></thead><tbody>{job.rows.map((row) => <tr key={row.row_number}><td>{row.row_number}</td><td>{row.status}</td><td>{String(row.parsed?.date || row.raw[mapping.date] || '')}</td><td>{String(row.parsed?.concept || row.raw[mapping.concept] || '')}</td><td>{String(row.parsed?.amount || row.raw[mapping.amount] || '')}</td><td>{row.error || '—'}</td></tr>)}</tbody></table></div>}
      {job.total_rows > job.rows.length && <p className="table-note">Se muestran las primeras 100 filas; la confirmación procesa todas las filas válidas.</p>}
    </section>}
    <section className="panel"><div className="panel-header"><div><span className="eyebrow">DESCARGA</span><h3>Exportar movimientos</h3></div></div><p>Incluye movimientos confirmados y pendientes.</p><div className="form-actions"><button className="button secondary" onClick={() => download('csv')}>CSV</button><button className="button secondary" onClick={() => download('xlsx')}>XLSX</button><button className="button secondary" onClick={() => download('json')}>JSON</button></div></section>
  </>
}
