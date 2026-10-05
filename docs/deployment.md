# Despliegue

SpiderFinance se publica bajo un solo dominio HTTPS. El frontend ocupa `/` y llama a `/api/v1/...` en ese mismo dominio. El backend recibe esas rutas con el prefijo `/api/v1` intacto. Un dominio como `https://finanzas.ejemplo.com` sirve ambas partes; no hace falta un subdominio adicional para la API.

## Docker Compose con proxy en el servidor

Usa `compose.yaml`. Copia `.env.example` a `.env`, cambia `POSTGRES_PASSWORD` y `SECRET_KEY`, y ejecuta `docker compose up -d --build`. Por defecto, solo el frontend publica `127.0.0.1:8080`; dirige tu dominio HTTPS a ese puerto con el proxy que prefieras. Si el proxy está en otro equipo, establece `APP_BIND_ADDRESS` en una dirección alcanzable desde él y protege ese acceso según tu red. PostgreSQL y el backend no necesitan puertos públicos.

## Gestor que enruta a contenedores

Usa `compose.managed.yaml` como archivo Compose del despliegue. Define `POSTGRES_PASSWORD` y `SECRET_KEY` como variables de entorno del proyecto. Asigna el dominio completo al servicio `frontend`, puerto interno `80`; deja `backend`, `postgres` y `admin` sin rutas públicas. El proxy del gestor debe tener acceso de red al contenedor frontend. El único puerto de host es el del backoffice, ligado a `127.0.0.1:8081` por defecto. Los servicios usan la red privada de Compose y PostgreSQL guarda los datos en el volumen `postgres_data`.

## Servicios o alojamiento estático por separado

Puedes construir `frontend/Dockerfile` y `backend/Dockerfile` por separado. El backend escucha en `8000` y necesita `DATABASE_URL` (PostgreSQL), `SECRET_KEY` y, si procede, `REGISTRATION_ENABLED`. El contenedor frontend escucha en `80`; define en él `API_UPSTREAM` con la dirección HTTP interna alcanzable del backend, por ejemplo `http://backend:8000`. Es una variable de **ejecución**, por lo que no requiere recompilar el frontend. No añadas `/api` ni una barra final al valor.

Si sirves directamente los archivos compilados de `frontend/dist` sin su contenedor Nginx, genéralos con `cd frontend && npm ci && npm run build`. Configura tu propio proxy para enviar `/api/` al backend y conservar la ruta completa. El frontend seguirá solicitando `/api/v1/...` del mismo origen. Dirige el resto de rutas al frontend y aplica la regla de fallback a `index.html` para la navegación de la SPA.

## Rutas y comprobaciones

| Ruta pública | Destino |
| --- | --- |
| `/` y rutas de la interfaz | Frontend |
| `/api/` | Backend; responde `{"status":"ok"}` |
| `/api/v1/...` | Backend; conserva el prefijo completo |

Cuando uses el contenedor frontend, configura en tu proxy o gestor **una sola ruta para el dominio completo** hacia el frontend. Su Nginx ya separa `/api/`. Si enrutas `/api` directamente al backend, asegúrate de que tu proxy no quite el prefijo. El archivo `compose.yaml` publica el frontend en el host; `compose.managed.yaml` permite que el gestor llegue al puerto interno sin publicar un puerto del servidor.

Comprueba `https://TU_DOMINIO/`, `https://TU_DOMINIO/api/` y `https://TU_DOMINIO/api/v1/auth/config`. El endpoint `/health` del backend comprueba internamente la conexión con PostgreSQL. `CORS_ORIGINS` solo es necesario para clientes alojados en otro origen; el frontend integrado no lo necesita. Si administras las altas desde el backoffice, establece `REGISTRATION_ENABLED=false` antes de publicar el dominio. Si ya tienes datos, migra la base antes de reemplazar la instalación: un volumen nuevo empieza vacío.

El backoffice usa un puerto local separado y credenciales `SUPERUSER_EMAIL`/`SUPERUSER_PASSWORD`; consulta [Administración local](administration.md). No asignes un dominio público al servicio `admin`.

## SMTP saliente

El backend puede conectarse a un servidor SMTP mediante `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY` (`starttls`, `ssl` o `none`) y `SMTP_FROM`. El envío solo se permite con `SMTP_ENABLED=true`; el valor predeterminado es `false`. Si el servidor exige autenticación, configura juntos `SMTP_USERNAME` y `SMTP_PASSWORD`; la autenticación sin TLS está deshabilitada. `SMTP_TIMEOUT_SECONDS` controla el tiempo máximo de conexión. En Compose las variables se pasan al backend, sin publicar puertos SMTP. El transporte está preparado, pero todavía no hay correos automáticos ni cambios en los flujos de contraseñas.

Para comprobar la conexión desde el contenedor, ejecuta `docker compose exec backend python -m app.modules.notifications --to tu-correo@example.com`. El comando envía un único mensaje de prueba al destinatario indicado cuando SMTP está activado. Las credenciales pertenecen al entorno de despliegue; si más adelante se añade un interruptor en el backoffice, la base de datos solo debería guardar el estado de activación, sin claves ni contraseñas SMTP.
