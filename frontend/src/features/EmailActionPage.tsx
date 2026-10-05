import { useEffect, useRef, useState, type FormEvent } from 'react'
import { api } from '../api/client'
import RepositoryCredit from './RepositoryCredit'

const params = new URLSearchParams(window.location.hash.slice(1))
const initialToken = params.get('token') || ''
const initialKind = params.get('kind') || ''
if (window.location.hash || window.location.search) window.history.replaceState(null, '', window.location.pathname)

export default function EmailActionPage() {
  const verify = window.location.pathname === '/verify-email'
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [busy, setBusy] = useState(false)
  const verificationStarted = useRef(false)

  useEffect(() => {
    if (!verify) return
    if (verificationStarted.current) return
    verificationStarted.current = true
    if (!initialToken) { setError('El enlace no es válido.'); return }
    api<{ message: string }>('/auth/email-verification/complete', { method: 'POST', body: JSON.stringify({ token: initialToken }) })
      .then((result) => setMessage(result.message))
      .catch((cause: Error) => setError(cause.message))
  }, [verify])

  const complete = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    if (password !== confirmation) { setError('Las contraseñas no coinciden.'); return }
    if (password.length < 12) { setError('Usa al menos 12 caracteres.'); return }
    setBusy(true)
    try {
      const result = await api<{ message: string }>('/auth/password-recovery/complete', {
        method: 'POST', body: JSON.stringify({ token: initialToken, kind: initialKind, new_password: password }),
      })
      setMessage(result.message)
      setPassword('')
      setConfirmation('')
    } catch (cause) { setError((cause as Error).message) }
    finally { setBusy(false) }
  }

  return <div className="admin-login"><div className="admin-login-card">
    <span className="eyebrow">SPIDERFINANCE</span><h1>{verify ? 'Verificar correo' : 'Elegir contraseña'}</h1>
    {verify && !message && !error && <p>Comprobando el enlace...</p>}
    {!verify && !initialToken && <p className="alert error">El enlace no es válido.</p>}
    {!verify && initialToken && !message && <form className="security-form" onSubmit={complete}>
      <label>Nueva contraseña<input type="password" autoComplete="new-password" minLength={12} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} required /></label>
      <label>Repetir contraseña<input type="password" autoComplete="new-password" minLength={12} maxLength={128} value={confirmation} onChange={(event) => setConfirmation(event.target.value)} required /></label>
      <button className="button primary" disabled={busy}>{busy ? 'Guardando...' : 'Guardar contraseña'}</button>
    </form>}
    {message && <div className="notice" role="status">{message}</div>}
    {error && <div className="alert error" role="alert">{error}</div>}
    <a href="/">Ir al inicio de sesión</a>
    <RepositoryCredit />
  </div></div>
}
