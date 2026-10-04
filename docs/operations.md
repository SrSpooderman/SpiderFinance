# Operación

## Comprobación de salud

`docker compose ps` muestra el estado de los tres servicios. El backend verifica su conexión a PostgreSQL en `/health`; el frontend tiene un healthcheck HTTP.

## Copias de seguridad

Usa `pg_dump` según el README. Comprueba periódicamente que el archivo no esté vacío y ensaya la restauración en un volumen nuevo. La aplicación no guarda ficheros de usuario en Fase 1; los datos se encuentran en PostgreSQL.

Los actualizadores `scripts/update.sh` y `scripts/update.ps1` realizan un `pg_dump -Fc` antes de cambiar imágenes o código. Copian el archivo a `backups/` y se detienen si la copia falla. Para restaurar uno de esos archivos, detén `frontend` y `backend`, copia el `.dump` al contenedor `postgres` y usa `pg_restore --clean --if-exists`; después vuelve a arrancar con la versión de aplicación compatible con esa base. Prueba este procedimiento en una instalación separada antes de necesitarlo.

## Migraciones

El comando de inicio del backend ejecuta `alembic upgrade head` antes de servir tráfico. Si falla, consulta `docker compose logs backend` y conserva la copia de la base antes de resolverlo. Las migraciones están en `backend/migrations/versions`.

## Publicaciones

El workflow `.github/workflows/ci-release.yml` publica dos imágenes versionadas en GHCR y adjunta sus digests al GitHub Release. Las etiquetas automáticas se crean después de construir y subir ambas imágenes; las etiquetas manuales solo se publican si pasan las mismas pruebas. En una instalación basada en imágenes, `APP_VERSION` puede fijar una versión concreta para evitar actualizaciones inesperadas de `latest`.

## Seguridad y acceso público

Genera claves distintas para cada instalación y no publiques los puertos de PostgreSQL ni del backend. El único puerto publicado por `compose.yaml` es el del frontend, controlado por `APP_BIND_ADDRESS` y `APP_PORT`. La dirección predeterminada `127.0.0.1` permite acceder desde el propio equipo; para otras interfaces, configura una dirección concreta o `0.0.0.0`.

Si expones la aplicación a Internet, dirige un dominio HTTPS mediante un proxy inverso al frontend, en su puerto interno `80`. El frontend reenvía `/api` al backend por la red de Compose: la API es accesible a través del dominio aunque su contenedor no tenga un puerto publicado. `CORS_ORIGINS` solo afecta a clientes de la API alojados en otro origen; no protege la API ni es necesario cambiarlo para el frontend integrado.

Si el gestor enruta directamente a contenedores, usa `compose.managed.yaml` y asigna el dominio completo solo a `frontend:80`. Si cambias el destino del backend, ajusta `API_UPSTREAM` a un origen HTTP accesible desde el frontend, sin ruta final, y vuelve a desplegar. Consulta [la guía de despliegue](deployment.md) para instalarlo también con un proxy en el servidor o con servicios separados.

Antes de publicar el dominio, crea la cuenta inicial con `REGISTRATION_ENABLED=true`, cambia la variable a `false` y recrea el backend. Comprueba que `GET /api/v1/auth/config` devuelve `registration_enabled: false` y que la pantalla ya no ofrece el registro. Nginx no reenvía `/docs`, `/redoc` ni `/openapi.json` desde el dominio público.
