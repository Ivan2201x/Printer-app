# Servidor de telemetría (FastAPI)

Recibe eventos JSON y escaneos desde la app de escritorio.

## Instalación

```bash
cd server
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Variables de entorno

```bash
export TELEMETRY_API_KEY="clave-secreta-larga"
export PORT=8000
```

Use **HTTPS** en producción (reverse proxy Nginx/Caddy).

## Ejecutar

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Estado |
| POST | `/api/v1/events` | Lote JSON `{ "events": [...] }` |
| POST | `/api/v1/scans/upload` | Multipart: `metadata` + `file` |

Header obligatorio: `X-API-Key: <TELEMETRY_API_KEY>`

Datos guardados en `server/data/events.jsonl` y `server/data/scans/`.

## Monitoreo de actividad (in-app)

- Política: `GET /api/v1/activity/policy`
- Panel RBAC: `/admin/login` (bootstrap con `ADMIN_BOOTSTRAP_EMAIL` / `ADMIN_BOOTSTRAP_PASSWORD`)
- Documentación completa: [`docs/ACTIVITY_MONITORING.md`](../docs/ACTIVITY_MONITORING.md)

## Cliente (app escritorio)

En **Configuración → Empresa**:

- Activar telemetría
- URL: `https://su-servidor:8000`
- Misma API Key que `TELEMETRY_API_KEY`
