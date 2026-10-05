# Administración local y contraseñas

Cada usuario autenticado puede cambiar su propia contraseña desde **Configuración → Cambiar contraseña**. Debe indicar la actual y una nueva de al menos 12 caracteres. El cambio renueva su sesión e invalida las sesiones anteriores de esa cuenta.

## Activar el superusuario

Define `SUPERUSER_EMAIL` y `SUPERUSER_PASSWORD` en `.env` o en las variables de entorno del despliegue. Usa una contraseña única de al menos 12 caracteres; se recomiendan 24 o más. El superusuario vive en la configuración del servidor, separado de las cuentas de la aplicación. Tras cambiar estas variables, vuelve a desplegar o recrea el backend para que lea el nuevo entorno; cambiar la contraseña del superusuario invalida sus sesiones administrativas. Las sesiones del backoffice caducan a los 30 minutos.

El servicio `admin` escucha únicamente en `127.0.0.1:8081` del servidor de manera predeterminada. Abre `http://127.0.0.1:8081/admin` en el propio servidor. Desde otro equipo, crea un túnel SSH y abre esa misma dirección en tu navegador local:

```bash
ssh -L 8081:127.0.0.1:8081 usuario@servidor
```

Si necesitas acceso desde una red local, configura `ADMIN_BIND_ADDRESS` con la IP privada del servidor y protege la conexión con HTTPS o un túnel. No uses `0.0.0.0` ni asignes un dominio público al servicio `admin`. El frontend público devuelve 404 para `/admin` y `/api/v1/admin/`.

## Crear usuarios y solicitar recuperación

En el backoffice inicia sesión con el correo y la contraseña del superusuario. Con SMTP y `APP_PUBLIC_URL` configurados, puedes crear cuentas aunque `REGISTRATION_ENABLED=false`: el usuario recibe una invitación para establecer su contraseña y verificar su correo. Para una cuenta existente, el administrador puede solicitar una recuperación; el enlace llega solo al usuario. El backoffice nunca recibe contraseñas ni enlaces. Solicitar la recuperación no cierra sesiones ni cambia la contraseña; al completar el enlace sí se invalidan las sesiones anteriores. Las cuentas sin verificar pueden entrar, pero la recuperación iniciada por el propio usuario exige que verifiquen antes su correo desde Configuración. Si SMTP está desactivado, estas acciones administrativas de correo quedan deshabilitadas.

Si despliegas los contenedores por separado, usa la misma imagen del frontend para el servicio `admin` y define `NGINX_ENVSUBST_TEMPLATE_DIR=/etc/nginx/templates/admin` además de `API_UPSTREAM`. Publícalo solo en la interfaz local del servidor. El backend recibe `SUPERUSER_EMAIL` y `SUPERUSER_PASSWORD`; el contenedor frontend público no los recibe.
