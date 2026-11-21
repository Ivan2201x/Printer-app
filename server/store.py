"""Persistencia SQLite: métricas, usuarios RBAC, auditoría admin."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import settings

ROLES = ("admin", "auditor", "viewer")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@contextmanager
def connect():
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin','auditor','viewer')),
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS activity_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                received_at TEXT NOT NULL,
                device_id TEXT NOT NULL,
                corporate_user_id TEXT NOT NULL,
                event_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS admin_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                at TEXT NOT NULL,
                actor_email TEXT NOT NULL,
                action TEXT NOT NULL,
                detail TEXT
            );
            CREATE TABLE IF NOT EXISTS policy (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        row = conn.execute("SELECT value FROM policy WHERE key='monitoring_enabled'").fetchone()
        if not row:
            conn.execute(
                "INSERT INTO policy (key, value) VALUES ('monitoring_enabled', ?)",
                ("true" if settings.ACTIVITY_MONITORING_ENABLED else "false",),
            )


def set_monitoring_enabled(enabled: bool) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO policy (key, value) VALUES ('monitoring_enabled', ?)",
            ("true" if enabled else "false",),
        )


def get_monitoring_enabled() -> bool:
    with connect() as conn:
        row = conn.execute("SELECT value FROM policy WHERE key='monitoring_enabled'").fetchone()
        if not row:
            return settings.ACTIVITY_MONITORING_ENABLED
        return row["value"].lower() in ("1", "true", "yes")


def create_user(email: str, password_hash: str, role: str) -> None:
    if role not in ROLES:
        raise ValueError("rol inválido")
    with connect() as conn:
        conn.execute(
            "INSERT INTO users (email, password_hash, role, created_at) VALUES (?,?,?,?)",
            (email.lower(), password_hash, role, _utc_now()),
        )


def get_user_by_email(email: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email=?", (email.lower(),)).fetchone()
        return dict(row) if row else None


def list_users() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT id, email, role, created_at FROM users ORDER BY email").fetchall()
        return [dict(r) for r in rows]


def insert_activity_metric(device_id: str, corporate_user_id: str, event: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO activity_metrics (received_at, device_id, corporate_user_id, event_json) VALUES (?,?,?,?)",
            (_utc_now(), device_id, corporate_user_id, json.dumps(event, ensure_ascii=False)),
        )


def query_activity(limit: int = 200) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, received_at, device_id, corporate_user_id, event_json FROM activity_metrics "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        out = []
        for r in rows:
            item = dict(r)
            item["event"] = json.loads(item.pop("event_json"))
            out.append(item)
        return out


def export_activity(limit: int = 5000) -> str:
    rows = query_activity(limit=limit)
    return json.dumps(rows, ensure_ascii=False, indent=2)


def purge_activity_older_than(days: int) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with connect() as conn:
        cur = conn.execute("DELETE FROM activity_metrics WHERE received_at < ?", (cutoff,))
        return cur.rowcount


def log_admin_action(actor_email: str, action: str, detail: str = "") -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO admin_audit (at, actor_email, action, detail) VALUES (?,?,?,?)",
            (_utc_now(), actor_email, action, detail),
        )


def list_admin_audit(limit: int = 100) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM admin_audit ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
