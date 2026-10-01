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

## Seguridad local

Genera claves distintas para cada instalación y no publiques el puerto de PostgreSQL. Si expones la aplicación a Internet, coloca HTTPS delante del puerto 8080 y configura el origen público en `CORS_ORIGINS`. El registro público de usuarios está habilitado en esta fase, apropiado para un servidor local privado; antes de abrirlo a Internet debe añadirse una política de invitaciones o desactivar el registro después de crear el primer usuario.
