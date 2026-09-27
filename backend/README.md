# Backend piloto de seguimiento de la OVA

API independiente del HTML para probar el guardado del progreso en PostgreSQL. La autenticación institucional no está conectada todavía; el modo de usuarios ficticios se limita a desarrollo y requiere un secreto local.

## Datos guardados

- Identificador autenticado (`subject_id`); en esta etapa son identidades ficticias, no datos de funcionarios.
- Curso y versión de la OVA.
- Estado general, primer ingreso, última actividad y fecha de finalización (marcas de tiempo generadas por el servidor).
- Estado por módulo, puntaje, intentos, acceso a recursos requeridos y tipos de recurso.

No se guardan contraseñas, clics individuales ni mensajes de chat. El puntaje llega desde el navegador y puede manipularse; este prototipo sirve para seguimiento formativo, no para certificar resultados.

## Ejecución local o en un VPS de pruebas

1. Copia `.env.example` como `.env` y cambia `DEV_TEST_SECRET` y `POSTGRES_PASSWORD` por valores aleatorios alfanuméricos (o URL-safe). No subas `.env` a GitHub.
2. Ejecuta `docker compose up --build -d`.
3. El backend queda enlazado a `127.0.0.1:8000`; la base de datos no publica un puerto al exterior. En un VPS, configura después un proxy HTTPS y reglas de firewall antes de permitir acceso desde un navegador.
4. Consulta `http://127.0.0.1:8000/healthz` y la documentación interactiva en `http://127.0.0.1:8000/docs`.

La sesión ficticia solo está disponible con `APP_ENV=development`, `AUTH_MODE=mock`, `ENABLE_TEST_AUTH=true` y el encabezado `X-Dev-Test-Secret`. Hay veinte identidades de ejemplo (`test-agent-001` a `test-agent-020`) para poder simular hasta quince conexiones simultáneas. El endpoint entrega un token temporal que se envía como `Authorization: Bearer <token>`.

Para detener servicios sin borrar el avance: `docker compose down`. No uses `docker compose down -v` salvo que quieras eliminar permanentemente la base de pruebas.

## Endpoints iniciales

- `GET /healthz`: estado del servicio.
- `POST /v1/dev/session`: emite un token temporal para una identidad ficticia (solo desarrollo).
- `POST /v1/me/entry`: registra primer ingreso o actividad posterior del curso autenticado.
- `PUT /v1/me/progress`: crea o actualiza el avance del curso autenticado.
- `GET /v1/me/progress?course_id=...&course_version=...`: consulta el avance propio.

El backend no confía en un identificador de persona enviado en el cuerpo de progreso: toma el sujeto del token. Las marcas de tiempo las genera el servidor.

## Pruebas automatizadas

Desde `backend/`, instala `requirements.txt` y `requirements-dev.txt`, y ejecuta `pytest`.

Este piloto todavía no integra el HTML, la autenticación de la Alcaldía, el chat/RAG, migraciones de base de datos, administración de reportes ni política institucional de retención. No debe desplegarse como servicio de producción. La autenticación institucional y las condiciones de producción requieren validación de TIC.
