export type AccountType = 'CHECKING' | 'SAVINGS' | 'CASH' | 'INVESTMENT' | 'CARD' | 'OTHER'
export type TransactionType = 'INCOME' | 'EXPENSE' | 'TRANSFER' | 'ADJUSTMENT'
export type Account = {
  id: number; name: string; type: AccountType; institution: string | null
  initial_balance: string; balance: string; currency: string; active: boolean; notes: string | null
}
export type Category = { id: number; name: string; parent_id: number | null }
export type Movement = {
  id: number; date: string; type: TransactionType; source_account_id: number | null
  destination_account_id: number | null; category_id: number | null; concept: string
  amount: string; payment_method: string | null; is_fixed: boolean; is_necessary: boolean
  notes: string | null; status: 'CLEARED' | 'PENDING'; reconciliation: boolean
}
export type MovementPage = { items: Movement[]; total: number; page: number; page_size: number }
export type Dashboard = {
  balances: { currency: string; total: string; savings: string }[]
  accounts: { id: number; name: string; type: AccountType; currency: string; balance: string }[]
  spending_by_category: { name: string; amount: string; currency: string }[]
  recent_transactions: { id: number; date: string; type: TransactionType; concept: string; amount: string; currency: string }[]
}
export type Settings = { currency: string; locale: string; timezone: string }

export const money = (value: string | number, currency = 'EUR', locale = 'es-ES') =>
  new Intl.NumberFormat(locale, { style: 'currency', currency }).format(Number(value))

export const todayInTimezone = (timezone = 'Europe/Madrid') =>
  new Intl.DateTimeFormat('en-CA', { timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date())

const tokenKey = 'spiderfinance-token'
export const getToken = () => localStorage.getItem(tokenKey)
export const setToken = (token: string) => localStorage.setItem(tokenKey, token)
export const clearToken = () => localStorage.removeItem(tokenKey)

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
      ...options.headers,
    },
  })
  if (response.status === 401 && !path.startsWith('/auth/')) {
    clearToken()
    window.location.reload()
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(typeof body.detail === 'string' ? body.detail : `Error ${response.status}`)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const json = (data: unknown): RequestInit => ({
  method: 'POST', body: JSON.stringify(data),
})
