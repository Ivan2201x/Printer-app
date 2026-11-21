"""Eliminación automática por política de retención."""

import logging

import settings
from store import log_admin_action, purge_activity_older_than

logger = logging.getLogger(__name__)


def run_retention_job() -> int:
    deleted = purge_activity_older_than(settings.ACTIVITY_RETENTION_DAYS)
    if deleted:
        logger.info("Retención: eliminados %s registros de actividad", deleted)
        log_admin_action("system@retention", "purge_activity", f"deleted={deleted}")
    return deleted
