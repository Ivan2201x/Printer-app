"""API FastAPI: telemetría + actividad in-app + panel admin RBAC."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

import auth
import settings
import store
from auth import (
    audit_from_request,
    create_token,
    get_current_user,
    hash_password,
    require_perm,
    verify_password,
)
from retention import run_retention_job
from store import (
    export_activity,
    get_monitoring_enabled,
    insert_activity_metric,
    list_admin_audit,
    query_activity,
    set_monitoring_enabled,
)

DATA_DIR = settings.DATA_DIR
EVENTS_FILE = DATA_DIR / "events.jsonl"
SCANS_DIR = DATA_DIR / "scans"
TEMPLATES = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

app = FastAPI(title="Printer App Telemetry", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def require_api_key(x_api_key: str = Header(default="", alias="X-API-Key")) -> str:
    if not settings.TELEMETRY_API_KEY or x_api_key != settings.TELEMETRY_API_KEY:
        raise HTTPException(status_code=401, detail="API key inválida")
    return x_api_key


class TelemetryEvent(BaseModel):
    type: str
    timestamp_utc: str
    device_id: str
    payload: dict = Field(default_factory=dict)


class EventsBatch(BaseModel):
    events: list[TelemetryEvent]


class LoginBody(BaseModel):
    email: str
    password: str


def _policy_public() -> dict:
    return {
        "monitoring_enabled": get_monitoring_enabled(),
        "purpose": settings.ACTIVITY_POLICY_PURPOSE,
        "legal_basis": settings.ACTIVITY_POLICY_LEGAL_BASIS,
        "retention": settings.ACTIVITY_POLICY_RETENTION,
        "contact": settings.ACTIVITY_POLICY_CONTACT,
        "retention_days": settings.ACTIVITY_RETENTION_DAYS,
        "scope": "Solo actividad de teclado dentro del gestor de impresión/escaneo (no hook global SO).",
    }


def _bootstrap_admin() -> None:
    if store.get_user_by_email(settings.ADMIN_BOOTSTRAP_EMAIL):
        return
    pwd = settings.ADMIN_BOOTSTRAP_PASSWORD
    if not pwd:
        return
    store.create_user(settings.ADMIN_BOOTSTRAP_EMAIL, hash_password(pwd), "admin")


@app.on_event("startup")
def startup() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SCANS_DIR.mkdir(parents=True, exist_ok=True)
    store.init_db()
    _bootstrap_admin()
    run_retention_job()


@app.get("/health")
def health():
    return {"status": "ok", "time_utc": datetime.now(timezone.utc).isoformat()}


@app.get("/api/v1/activity/policy")
def activity_policy(_: str = Depends(require_api_key)):
    return _policy_public()


@app.post("/api/v1/events")
def ingest_events(batch: EventsBatch, _: str = Depends(require_api_key)):
    with EVENTS_FILE.open("a", encoding="utf-8") as f:
        for ev in batch.events:
            f.write(json.dumps(ev.model_dump(), ensure_ascii=False) + "\n")
            if ev.type == "activity_metrics":
                payload = ev.payload
                insert_activity_metric(
                    ev.device_id,
                    str(payload.get("corporate_user_id", "—")),
                    ev.model_dump(),
                )
    return {"accepted": len(batch.events)}


@app.post("/api/v1/scans/upload")
async def upload_scan(
    metadata: str = Form(...),
    file: UploadFile = File(...),
    _: str = Depends(require_api_key),
):
    try:
        meta = json.loads(metadata)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="metadata JSON inválido") from e
    import uuid

    device_id = str(meta.get("device_id") or "unknown")
    safe_id = device_id.replace("/", "_").replace("\\", "_")[:80]
    ext = Path(file.filename or "scan.bin").suffix or ".bin"
    name = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"
    dest = SCANS_DIR / safe_id
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / name
    content = await file.read()
    out.write_bytes(content)
    meta_path = out.with_suffix(out.suffix + ".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"stored": str(out), "bytes": len(content)}


# --- Admin panel (cookie JWT simple en header Authorization desde JS no — form + redirect token en cookie mejor)

SESSION_COOKIE = "admin_token"


def _user_from_cookie(request: Request) -> dict | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    try:
        data = auth.decode_token(token)
        return store.get_user_by_email(data["sub"])
    except HTTPException:
        return None


def _require_cookie_user(request: Request, perm: str) -> dict | None:
    user = _user_from_cookie(request)
    if not user:
        return None
    role = user.get("role", "viewer")
    if perm not in auth.ROLE_PERMISSIONS.get(role, set()):
        raise HTTPException(status_code=403, detail="Permiso denegado")
    return user


@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_page(request: Request):
    return TEMPLATES.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/admin/login")
async def admin_login_post(request: Request):
    form = await request.form()
    email = str(form.get("email", ""))
    password = str(form.get("password", ""))
    user = store.get_user_by_email(email)
    if not user or not verify_password(password, user["password_hash"]):
        return TEMPLATES.TemplateResponse(
            "login.html",
            {"request": request, "error": "Credenciales inválidas"},
            status_code=401,
        )
    token = create_token(user)
    resp = RedirectResponse("/admin/dashboard", status_code=303)
    resp.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax", max_age=settings.JWT_HOURS * 3600)
    store.log_admin_action(email, "login", "admin panel")
    return resp


@app.get("/admin/logout")
def admin_logout():
    resp = RedirectResponse("/admin/login", status_code=303)
    resp.delete_cookie(SESSION_COOKIE)
    return resp


def _summarize_event(event: dict) -> str:
    payload = event.get("payload") or {}
    mods = payload.get("modules") or {}
    parts = []
    for name, m in mods.items():
        parts.append(f"{name}: keys={m.get('key_press_count', 0)} shortcuts={m.get('shortcuts', {})}")
    return "\n".join(parts) or json.dumps(payload, ensure_ascii=False)[:500]


@app.get("/admin/dashboard", response_class=HTMLResponse)
def admin_dashboard(request: Request):
    user = _require_cookie_user(request, "view")
    if not user:
        return RedirectResponse("/admin/login", status_code=303)
    rows_raw = query_activity(limit=100)
    rows = []
    for r in rows_raw:
        rows.append(
            {
                "received_at": r["received_at"],
                "corporate_user_id": r["corporate_user_id"],
                "device_id": r["device_id"],
                "summary": _summarize_event(r["event"]),
            }
        )
    store.log_admin_action(user["email"], "view_metrics", f"rows={len(rows)}")
    role = user["role"]
    return TEMPLATES.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "rows": rows,
            "monitoring_enabled": get_monitoring_enabled(),
            "retention_days": settings.ACTIVITY_RETENTION_DAYS,
            "policy": _policy_public(),
            "can_export": "export" in auth.ROLE_PERMISSIONS.get(role, set()),
            "can_policy": "policy" in auth.ROLE_PERMISSIONS.get(role, set()),
        },
    )


@app.post("/admin/export")
async def admin_export(request: Request):
    user = _require_cookie_user(request, "export")
    if not user:
        return RedirectResponse("/admin/login", status_code=303)
    data = export_activity()
    audit_from_request(request, user, "export_metrics", f"bytes={len(data)}")
    return JSONResponse(content=json.loads(data))


@app.get("/admin/audit", response_class=HTMLResponse)
def admin_audit_page(request: Request):
    user = _require_cookie_user(request, "audit")
    if not user:
        return RedirectResponse("/admin/login", status_code=303)
    rows = list_admin_audit(200)
    store.log_admin_action(user["email"], "view_audit_log", f"rows={len(rows)}")
    return TEMPLATES.TemplateResponse("audit.html", {"request": request, "rows": rows})


@app.get("/admin/policy", response_class=HTMLResponse)
def admin_policy_page(request: Request):
    user = _require_cookie_user(request, "policy")
    if not user:
        return RedirectResponse("/admin/login", status_code=303)
    return TEMPLATES.TemplateResponse(
        "policy.html",
        {
            "request": request,
            "monitoring_enabled": get_monitoring_enabled(),
            "can_purge": user["role"] == "admin",
        },
    )


@app.post("/admin/policy")
async def admin_policy_post(request: Request):
    user = _require_cookie_user(request, "policy")
    if not user:
        return RedirectResponse("/admin/login", status_code=303)
    form = await request.form()
    enabled = form.get("monitoring_enabled") == "1"
    set_monitoring_enabled(enabled)
    audit_from_request(request, user, "set_monitoring", f"enabled={enabled}")
    return RedirectResponse("/admin/policy", status_code=303)


@app.post("/admin/purge")
async def admin_purge(request: Request):
    user = _require_cookie_user(request, "delete")
    if not user:
        return RedirectResponse("/admin/login", status_code=303)
    deleted = run_retention_job()
    audit_from_request(request, user, "purge_activity", f"deleted={deleted}")
    return RedirectResponse("/admin/dashboard", status_code=303)


# API JSON para integraciones
@app.post("/api/v1/admin/login")
def api_admin_login(body: LoginBody):
    user = store.get_user_by_email(body.email)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    return {"access_token": create_token(user), "role": user["role"]}


@app.get("/api/v1/admin/activity")
def api_list_activity(user: dict = Depends(require_perm("view"))):
    return query_activity(limit=200)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), reload=False)
