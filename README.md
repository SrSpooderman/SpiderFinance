# SpiderFinance

Aplicación de finanzas personales autoalojada.

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

## Publicar con cualquier gestor

La aplicación usa un solo origen: el frontend se sirve en `/` y la API en `/api/`. El navegador solicita rutas relativas como `/api/v1/auth/config`; el contenedor frontend reenvía `/api/` al backend. El destino se configura en tiempo de ejecución con `API_UPSTREAM` (por defecto `http://backend:8000`).

Para un proxy inverso instalado en el servidor, usa `compose.yaml` y dirige el dominio al puerto local `APP_PORT` (por defecto `127.0.0.1:8080`). Si tu gestor enruta directamente a contenedores, usa `compose.managed.yaml` y dirige el dominio completo a `frontend:80`. También puedes desplegar los servicios por separado o servir los archivos estáticos con tu propio proxy. Consulta [la guía de despliegue](docs/deployment.md) para las variables, rutas y comprobaciones de cada opción.

Cada usuario puede cambiar su contraseña en **Configuración**. Para crear usuarios o reiniciarles la contraseña, configura `SUPERUSER_EMAIL` y `SUPERUSER_PASSWORD` en `.env` y abre el backoffice local en <http://127.0.0.1:8081/admin>. El acceso público a `/admin` y `/api/v1/admin/` está bloqueado. [La guía del backoffice](docs/administration.md) explica el acceso desde otro equipo mediante SSH y el uso con gestores de contenedores.

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
