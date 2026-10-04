# SpiderFinance

Aplicación de finanzas personales para instalar en tu equipo.

## Instalar y ejecutar

Necesitas Docker Engine con Docker Compose. Desde la raíz del proyecto:

```bash
cp .env.example .env
```

En Windows PowerShell, usa `Copy-Item .env.example .env`. Edita `.env` y cambia al menos `POSTGRES_PASSWORD` y `SECRET_KEY` por valores propios. Después arranca la aplicación:

```bash
docker compose up -d --build
```

Abre <http://localhost:8080> y crea tu usuario. Si cambias `APP_PORT` en `.env`, usa ese puerto en la dirección. Para detener los contenedores:

```bash
docker compose down
```

Los datos permanecen en el volumen de PostgreSQL entre arranques.

## Desarrollar

Necesitas Python 3.12 o superior y Node.js 22. Ejecuta el backend y el frontend en terminales distintas. Cada bloque de comandos parte de la raíz del proyecto. El backend usa SQLite local por defecto, sin necesidad de arrancar Docker.

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload
```

En Windows PowerShell, sustituye `python3` por `py -3.12` y activa el entorno con `.venv\Scripts\Activate.ps1`. La API queda en <http://localhost:8000> y su documentación en <http://localhost:8000/docs>.

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

Abre <http://localhost:5173>. Vite redirige las peticiones a `/api` al backend local.

### Comprobaciones

```bash
cd backend
pytest
```

```bash
cd frontend
npm test
npm run build
```
