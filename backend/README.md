# Backend piloto de seguimiento de la OVA

API independiente del HTML para probar el guardado del progreso en PostgreSQL. La autenticación institucional no está conectada todavía; el modo de usuarios ficticios se limita a desarrollo y requiere un secreto local.

## Datos guardados

- Identificador autenticado (`subject_id`); en esta etapa son identidades ficticias, no datos de funcionarios.
- Curso y versión de la OVA.
- Estado general, primer ingreso, última actividad y fecha de finalización (marcas de tiempo generadas por el servidor).
- Estado por módulo, puntaje, intentos, acceso a recursos requeridos y tipos de recurso.

No se guardan contraseñas, clics individuales ni mensajes de chat. El puntaje llega desde el navegador y puede manipularse; este prototipo sirve para seguimiento formativo, no para certificar resultados.

## Ejecución local

1. Copia `.env.example` como `.env` y cambia `DEV_TEST_SECRET` y `POSTGRES_PASSWORD` por valores aleatorios alfanuméricos (o URL-safe). No subas `.env` a GitHub.
2. Ejecuta `docker compose up --build -d`.
3. El backend queda enlazado a `127.0.0.1:8000`; la base de datos no publica un puerto al exterior.
4. Consulta `http://127.0.0.1:8000/healthz` y la documentación interactiva en `http://127.0.0.1:8000/docs`.

La sesión ficticia solo está disponible con `APP_ENV=development`, `AUTH_MODE=mock`, `ENABLE_TEST_AUTH=true` y el encabezado `X-Dev-Test-Secret`. Hay veinte identidades de ejemplo (`test-agent-001` a `test-agent-020`) para poder simular hasta quince conexiones simultáneas. El endpoint entrega un token temporal que se envía como `Authorization: Bearer <token>`.

Para detener servicios sin borrar el avance: `docker compose down`. No uses `docker compose down -v` salvo que quieras eliminar permanentemente la base de pruebas.

## VPS de piloto

El perfil `vps` publica únicamente Caddy en los puertos 80/443. Caddy entrega `index.html`, obtiene HTTPS automáticamente y envía `/v1/*` al backend. El backend queda enlazado solo a `127.0.0.1:8000` y PostgreSQL no publica puertos al internet; el acceso web queda protegido con autenticación básica adicional para el piloto.

Antes del despliegue, configura un dominio o subdominio con DNS apuntando al VPS y permite en el firewall únicamente SSH, HTTP (80) y HTTPS (443). En el servidor:

1. Clona la rama `chat-docs-pilot` de `Vieterre/OVAM3LPRUEBA`.
2. Copia `.env.example` a `.env`; completa `SITE_ADDRESS`, `POSTGRES_PASSWORD`, `DEV_TEST_SECRET`, el usuario y el hash bcrypt de acceso web. Genera secretos nuevos; no los guardes en GitHub ni los compartas en el chat. Conserva el hash entre comillas simples porque contiene signos `$`.
3. Genera el hash con `docker compose --profile vps run --rm -it caddy caddy hash-password`; escribe la clave cuando se solicite (no se mostrará en pantalla) y consérvala solo en `.env`.
4. Ejecuta `docker compose --profile vps up --build -d` y comprueba `https://<SITE_ADDRESS>/healthz`.
5. Abre la dirección HTTPS, completa la autenticación básica del navegador y luego ingresa una identidad ficticia junto con el secreto de prueba.

No se ha desplegado desde este entorno: para hacerlo hacen falta el subdominio/DNS y acceso SSH seguro al VPS. Esta configuración sigue siendo un piloto: el modo ficticio se debe desactivar antes de producción y TIC debe definir la autenticación institucional y la retención de datos.

## Endpoints iniciales

- `GET /healthz`: estado del servicio.
- `POST /v1/dev/session`: emite un token temporal para una identidad ficticia (solo desarrollo).
- `POST /v1/me/entry`: registra primer ingreso o actividad posterior del curso autenticado.
- `PUT /v1/me/progress`: crea o actualiza el avance del curso autenticado.
- `GET /v1/me/progress?course_id=...&course_version=...`: consulta el avance propio.

El backend no confía en un identificador de persona enviado en el cuerpo de progreso: toma el sujeto del token. Las marcas de tiempo las genera el servidor.

## Pruebas automatizadas

Desde `backend/`, instala `requirements.txt` y `requirements-dev.txt`, y ejecuta `pytest`.

Este piloto integra el HTML y la persistencia de avance ficticio. Todavía no integra la autenticación de la Alcaldía, el chat/RAG, migraciones formales de base de datos, administración de reportes ni política institucional de retención. No debe desplegarse como servicio de producción. La autenticación institucional y las condiciones de producción requieren validación de TIC.