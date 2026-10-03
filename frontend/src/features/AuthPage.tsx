import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { api, setToken } from '../api/client'

const schema = z.object({ email: z.string().email('Introduce un correo válido'), password: z.string().min(1, 'Introduce una contraseña') })
type Values = z.infer<typeof schema>

export default function AuthPage({ onAuthenticated }: { onAuthenticated: (token: string) => void }) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [error, setError] = useState('')
  const [registrationEnabled, setRegistrationEnabled] = useState(false)
  useEffect(() => {
    let active = true
    api<{ registration_enabled: boolean }>('/auth/config')
      .then((config) => { if (active) setRegistrationEnabled(config.registration_enabled) })
      .catch(() => {})
    return () => { active = false }
  }, [])
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<Values>({ resolver: zodResolver(schema) })
  const submit = handleSubmit(async (values) => {
    setError('')
    if (mode === 'register' && values.password.length < 12) {
      setError('La contraseña debe tener al menos 12 caracteres')
      return
    }
    try {
      const result = await api<{ access_token: string }>(`/auth/${mode}`, { method: 'POST', body: JSON.stringify(values) })
      setToken(result.access_token)
      onAuthenticated(result.access_token)
    } catch (cause) { setError((cause as Error).message) }
  })
  return <div className="auth-layout"><div className="auth-intro"><div className="brand"><span className="brand-mark">S</span><span>Spider<span className="brand-accent">Finance</span></span></div>
    <div><span className="eyebrow">CONTROL CLARO DE TU DINERO</span><h1>Tu dinero,<br />con perspectiva.</h1><p>Organiza tus cuentas y movimientos en un espacio privado que controlas tú.</p></div>
    <small>Autohospedado · Tus datos, en tu servidor</small>
  </div><div className="auth-panel"><form className="auth-card" onSubmit={submit}>
    <span className="eyebrow">BIENVENIDO</span><h2>{mode === 'login' ? 'Inicia sesión' : 'Crea tu cuenta'}</h2><p>{mode === 'login' ? 'Accede a tu espacio financiero.' : 'Empieza a organizar tus finanzas.'}</p>
    <label>Correo electrónico<input autoComplete="email" type="email" {...register('email')} /></label>{errors.email && <small className="error">{errors.email.message}</small>}
    <label>Contraseña<input autoComplete={mode === 'login' ? 'current-password' : 'new-password'} type="password" {...register('password')} /></label>{errors.password && <small className="error">{errors.password.message}</small>}
    {error && <div className="alert error" role="alert">{error}</div>}
    <button className="button primary wide" disabled={isSubmitting}>{isSubmitting ? 'Un momento...' : mode === 'login' ? 'Entrar' : 'Crear cuenta'}</button>
    {(registrationEnabled || mode === 'register') && <div className="auth-switch">{mode === 'login' ? '¿Primera vez aquí?' : '¿Ya tienes cuenta?'} <button type="button" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}>{mode === 'login' ? 'Regístrate' : 'Inicia sesión'}</button></div>}
  </form></div></div>
}
