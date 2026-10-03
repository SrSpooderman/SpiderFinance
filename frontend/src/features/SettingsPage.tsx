import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, Category, Settings } from '../api/client'

export default function SettingsPage() {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [parent, setParent] = useState('')
  const [notice, setNotice] = useState('')
  const { data: settings } = useQuery({ queryKey: ['settings'], queryFn: () => api<Settings>('/settings') })
  const { data: categories = [] } = useQuery({ queryKey: ['categories'], queryFn: () => api<Category[]>('/categories') })
  const create = useMutation({ mutationFn: () => api<Category>('/categories', { method: 'POST', body: JSON.stringify({ name, parent_id: parent ? Number(parent) : null }) }), onSuccess: () => { setName(''); setParent(''); queryClient.invalidateQueries({ queryKey: ['categories'] }); setNotice('Categoría creada.') }, onError: (error: Error) => setNotice(error.message) })
  const remove = useMutation({ mutationFn: (id: number) => api<void>(`/categories/${id}`, { method: 'DELETE' }), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['categories'] }); setNotice('Categoría eliminada.') }, onError: (error: Error) => setNotice(error.message) })
  const update = useMutation({ mutationFn: (changes: Partial<Settings>) => api<Settings>('/settings', { method: 'PATCH', body: JSON.stringify(changes) }), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['settings'] }); setNotice('Preferencias guardadas.') }, onError: (error: Error) => setNotice(error.message) })
  return <><div className="page-heading"><div><span className="eyebrow">PERSONALIZACIÓN</span><h2>Configuración</h2></div></div>
    {notice && <div className="notice" role="status">{notice}</div>}
    <div className="settings-grid"><section className="panel"><div className="panel-header"><div><span className="eyebrow">PREFERENCIAS</span><h3>Tu espacio</h3></div></div>
      {settings && <div className="settings-fields"><label>Moneda principal<input key={settings.currency} defaultValue={settings.currency} maxLength={3} onBlur={(event) => { const value = event.target.value.toUpperCase(); if (value !== settings.currency) update.mutate({ currency: value }) }} /></label><label>Idioma y formato<input key={settings.locale} defaultValue={settings.locale} onBlur={(event) => { if (event.target.value !== settings.locale) update.mutate({ locale: event.target.value }) }} /></label><label>Zona horaria<input key={settings.timezone} defaultValue={settings.timezone} onBlur={(event) => { if (event.target.value !== settings.timezone) update.mutate({ timezone: event.target.value }) }} /></label><p className="hint">Los cambios se guardan al salir del campo. Las cuentas conservan su propia moneda.</p></div>}
    </section><section className="panel"><div className="panel-header"><div><span className="eyebrow">ORGANIZACIÓN</span><h3>Categorías</h3></div></div>
      <form className="category-form" onSubmit={(event) => { event.preventDefault(); if (name.trim()) create.mutate() }}><input aria-label="Nombre de categoría" placeholder="Nueva categoría" value={name} onChange={(event) => setName(event.target.value)} /><select aria-label="Categoría principal" value={parent} onChange={(event) => setParent(event.target.value)}><option value="">Categoría principal</option>{categories.filter((item) => !item.parent_id).map((item) => <option key={item.id} value={item.id}>Bajo {item.name}</option>)}</select><button className="button primary" disabled={create.isPending}>Añadir</button></form>
      <div className="category-list">{categories.map((item) => <div key={item.id}><span>{item.parent_id && '↳ '}{item.name}</span><button onClick={() => { if (window.confirm(`¿Eliminar ${item.name}?`)) remove.mutate(item.id) }}>Eliminar</button></div>)}</div><p className="hint">Las categorías utilizadas en movimientos se conservan para mantener el historial.</p>
    </section></div>
  </>
}
