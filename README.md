# SpiderFinance

Gestor de finanzas personales autohospedado. Permite registrar usuarios, cuentas, categorías y movimientos, planificar ingresos y pagos, y consultar una previsión de saldos. El diseño del sistema completo está en [ARCHITECTURE.md](ARCHITECTURE.md).

## Estado de la aplicación

Las Fases 1, 2 y 3 están implementadas. El resumen muestra dinero y gastos reales registrados; la previsión se identifica como tal y usa ingresos, obligaciones y movimientos pendientes. Ahorro, inversiones, importación y simulación siguen pendientes. Las transferencias no cuentan como gasto. Los movimientos pendientes o fechados en el futuro no alteran el saldo actual.

## Requisitos

- Docker Engine y Docker Compose.
- Puertos locales: `8080` para la aplicación.
- No se necesita ningún servicio externo para utilizarla.

## Instalación con Docker

```bash
cp .env.example .env
```

Edita `.env` con una contraseña de PostgreSQL y una clave `SECRET_KEY` aleatoria y larga. Después:

```bash
docker compose up -d --build
```

Abre <http://localhost:8080>, crea tu usuario y añade una cuenta. PostgreSQL se guarda en el volumen `postgres_data`. El backend aplica migraciones Alembic al iniciar. La documentación de API está en <http://localhost:8080/docs>.

El frontend contiene vistas de resumen, movimientos, cuentas, planificación, previsión y configuración. Los formularios permiten registrar transferencias entre cuentas, ajustar saldos y crear subcategorías. En pantallas pequeñas la navegación pasa a la parte superior.

## Planificación y previsión

En «Planificación» puedes crear fuentes de ingreso mensuales, gastos recurrentes semanales o mensuales, gastos únicos y deudas con cuotas. Los vencimientos se muestran en un calendario de 90 días. Cuando registres el cobro o pago real en «Movimientos», vincúlalo al vencimiento: así se retira de los próximos pagos y el movimiento permanece como único efecto en el saldo. Los vínculos pueden corregirse sin borrar el movimiento.

«Previsión» proyecta los saldos durante 30, 90, 180 o 365 días. Incluye las obligaciones activas y los movimientos pendientes o futuros. Se calcula al consultar, sin crear movimientos. Los importes de monedas distintas se muestran por separado. El ciclo de nómina requiere una fuente de ingreso marcada como principal; «primer día laborable» considera lunes a viernes, sin festivos nacionales.

## Capturas

Datos de ejemplo, sin información personal real:

![Resumen financiero de la Fase 1](docs/screenshots/resumen.png)

![Vista de cuentas](docs/screenshots/cuentas.png)

![Inicio de sesión](docs/screenshots/inicio-sesion.png)

## Configuración

| Variable | Uso |
| --- | --- |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Base de datos local |
| `SECRET_KEY` | Firma de tokens JWT |
| `CORS_ORIGINS` | Orígenes permitidos, separados por coma |

Las preferencias de moneda principal, locale y zona horaria se editan por usuario en la aplicación. Cada cuenta conserva su propia moneda; las transferencias entre monedas distintas se rechazan hasta que exista una política de conversión.

## Actualización

El comando de actualización crea primero una copia de PostgreSQL en `backups/`, mantiene `.env` y el volumen de datos, y espera a que los servicios vuelvan a estar saludables. En Linux/macOS:

```bash
./scripts/update.sh local
```

En Windows PowerShell:

```powershell
.\scripts\update.ps1 -Mode local
```

`local` reconstruye los archivos ya presentes, sin reinstalar. En un clon Git, usa `source` para hacer `git pull --ff-only` antes de reconstruir:

```bash
./scripts/update.sh source
```

Para actualizar mediante imágenes publicadas en GHCR, añade `IMAGE_REPOSITORY=propietario/repositorio` a `.env` (en minúsculas). `APP_VERSION=latest` es opcional; puedes fijar `APP_VERSION=v1.2.3`. Arranca esa modalidad una vez con:

```bash
docker compose -f compose.yaml -f compose.release.yaml pull
docker compose -f compose.yaml -f compose.release.yaml up -d --no-build --wait
```

Después basta con `./scripts/update.sh release` (o `.\scripts\update.ps1 -Mode release` en Windows). El actualizador descarga las nuevas imágenes y recrea los contenedores; Alembic ejecuta las migraciones. Si GHCR es privado, inicia sesión con `docker login ghcr.io` antes de actualizar. `compose.release.yaml` requiere una versión reciente de Docker Compose con soporte para `!reset`.

## CI, etiquetas y releases

[GitHub Actions](.github/workflows/ci-release.yml) ejecuta pytest, las pruebas del versionado, la compilación de React y un arranque real con PostgreSQL antes de publicar. Tras cada push a la rama principal crea automáticamente una versión SemVer y, si todo pasa, publica las imágenes `ghcr.io/propietario/repositorio/backend:vX.Y.Z` y `.../frontend:vX.Y.Z` para amd64 y arm64. También actualiza `latest`, crea la etiqueta Git y un GitHub Release con `docker-images.json`, que contiene los digests inmutables. Un push manual de una etiqueta `vX.Y.Z` sigue el mismo control de pruebas y publica esa versión.

La primera versión es `v0.1.0`. Después, los commits `feat:` incrementan minor, `BREAKING CHANGE:` o `feat!:` incrementan major y los demás incrementan patch. Publica el proyecto en GitHub para activar el flujo; este directorio aún no tiene un remoto configurado. Las imágenes de GHCR pueden necesitar que se cambie su visibilidad a pública en GitHub Packages para permitir instalaciones anónimas.

## Copia y restauración

Para crear un archivo de copia SQL desde el directorio del proyecto:

```bash
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > spiderfinance-backup.sql
```

Para restaurarlo en una instalación nueva y vacía, arranca solo PostgreSQL y ejecuta:

```bash
docker compose up -d postgres
cat spiderfinance-backup.sql | docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"'
docker compose up -d
```

Guarda `.env` junto a tu copia en un lugar seguro; no se incluye en Git. La restauración de una copia sobre una base con datos existentes puede producir duplicados o conflictos.

Las copias creadas por el actualizador usan formato personalizado de `pg_dump` (`.dump`), adecuado para `pg_restore`. Guárdalas fuera del servidor periódicamente; `backups/` está excluido de Git.

## Desarrollo

Backend con Python 3.12 o superior:

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload
pytest
```

Por defecto usa SQLite local en desarrollo. Frontend con Node 22:

```bash
cd frontend
npm install
npm run dev
```

Vite atiende en <http://localhost:5173> y redirige `/api` a `localhost:8000`. La API publica OpenAPI en <http://localhost:8000/docs> durante desarrollo.

## Documentación

- [Arquitectura, modelo y roadmap](ARCHITECTURE.md)
- [Operación y respaldo](docs/operations.md)
