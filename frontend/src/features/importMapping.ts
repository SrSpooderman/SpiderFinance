const aliases: Record<string, string[]> = {
  date: ['fecha', 'date', 'fecha operacion', 'fecha de operacion'],
  concept: ['concepto', 'description', 'descripcion', 'detalle', 'concept'],
  amount: ['importe', 'amount', 'cantidad', 'monto'],
  type: ['tipo', 'type'],
  source_account: ['source_account', 'cuenta origen', 'cuenta de origen'],
  destination_account: ['destination_account', 'cuenta destino', 'cuenta de destino'],
  category: ['category', 'categoria', 'ruta categoria'],
  status: ['status', 'estado'], notes: ['notes', 'notas', 'observaciones'],
  payment_method: ['payment_method', 'metodo de pago', 'forma de pago'],
  is_fixed: ['is_fixed', 'gasto fijo', 'fijo'],
  is_necessary: ['is_necessary', 'necesario', 'gasto necesario'],
  external_id: ['id externo', 'external_id', 'reference', 'referencia'],
}

const normalizeHeader = (value: string) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '')
  .toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim()

export const detectColumns = (headers: string[]) => {
  const detected: Record<string, string> = {}
  const used = new Set<string>()
  for (const [field, names] of Object.entries(aliases)) {
    const normalizedNames = names.map(normalizeHeader)
    const header = headers.find((value) => !used.has(value) && normalizedNames.includes(normalizeHeader(value)))
    if (header) { detected[field] = header; used.add(header) }
  }
  return detected
}
