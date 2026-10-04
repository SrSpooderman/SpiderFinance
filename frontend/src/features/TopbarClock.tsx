import { useEffect, useState } from 'react'
import { Settings } from '../api/client'
import './TopbarClock.css'

export default function TopbarClock({ settings }: { settings?: Settings }) {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 15_000)
    return () => window.clearInterval(timer)
  }, [])
  const locale = settings?.locale || 'es-ES'
  const timeZone = settings?.timezone || 'Europe/Madrid'
  const time = new Intl.DateTimeFormat(locale, { timeZone, hour: '2-digit', minute: '2-digit', hour12: false }).format(now)
  const date = new Intl.DateTimeFormat(locale, { timeZone, weekday: 'short', day: 'numeric', month: 'long', year: 'numeric' }).format(now)
  return <div className="topbar-clock" aria-label={`${time}, ${date}`}>
    <span className="topbar-clock-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="8.5" stroke="currentColor" strokeWidth="1.8"/><path d="M12 6.8v5.5l3.6 2.2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg></span>
    <span className="topbar-clock-copy"><time dateTime={now.toISOString()}>{time}</time><small>{date}</small></span>
  </div>
}
