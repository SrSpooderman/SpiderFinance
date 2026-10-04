import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, Category, ProfilePhoto, setToken, Settings, Theme } from '../api/client'
import './SettingsPage.css'

const palettes: { id: Theme; label: string; description: string }[] = [
  { id: 'light-teal', label: 'Marea', description: 'Clara · verde' },
  { id: 'light-red', label: 'Coral', description: 'Clara · rojo' },
  { id: 'dark-red', label: 'Carmesí', description: 'Oscura · rojo' },
  { id: 'dark-purple', label: 'Amatista', description: 'Oscura · morado' },
]

export default function SettingsPage() {
  const queryClient = useQueryClient()
  const photoInput = useRef<HTMLInputElement>(null)
  const [name, setName] = useState('')
  const [parent, setParent] = useState('')
  const [notice, setNotice] = useState('')
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passwordError, setPasswordError] = useState('')
  const [changingPassword, setChangingPassword] = useState(false)
  const { data: settings } = useQuery({ queryKey: ['settings'], queryFn: () => api<Settings>('/settings') })
  const { data: me } = useQuery({ queryKey: ['me'], queryFn: () => api<{ id: number; email: string }>('/auth/me') })
  const { data: profilePhoto } = useQuery({ queryKey: ['profile-photo'], queryFn: () => api<ProfilePhoto>('/auth/profile-photo') })
  const { data: categories = [] } = useQuery({ queryKey: ['categories'], queryFn: () => api<Category[]>('/categories') })
  const create = useMutation({ mutationFn: () => api<Category>('/categories', { method: 'POST', body: JSON.stringify({ name, parent_id: parent ? Number(parent) : null }) }), onSuccess: () => { setName(''); setParent(''); queryClient.invalidateQueries({ queryKey: ['categories'] }); setNotice('Categoría creada.') }, onError: (error: Error) => setNotice(error.message) })
  const remove = useMutation({ mutationFn: (id: number) => api<void>(`/categories/${id}`, { method: 'DELETE' }), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['categories'] }); setNotice('Categoría eliminada.') }, onError: (error: Error) => setNotice(error.message) })
  const update = useMutation({ mutationFn: (changes: Partial<Settings>) => api<Settings>('/settings', { method: 'PATCH', body: JSON.stringify(changes) }), onSuccess: (saved) => { queryClient.setQueryData(['settings'], saved); setNotice('Preferencias guardadas.') }, onError: (error: Error) => { document.documentElement.dataset.theme = settings?.theme || 'light-teal'; setNotice(error.message) } })
  const uploadPhoto = useMutation({
    mutationFn: (photo: File) => { const body = new FormData(); body.append('photo', photo); return api<ProfilePhoto>('/auth/profile-photo', { method: 'PUT', body }) },
    onSuccess: (saved) => { queryClient.setQueryData(['profile-photo'], saved); setNotice('Foto de perfil guardada.') },
    onError: (error: Error) => setNotice(error.message),
  })
  const removePhoto = useMutation({
    mutationFn: () => api<void>('/auth/profile-photo', { method: 'DELETE' }),
    onSuccess: () => { queryClient.setQueryData(['profile-photo'], { data_url: null }); setNotice('Foto de perfil eliminada.') },
    onError: (error: Error) => setNotice(error.message),
  })
  const changePassword = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setPasswordError('')
    if (newPassword.length < 12) { setPasswordError('La nueva contraseña debe tener al menos 12 caracteres.'); return }
    if (newPassword !== confirmPassword) { setPasswordError('Las contraseñas nuevas no coinciden.'); return }
    setChangingPassword(true)
    try {
      const result = await api<{ access_token: string }>('/auth/change-password', {
        method: 'POST', body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      })
      setToken(result.access_token)
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      setNotice('Contraseña actualizada. Se han cerrado las demás sesiones.')
    } catch (error) { setPasswordError((error as Error).message) }
    finally { setChangingPassword(false) }
  }
  return <><div className="page-heading"><div><span className="eyebrow">PERSONALIZACIÓN</span><h2>Configuración</h2></div></div>
    {notice && <div className="notice" role="status">{notice}</div>}
    <div className="settings-grid"><section className="panel"><div className="panel-header"><div><span className="eyebrow">PREFERENCIAS</span><h3>Tu espacio</h3></div></div>
      {settings && <div className="settings-fields">
        <div className="profile-photo-settings">
          <div className="avatar profile-photo-preview">{profilePhoto?.data_url ? <img src={profilePhoto.data_url} alt="Tu foto de perfil" /> : me?.email?.[0]?.toUpperCase() || 'U'}</div>
          <div className="profile-photo-details"><strong>Foto de perfil</strong><small>PNG, JPEG o WebP · máximo 2 MB</small>
            <div className="profile-photo-actions">
              <input ref={photoInput} type="file" accept="image/png,image/jpeg,image/webp" className="profile-photo-input" aria-label="Seleccionar foto de perfil" onChange={(event) => {
                const file = event.target.files?.[0]
                event.target.value = ''
                if (!file) return
                if (file.size > 2 * 1024 * 1024) { setNotice('La foto no puede superar los 2 MB.'); return }
                if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) { setNotice('Usa una imagen PNG, JPEG o WebP.'); return }
                uploadPhoto.mutate(file)
              }} />
              <button className="button secondary" disabled={uploadPhoto.isPending || removePhoto.isPending} onClick={() => photoInput.current?.click()}>{profilePhoto?.data_url ? 'Cambiar foto' : 'Subir foto'}</button>
              {profilePhoto?.data_url && <button className="button secondary" disabled={uploadPhoto.isPending || removePhoto.isPending} onClick={() => removePhoto.mutate()}>Quitar</button>}
            </div>
          </div>
        </div>
        <div><span className="settings-field-title">Paleta de colores</span><div className="palette-grid" role="group" aria-label="Paleta de colores">{palettes.map((palette) => <button key={palette.id} type="button" className={`palette-option ${settings.theme === palette.id ? 'selected' : ''}`} aria-pressed={settings.theme === palette.id} disabled={update.isPending} onClick={() => { document.documentElement.dataset.theme = palette.id; update.mutate({ theme: palette.id }) }}><span className={`palette-preview ${palette.id}`} aria-hidden="true"><i /><i /><i /></span><strong>{palette.label}</strong><small>{palette.description}</small></button>)}</div></div>
        <label>Moneda principal<input key={settings.currency} defaultValue={settings.currency} maxLength={3} onBlur={(event) => { const value = event.target.value.toUpperCase(); if (value !== settings.currency) update.mutate({ currency: value }) }} /></label>
        <label>Idioma y formato<input key={settings.locale} defaultValue={settings.locale} onBlur={(event) => { if (event.target.value !== settings.locale) update.mutate({ locale: event.target.value }) }} /></label>
        <label>Zona horaria<input key={settings.timezone} defaultValue={settings.timezone} onBlur={(event) => { if (event.target.value !== settings.timezone) update.mutate({ timezone: event.target.value }) }} /></label>
        <p className="hint">Los cambios se guardan al salir del campo. Las cuentas conservan su propia moneda.</p>
      </div>}
    </section><section className="panel"><div className="panel-header"><div><span className="eyebrow">ORGANIZACIÓN</span><h3>Categorías</h3></div></div>
      <form className="category-form" onSubmit={(event) => { event.preventDefault(); if (name.trim()) create.mutate() }}><input aria-label="Nombre de categoría" placeholder="Nueva categoría" value={name} onChange={(event) => setName(event.target.value)} /><select aria-label="Categoría principal" value={parent} onChange={(event) => setParent(event.target.value)}><option value="">Categoría principal</option>{categories.filter((item) => !item.parent_id).map((item) => <option key={item.id} value={item.id}>Bajo {item.name}</option>)}</select><button className="button primary" disabled={create.isPending}>Añadir</button></form>
      <div className="category-list">{categories.map((item) => <div key={item.id}><span>{item.parent_id && '↳ '}{item.name}</span><button onClick={() => { if (window.confirm(`¿Eliminar ${item.name}?`)) remove.mutate(item.id) }}>Eliminar</button></div>)}</div><p className="hint">Las categorías utilizadas en movimientos se conservan para mantener el historial.</p>
    </section><section className="panel security-panel"><div className="panel-header"><div><span className="eyebrow">SEGURIDAD</span><h3>Cambiar contraseña</h3></div></div>
      <form className="security-form" onSubmit={changePassword}>
        <label>Contraseña actual<input type="password" autoComplete="current-password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} required /></label>
        <label>Nueva contraseña<input type="password" autoComplete="new-password" minLength={12} maxLength={128} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} required /></label>
        <label>Repetir nueva contraseña<input type="password" autoComplete="new-password" minLength={12} maxLength={128} value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} required /></label>
        {passwordError && <p className="alert error" role="alert">{passwordError}</p>}
        <button className="button primary" disabled={changingPassword}>{changingPassword ? 'Guardando...' : 'Cambiar contraseña'}</button>
      </form><p className="hint">Mínimo 12 caracteres. Al cambiarla, las otras sesiones dejarán de funcionar.</p>
    </section></div>
  </>
}
