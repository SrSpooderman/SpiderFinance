# Arquitectura de SpiderFinance

## Alcance y criterio de entrega

La primera entrega implementa la Fase 1: instalación con Docker, registro e inicio de sesión, categorías y subcategorías, cuentas, movimientos, conciliación y una interfaz utilizable. Las fases siguientes se describen aquí para mantener un dominio coherente, pero las cifras futuras no se presentan como si ya existiera un motor de previsión.

## Arquitectura elegida

Monolito modular. FastAPI expone controladores delgados; los servicios de `application` aplican las reglas financieras; `domain` contiene enumeraciones y reglas puras; `infrastructure` implementa persistencia SQLAlchemy. PostgreSQL es la base principal. El frontend React consume una API versionada. Cada entidad financiera pertenece a un usuario y toda consulta se filtra por el identificador obtenido del token autenticado.

El dinero se guarda como `NUMERIC(18,2)` y se transmite como cadena decimal. Se evita `float` en el backend. La moneda es un código ISO en cada cuenta. En Fase 1 una transferencia exige la misma moneda en ambas cuentas; no se inventa un tipo de cambio. Los saldos se obtienen siempre de saldos iniciales y movimientos. Un movimiento tiene importe positivo y su tipo y cuentas determinan el signo. Una transferencia es un solo registro con dos efectos opuestos.

## Módulos y entidades

| Módulo | Entidades | Responsabilidad |
| --- | --- | --- |
| users/settings | User, UserSettings | Identidad, contraseña cifrada, moneda, locale, zona horaria |
| accounts | Account | Contenedores de dinero y patrimonio, saldo derivado |
| transactions | Transaction | Ingreso, gasto, transferencia, ajuste y conciliación |
| categories | Category | Categorías jerárquicas por usuario |
| recurring/income/scheduled | RecurringExpense, IncomeSource, ScheduledExpense | Obligaciones e ingresos esperados, separados de movimientos reales |
| salary_cycles | SalaryCycle (vista calculada) | Periodos delimitados por cobros principales |
| forecasting | ForecastEvent, ForecastResult (proyecciones) | Calendario de sucesos y disponibilidad proyectada |
| savings/goals | SavingsRule, Reservation, SavingsGoal, GoalContribution | Reglas, reserva virtual e historial de aportaciones |
| debts | Debt, DebtInstallment | Principal y cuotas pendientes |
| budgets | Budget | Límite por categoría, mes o ciclo |
| investments | InvestmentAccount, InvestmentContribution, InvestmentPosition | Aportaciones y valoración sin consumo ficticio |
| net_worth | NetWorthSnapshot | Activos menos pasivos e histórico |
| imports | ImportJob, ImportRow | Previsualización, errores y trazabilidad de importación |
| scenarios | Scenario | Cambios temporales para simulación sin escrituras reales |

Relaciones clave: `User` es padre de todos los datos privados. `Category.parent_id` apunta a otra categoría del mismo usuario. `Transaction` puede apuntar a cuenta origen y destino; ambas deben pertenecer al usuario. Una obligación pagada se vincula con un `Transaction`; una transferencia entre cuentas nunca se convierte en gasto. `GoalContribution` apunta a `SavingsGoal`, y una `Reservation` identifica dinero reservado en una cuenta sin moverlo. Una aportación a inversión puede vincular una transferencia real a una cuenta de inversión.

## Esquema de base de datos

La migración inicial crea:

| Tabla | Columnas principales e índices |
| --- | --- |
| users | id PK, email UNIQUE, password_hash, created_at, updated_at |
| user_settings | user_id PK/FK, currency, locale, timezone |
| accounts | id PK, user_id FK, name, type, institution, initial_balance NUMERIC, currency, active, notes, created_at, updated_at; índice user_id |
| categories | id PK, user_id FK, parent_id FK, name, created_at, updated_at; índice user_id |
| transactions | id PK, user_id FK, date, type, source_account_id FK, destination_account_id FK, category_id FK, concept, amount NUMERIC positivo, payment_method, is_fixed, is_necessary, notes, status, reconciliation, created_at, updated_at; índices (user_id,date), cuentas y categoría |

