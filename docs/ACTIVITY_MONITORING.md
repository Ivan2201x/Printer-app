# Monitoreo de actividad empresarial

Documento de arquitectura, cumplimiento e implementación (v1.0).

## 1. Arquitectura propuesta

```
┌─────────────────────┐     HTTPS + X-API-Key      ┌──────────────────────────┐
│  App escritorio     │ ─────────────────────────► │  FastAPI (server/)       │
│  ActivityMonitor    │   activity_metrics         │  SQLite + events.jsonl   │
│  (solo in-app)      │ ◄── GET /activity/policy   │  Panel /admin (RBAC)     │
└─────────────────────┘                            └──────────────────────────┘
```

| Capa | Alcance | Estado |
|------|---------|--------|
| **A — In-app** | Teclado mientras la app tiene foco (pestaña = módulo) | **Implementado** |
| **B — Hook global SO** | Todas las apps (Chrome, Outlook, etc.) | **No implementado** — requiere aprobación formal (§2) |

Principios: minimización (métricas por defecto), mínimo privilegio (RBAC), cola offline reutilizando telemetría, kill switch en servidor.

## 2. Riesgos del hook global (decisión pendiente)

Antes de implementar captura a nivel de sistema operativo, la empresa debe aprobar por escrito:

| Riesgo | Detalle |
|--------|---------|
| **Privacidad** | Captura inevitable de credenciales, salud, sindicación, mensajes personales en el mismo equipo. |
| **Cumplimiento** | GDPR/LFPDPPP exigen base legal, proporcionalidad y DPIA; un hook global raramente pasa minimización. |
| **Seguridad** | Un bug o filtración del servidor expone todo lo tecleado en la organización. |
| **Técnico** | Antivirus/EDR pueden bloquear hooks; UAC; distinto API Win/Linux; conflictos con otros agentes. |
| **Laboral** | Debe existir aviso **previo**, específico y documentado; ocultar el indicador invalida consentimiento. |

**Implementación actual:** `try_os_global_hook()` lanza `NotImplementedError`. Solo capa A.

## 3. Modelo de datos

### Cliente (evento `activity_metrics`)

```json
{
  "type": "activity_metrics",
  "device_id": "uuid",
  "payload": {
    "corporate_user_id": "EMPRESA:usuario@HOST",
    "window_module": "Impresión",
    "metrics_only": true,
    "modules": {
      "Configuración": {
        "key_press_count": 42,
        "shortcuts": {"Ctrl+s": 1},
        "literal_samples": []
      }
    }
  }
}
```

### Servidor (`activity.db`)

- `activity_metrics` — eventos recibidos (JSON completo).
- `users` — email, hash contraseña, rol (`admin` | `auditor` | `viewer`).
- `admin_audit` — consultas, exportaciones, cambios de política, purgas.
- `policy.monitoring_enabled` — kill switch global.

## 4. Flujo consentimiento / aviso

1. IT activa política y despliega app con `activity_monitor_enabled` (o usuario activa en Configuración).
2. Al arrancar (o al guardar), diálogo **Consentimiento — monitoreo** con alcance in-app.
3. Usuario acepta → `activity_consent_acknowledged` + `activity_consent_version`.
4. Banner amarillo visible: **Monitoreo ACTIVO**.
5. Política publicada en servidor (`GET /api/v1/activity/policy`) y panel admin.

## 5. Controles de seguridad

- Autenticación API: `X-API-Key` (clientes).
- Panel admin: JWT en cookie HttpOnly; PBKDF2 para contraseñas admin.
- **RBAC:** admin (todo), auditor (ver + exportar + audit), viewer (solo ver).
- Auditoría de acciones admin en `admin_audit`.
- HTTPS obligatorio en producción.
- Exclusión de campos `show="*"` y nombres sensibles (`activity_sanitize.py`).

## 6. Implementación en repo

| Archivo | Rol |
|---------|-----|
| `app/activity_monitor.py` | Métricas in-app, flush periódico |
| `app/activity_sanitize.py` | Enmascaramiento y exclusiones |
| `server/main.py` | Ingesta + panel admin |
| `server/store.py` | SQLite |
| `server/auth.py` | JWT + RBAC |
| `server/retention.py` | Purga automática |

## 7. Variables de entorno (servidor)

| Variable | Descripción |
|----------|-------------|
| `TELEMETRY_API_KEY` | Clave clientes |
| `JWT_SECRET` | Firma tokens admin |
| `ADMIN_BOOTSTRAP_EMAIL` / `ADMIN_BOOTSTRAP_PASSWORD` | Primer admin |
| `ACTIVITY_RETENTION_DAYS` | Retención (default 90) |
| `ACTIVITY_MONITORING_ENABLED` | Estado inicial kill switch |
| `ACTIVITY_POLICY_*` | Textos finalidad, base legal, contacto DPO |

## 8. Panel administrativo

- `http://servidor:8000/admin/login`
- Dashboard métricas, export JSON (auditado), auditoría de accesos, política / desactivar monitoreo, purga manual.

## 9. Política de retención

- Al arrancar el servidor: `run_retention_job()` elimina registros más antiguos que `ACTIVITY_RETENTION_DAYS`.
- Admin puede ejecutar purga desde `/admin/policy`.

## 10. Pruebas

```bash
python -m unittest discover -s tests -p "test_activity*.py"
```

Verifican enmascaramiento, detección de campos contraseña y ausencia de texto sensible en registros de ejemplo.

---

**Responsables:** definir en `ACTIVITY_POLICY_CONTACT`. **Base jurídica:** sustituir placeholder en `ACTIVITY_POLICY_LEGAL_BASIS` con texto aprobado por legal.
