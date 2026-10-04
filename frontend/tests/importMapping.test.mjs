import assert from 'node:assert/strict'
import test from 'node:test'

import { detectColumns } from '../src/features/importMapping.ts'

test('detecta todas las columnas del formato exportado sin usar IDs locales', () => {
  const fields = [
    'date', 'type', 'concept', 'amount', 'source_account', 'destination_account',
    'category', 'status', 'notes', 'payment_method', 'is_fixed', 'is_necessary',
  ]
  assert.deepEqual(detectColumns([...fields, 'source_account_id', 'category_id']),
    Object.fromEntries(fields.map((field) => [field, field])))
})

test('detecta cabeceras en español con acentos y separadores distintos', () => {
  assert.deepEqual(detectColumns([
    'Fecha de operación', 'Descripción', 'Importe', 'Cuenta origen',
    'Cuenta destino', 'Categoría', 'Método de pago', 'Gasto fijo',
  ]), {
    date: 'Fecha de operación', concept: 'Descripción', amount: 'Importe',
    source_account: 'Cuenta origen', destination_account: 'Cuenta destino',
    category: 'Categoría', payment_method: 'Método de pago', is_fixed: 'Gasto fijo',
  })
})