Las siguientes migraciones incorporarán entidades planificadas. `RecurringExpense`: frecuencia, día, vigencia, cuenta y estado. `ScheduledExpense`: fecha, estado y transaction_id opcional. `IncomeSource`: regla de cobro, cuenta y marca de ingreso principal. `Debt`: cuota, vigencia, principal opcional y saldo restante derivado de pagos. `SavingsRule`: porcentaje o cantidad. `Reservation`: cuenta, objetivo opcional, importe vigente y movimientos de reserva. `SavingsGoal` y `GoalContribution`: meta e historial. `Budget`: periodo, categoría e importe. `InvestmentContribution/Position`: importes y valoraciones manuales. `NetWorthSnapshot`: fecha y valores. `ImportJob/Row`: mapeo, estado, errores y claves de deduplicación. Todos incluyen `user_id` e índices por usuario. Los cambios importantes mantienen `created_at` y `updated_at`; se añadirá historial de revisiones para operaciones críticas.

## Casos de uso y API

Base `/api/v1`; OpenAPI en `/docs`.

| Caso de uso | Endpoint de Fase 1 |
| --- | --- |
| Registrar e iniciar sesión | `POST /auth/register`, `POST /auth/login`, `GET /auth/me` |
| Consultar y modificar preferencias | `GET/PATCH /settings` |
| Crear, listar, editar y desactivar cuentas | `GET/POST /accounts`, `GET/PATCH /accounts/{id}` |
| Ver saldo y desglose de cuenta | `GET /accounts/{id}/balance` |
| Crear y gestionar categorías/subcategorías | `GET/POST /categories`, `PATCH/DELETE /categories/{id}` |
| Registrar y filtrar movimientos | `GET/POST /transactions`, `GET/PATCH/DELETE /transactions/{id}` |
| Corregir descuadre de banco | `POST /accounts/{id}/reconcile` |
| Resumen de estado actual | `GET /dashboard` |
| Comprobar servicio | `GET /health` |

El listado de movimientos acepta `page`, `page_size`, fechas, cuenta, tipo, categoría, texto, importes, fijo y necesario. Un movimiento puede corregirse o borrarse; el saldo se recalcula. El ajuste de conciliación guarda la diferencia positiva o negativa mediante la dirección de cuenta y `reconciliation=true`, por lo que es auditable.

API planificada: `/recurring-expenses`, `/scheduled-expenses`, `/income-sources`, `/salary-cycles`, `/debts`, `/upcoming`, `/forecast`, `/savings-rules`, `/reservations`, `/goals`, `/budgets`, `/investments`, `/net-worth`, `/imports`, `/exports`, `/scenarios`. Cada módulo dispondrá de operaciones de lectura y escritura apropiadas y usará la misma identidad y validación de propiedad.

## Previsión y ciclos de nómina

El motor se implementará como servicio de aplicación puro: recibe fecha de corte, saldos reales por cuenta, reservas activas y sucesos futuros normalizados. Expande recurrencias dentro de un horizonte acotado, agrega gastos únicos, cuotas, ingresos, transferencias y ahorro/inversión programados, y elimina obligaciones pagadas vinculadas a movimientos reales. Ordena sucesos por fecha e identificador estable y produce saldos proyectados por día, compromisos hasta la próxima nómina, dinero reservado, disponible real y disponible hasta nómina. Nunca escribe movimientos durante una consulta. Un escenario introduce sucesos o cambios de regla en una copia temporal de los datos de entrada.

