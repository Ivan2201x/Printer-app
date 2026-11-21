"""Configuración del servidor por variables de entorno."""

import os
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
DB_PATH = Path(os.environ.get("ACTIVITY_DB_PATH", str(DATA_DIR / "activity.db")))

TELEMETRY_API_KEY = os.environ.get("TELEMETRY_API_KEY", "cambiar-en-produccion")
JWT_SECRET = os.environ.get("JWT_SECRET", "cambiar-jwt-secreto-largo")
JWT_HOURS = int(os.environ.get("JWT_HOURS", "8"))

ADMIN_BOOTSTRAP_EMAIL = os.environ.get("ADMIN_BOOTSTRAP_EMAIL", "admin@empresa.local")
ADMIN_BOOTSTRAP_PASSWORD = os.environ.get("ADMIN_BOOTSTRAP_PASSWORD", "")

ACTIVITY_RETENTION_DAYS = int(os.environ.get("ACTIVITY_RETENTION_DAYS", "90"))
ACTIVITY_MONITORING_ENABLED = os.environ.get("ACTIVITY_MONITORING_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
)

ACTIVITY_POLICY_PURPOSE = os.environ.get(
    "ACTIVITY_POLICY_PURPOSE",
    "Auditoría de uso del gestor de impresión/escaneo en equipos corporativos.",
)
ACTIVITY_POLICY_LEGAL_BASIS = os.environ.get(
    "ACTIVITY_POLICY_LEGAL_BASIS",
    "Contrato laboral y política interna IT — definir texto oficial con legal.",
)
ACTIVITY_POLICY_RETENTION = os.environ.get(
    "ACTIVITY_POLICY_RETENTION",
    f"{ACTIVITY_RETENTION_DAYS} días, eliminación automática.",
)
ACTIVITY_POLICY_CONTACT = os.environ.get("ACTIVITY_POLICY_CONTACT", "dpo@empresa.local")
