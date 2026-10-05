import { useEffect, useState, type FormEvent } from 'react'
import './AdminPage.css'

type AdminUser = { id: number; email: string; email_verified_at: string | null }
type InviteResult = { user: AdminUser; message: string }

const adminTokenKey = 'spiderfinance-admin-token'

class AdminRequestError extends Error {
  constructor(message: string, readonly status: number) { super(message) }
}

async function adminRequest<T>(path: string, options: RequestInit = {}, token = ''): Promise<T> {
  const response = await fetch(`/api/v1/admin${path}`, {
    ...options,
    cache: 'no-store',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new AdminRequestError(typeof body.detail === 'string' ? body.detail : `Error ${response.status}`, response.status)
  }
  return response.json() as Promise<T>
}

export default function AdminPage() {
  const [token, setToken] = useState(() => sessionStorage.getItem(adminTokenKey) || '')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [newEmail, setNewEmail] = useState('')
  const [users, setUsers] = useState<AdminUser[]>([])
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const handleActionError = (cause: unknown) => {
    if (cause instanceof AdminRequestError && cause.status === 401) {
      sessionStorage.removeItem(adminTokenKey)
      setToken('')
      setUsers([])
      setNotice('')
    }
    setError((cause as Error).message)
  }

  useEffect(() => {
    if (!token) return
    let active = true
    adminRequest<AdminUser[]>('/users', {}, token).then((items) => {
      if (active) setUsers(items)
    }).catch((cause: Error) => {
      if (!active) return
      sessionStorage.removeItem(adminTokenKey)
      setToken('')
      setError(cause.message)
    })
    return () => { active = false }
  }, [token])

  const login = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const result = await adminRequest<{ access_token: string }>('/login', {
        method: 'POST', body: JSON.stringify({ email, password }),
      })
      sessionStorage.setItem(adminTokenKey, result.access_token)
      setPassword('')
      setToken(result.access_token)
    } catch (cause) { handleActionError(cause) }
    finally { setBusy(false) }
  }

  const createUser = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const result = await adminRequest<InviteResult>('/users', {
        method: 'POST', body: JSON.stringify({ email: newEmail }),
      }, token)
      setNotice(`${result.message} a ${result.user.email}.`)
      setUsers((current) => [...current, result.user])
      setNewEmail('')
    } catch (cause) { handleActionError(cause) }
    finally { setBusy(false) }
  }

  const resetPassword = async (user: AdminUser) => {
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const result = await adminRequest<{ message: string }>(`/users/${user.id}/password-recovery`, { method: 'POST' }, token)
      setNotice(`${result.message} a ${user.email}.`)
    } catch (cause) { handleActionError(cause) }
    finally { setBusy(false) }
  }

  const logout = () => {
    sessionStorage.removeItem(adminTokenKey)
    setToken('')
    setUsers([])
    setNotice('')
  }

  if (!token) return <div className="admin-login"><form className="admin-login-card" onSubmit={login}>
    <span className="eyebrow">ACCESO LOCAL</span><h1>Administración</h1>
    <p>Introduce las credenciales del superusuario configurado en el servidor.</p>
    <label>Correo del superusuario<input type="email" autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
    <label>Contraseña<input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required /></label>
    {error && <div className="alert error" role="alert">{error}</div>}
    <button className="button primary wide" disabled={busy}>{busy ? 'Entrando...' : 'Entrar'}</button>
  </form></div>

  return <div className="admin-shell"><div className="admin-content">
    <header className="admin-header"><div><span className="eyebrow">ACCESO LOCAL</span><h1>Administración de usuarios</h1></div><button className="button secondary" type="button" onClick={logout}>Cerrar sesión</button></header>
    {error && <div className="alert error" role="alert">{error}</div>}
    {notice && <div className="notice" role="status">{notice}</div>}
    <section className="panel"><div className="panel-header"><h2>Crear usuario</h2></div>
      <form className="admin-create-form" onSubmit={createUser}><label>Correo electrónico<input type="email" autoComplete="off" value={newEmail} onChange={(event) => setNewEmail(event.target.value)} required /></label><button className="button primary" disabled={busy}>Crear y enviar invitación</button></form>
    </section>
    <section className="panel"><div className="panel-header"><h2>Usuarios</h2></div>
      <div className="table-scroll"><table><thead><tr><th>Correo</th><th>Estado</th><th>Acción</th></tr></thead><tbody>{users.map((user) => <tr key={user.id}><td>{user.email}</td><td>{user.email_verified_at ? 'Verificado' : 'Pendiente'}</td><td><button className="button secondary" type="button" disabled={busy} onClick={() => resetPassword(user)}>{user.email_verified_at ? 'Enviar recuperación' : 'Enviar invitación'}</button></td></tr>)}</tbody></table></div>
      {users.length === 0 && <p className="hint">Todavía no hay usuarios.</p>}
    </section>
  </div></div>
}