El siguiente cobro se calcula desde una `IncomeSource` principal y su regla (`LAST_DAY_OF_MONTH`, día fijo o primera jornada laboral). El día 31 se ajusta al último día válido, incluidos febrero y años bisiestos. Un ciclo empieza en una fecha de cobro y termina justo antes de la fecha del cobro siguiente; las fechas de los cobros son los límites, no un número fijo de días. La zona horaria del usuario determina el día actual, pero los sucesos financieros se almacenan como fechas civiles. Si no existe nómina configurada, la interfaz indicará que el ciclo no está disponible en vez de inventarlo.

## Flujo de ahorro

La regla de porcentaje se aplica al ingreso neto configurado; la de cantidad fija genera un compromiso separado. La asignación distribuye primero entre objetivos activos por prioridad hasta su importe restante y deja el excedente sin asignar o dirigido a inversión según configuración. Cada aportación registra fecha, importe y origen. Reservar dinero reduce el disponible, no el saldo de cuenta ni el patrimonio. Una transferencia física a ahorro se registra como transferencia y una aportación a inversión también conserva el patrimonio; la valoración posterior puede cambiarlo.

## Importación de Excel y CSV

El archivo real aún no se ha entregado. El importador aceptará CSV/XLSX en una zona temporal, detectará hojas y encabezados, ofrecerá mapeo editable de columnas y previsualización, validará fechas/importes/monedas/cuentas y mostrará errores por fila. La confirmación importará por lotes en una transacción con claves para evitar duplicados. Las filas ambiguas se omitirán hasta que el usuario las corrija. Se creará un adaptador para el Excel proporcionado cuando esté disponible, sin modificar el modelo para reproducir sus limitaciones. Exportación simétrica JSON, CSV y XLSX.

## Frontend

`frontend/src`: `api` para cliente HTTP y tipos, `features` para páginas y formularios, `components` para elementos reutilizables, `styles` para diseño responsive. TanStack Query gestiona caché e invalidación; React Hook Form y Zod validan formularios. La sesión se conserva en el navegador en esta fase. El dashboard de Fase 1 muestra saldos actuales y gastos reales, sin presentar una previsión pendiente como dato real.

## Fases

1. Fundamentos: entrega actual ejecutable.
2. Planificación: ingresos, recurrencias, gastos únicos, deudas y próximos pagos; pruebas de calendario.
3. Previsión: ciclos de nómina, motor puro, dashboard proyectado y calendario.
4. Ahorro: reglas, reservas, objetivos y aportaciones.
5. Presupuestos y estadísticas por mes/ciclo.
6. Inversiones, patrimonio y snapshots.
7. Importación/exportación CSV/XLSX y adaptador del Excel real.
8. Simulador y comparación de escenarios.

Cada fase añade migraciones, endpoints, interfaz y pruebas antes de considerarse terminada.

## Decisiones técnicas y riesgos

- JWT firmado con secreto de entorno; contraseñas Argon2. Cada instalación debe definir su secreto.
- Alembic aplica migraciones al iniciar el contenedor backend. PostgreSQL usa volumen persistente. SQLite solo se usa para desarrollo/pruebas.
- Respuestas de error HTTP estándar y validación Pydantic. Los importes negativos se rechazan.
- Las sumas entre monedas distintas se muestran por moneda; falta conversión hasta que exista política de divisas.
- Una cuenta con movimientos se desactiva, no se elimina. Los ajustes conservan su etiqueta y pueden retirarse al identificar el movimiento original.
- Riesgos: dobles contabilizaciones al vincular obligaciones, fechas de cobro en festivos, precisión de importaciones y divisas. Se cubrirán en las fases correspondientes.

## Decisiones pendientes

- Regla exacta de `FIRST_BUSINESS_DAY` (festivos por país o solo fines de semana).
- Política de tipos de cambio y fecha de valoración para patrimonio multimoneda.
- Enlace de pagos parciales a deudas y obligaciones.
- Alcance del historial de auditoría de cambios y retención de importaciones.
- Mapeo concreto del Excel del usuario cuando se proporcione.
