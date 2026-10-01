# Arquitectura de SpiderFinance

## Alcance y criterio de entrega

La entrega actual implementa las Fases 1 a 5: instalación con Docker, registro e inicio de sesión, categorías y subcategorías, cuentas, movimientos, conciliación, planificación de ingresos y obligaciones, ciclos de nómina, previsión diaria, reservas virtuales con objetivos de ahorro, presupuestos y estadísticas. La previsión se distingue de los saldos reales.

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

La migración 0002 incorpora `IncomeSource`, `RecurringExpense`, `ScheduledExpense`, `Debt` y los vínculos de cobros o pagos con movimientos reales. La migración 0003 incorpora `SavingsRule`, `Reservation`, `SavingsGoal` y `GoalContribution`. La migración 0004 incorpora `Budget`. Las siguientes migraciones incorporarán `InvestmentContribution/Position`, `NetWorthSnapshot` e importaciones. Todas las entidades privadas incluyen `user_id`; los cambios importantes mantienen `created_at` y `updated_at`.

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

API implementada tras la Fase 1: `/recurring-expenses`, `/scheduled-expenses`, `/income-sources`, `/salary-cycles`, `/debts`, `/upcoming`, `/forecast`, `/planning-links`, `/savings-rules`, `/savings-recommendations`, `/reservations`, `/goals`, `/goal-contributions`, `/budgets`, `/budget-status` y `/statistics`. API pendiente: `/investments`, `/net-worth`, `/imports`, `/exports`, `/scenarios`.

## Previsión y ciclos de nómina

El motor puro recibe fecha de corte, saldos reales por cuenta y sucesos futuros normalizados. Expande recurrencias dentro de un horizonte acotado, agrega gastos únicos, cuotas, ingresos y movimientos pendientes o futuros, y elimina obligaciones pagadas vinculadas a movimientos reales. Ordena sucesos por fecha e identificador estable y produce saldos proyectados por día y mínimo por moneda antes de la próxima nómina. Las reservas virtuales se descuentan del disponible, sin modificar saldos. Nunca escribe movimientos durante una consulta. La programación automática de ahorro/inversión y los escenarios se incorporarán en sus fases correspondientes.

El siguiente cobro se calcula desde una `IncomeSource` principal y su regla (`LAST_DAY_OF_MONTH`, día fijo o primera jornada laboral). El día 31 se ajusta al último día válido, incluidos febrero y años bisiestos. Un ciclo empieza en una fecha de cobro y termina justo antes de la fecha del cobro siguiente; las fechas de los cobros son los límites, no un número fijo de días. La zona horaria del usuario determina el día actual, pero los sucesos financieros se almacenan como fechas civiles. Si no existe nómina configurada, la interfaz indicará que el ciclo no está disponible en vez de inventarlo.

## Flujo de ahorro

La regla de porcentaje se aplica al importe configurado en la fuente de ingreso; la de cantidad fija propone un importe separado. La propuesta distribuye primero entre objetivos activos por prioridad hasta su importe restante y deja el excedente sin asignar. Cada aportación registra fecha, importe y cuenta; una liberación registra un importe negativo. Reservar dinero reduce el disponible, no el saldo de cuenta ni el patrimonio. Una transferencia física a ahorro se registra como transferencia. La inversión y su valoración se incorporarán en la Fase 6.

## Importación de Excel y CSV

El archivo real aún no se ha entregado. El importador aceptará CSV/XLSX en una zona temporal, detectará hojas y encabezados, ofrecerá mapeo editable de columnas y previsualización, validará fechas/importes/monedas/cuentas y mostrará errores por fila. La confirmación importará por lotes en una transacción con claves para evitar duplicados. Las filas ambiguas se omitirán hasta que el usuario las corrija. Se creará un adaptador para el Excel proporcionado cuando esté disponible, sin modificar el modelo para reproducir sus limitaciones. Exportación simétrica JSON, CSV y XLSX.

## Frontend

`frontend/src`: `api` para cliente HTTP y tipos, `features` para páginas y formularios, `styles` para diseño responsive. TanStack Query gestiona caché e invalidación; React Hook Form y Zod validan los formularios de movimientos y cuentas. La sesión se conserva en el navegador en esta fase. El dashboard distingue saldos actuales de previsiones.

## Fases

1. Fundamentos: entrega actual ejecutable.
2. Planificación: ingresos, recurrencias, gastos únicos, deudas y próximos pagos; pruebas de calendario. Implementada.
3. Previsión: ciclos de nómina, motor puro, dashboard proyectado y calendario. Implementada.
4. Ahorro: reglas, reservas, objetivos y aportaciones. Implementada.
5. Presupuestos y estadísticas por mes/ciclo. Implementada.
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

- Ampliar `FIRST_BUSINESS_DAY` con festivos por país; actualmente solo excluye fines de semana.
- Política de tipos de cambio y fecha de valoración para patrimonio multimoneda.
- Enlace de pagos parciales a deudas y obligaciones.
- Alcance del historial de auditoría de cambios y retención de importaciones.
- Mapeo concreto del Excel del usuario cuando se proporcione.
