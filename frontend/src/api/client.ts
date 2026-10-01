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
export type IncomeSource = {
  id: number; name: string; amount: string; account_id: number; day_rule: 'FIXED_DAY' | 'LAST_DAY_OF_MONTH' | 'FIRST_BUSINESS_DAY'
  day_of_month: number | null; starts_on: string; ends_on: string | null; active: boolean; is_primary: boolean
}
export type RecurringExpense = {
  id: number; name: string; amount: string; account_id: number; category_id: number | null
  frequency: 'WEEKLY' | 'MONTHLY'; starts_on: string; ends_on: string | null; active: boolean
}
export type ScheduledExpense = {
  id: number; name: string; amount: string; account_id: number; category_id: number | null
  due_date: string; status: 'PLANNED' | 'PAID' | 'CANCELLED'; transaction_id: number | null
}
export type Debt = {
  id: number; name: string; principal: string; installment_amount: string; remaining: string
  account_id: number; starts_on: string; due_day: number; active: boolean
}
export type UpcomingEvent = {
  date: string; kind: 'INCOME' | 'RECURRING' | 'SCHEDULED' | 'DEBT'; source_id: number
  name: string; amount: string; currency: string; account_id: number; overdue: boolean
}
export type PlanningLink = {
  id: number; kind: UpcomingEvent['kind']; source_id: number; transaction_id: number; due_date: string | null
}
export type Forecast = {
  start: string; end: string
  salary_cycle: { available: boolean; source_id: number | null; current_start: string | null; current_end: string | null; next_payday: string | null }
  accounts: { id: number; name: string; currency: string; current: string; projected: string }[]
  events: { date: string; account_id: number; amount: string; label: string; key: string }[]
  days: { date: string; balances: Record<string, string>; totals_by_currency: Record<string, string> }[]
  reserved_by_currency: Record<string, string>
  available_now_by_currency: Record<string, string>
  minimum_until_payday_by_currency: Record<string, string> | null
}
export type SavingsGoal = {
  id: number; name: string; target_amount: string; funded: string; currency: string
  priority: number; due_date: string | null; active: boolean
}
export type Reservation = { id: number; account_id: number; goal_id: number | null; amount: string }
export type SavingsRule = {
  id: number; name: string; income_source_id: number; mode: 'PERCENT' | 'FIXED'; value: string; active: boolean
}
export type GoalContribution = {
  id: number; goal_id: number; account_id: number; date: string; amount: string; notes: string | null
}
export type SavingsRecommendation = {
  rules: { rule_id: number; source_id: number; currency: string; amount: string }[]
  allocations: { goal_id: number; currency: string; amount: string }[]
  unallocated_by_currency: Record<string, string>
}
export type Budget = {
  id: number; category_id: number | null; period: 'MONTH' | 'SALARY_CYCLE'
  currency: string; amount: string; active: boolean
}
export type BudgetStatus = Budget & {
  start: string | null; end: string | null; spent: string | null; remaining: string | null
}
export type Statistics = {
  period: Budget['period']; start: string; end: string
  income_by_currency: Record<string, string>; expense_by_currency: Record<string, string>
  expenses_by_category: { category_id: number | null; name: string; currency: string; amount: string }[]
  daily_expenses: { date: string; currency: string; amount: string }[]
}
export type InvestmentPosition = {
  id: number; account_id: number; name: string; symbol: string | null
  units: string; cost_basis: string; market_value: string; valued_on: string
}
export type InvestmentContribution = { id: number; account_id: number; transaction_id: number }
export type NetWorth = {
  date: string
  currencies: { currency: string; assets: string; liabilities: string; net_worth: string }[]
  accounts: { id: number; name: string; type: AccountType; currency: string; book_balance: string; position_value: string; uninvested_cash: string; asset_value: string }[]
}
export type NetWorthSnapshot = {
  id: number; date: string; currency: string; assets: string; liabilities: string; net_worth: string
}
export type ImportJob = {
  id: number; filename: string; sheet_names: string[]; selected_sheet: string | null
  headers: string[]; mapping: Record<string, string>; default_account_id: number | null
  positive_is_income: boolean; status: 'UPLOADED' | 'PREVIEWED' | 'CONFIRMED'
  total_rows: number; imported_rows: number; skipped_rows: number; error_rows: number
  rows: { row_number: number; raw: Record<string, string>; parsed: Record<string, unknown> | null; error: string | null; status: string }[]
}

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
