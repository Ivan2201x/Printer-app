"""Modelos compartidos impresión (Windows / Linux)."""

from dataclasses import dataclass


@dataclass
class PrinterInfo:
    name: str
    status: str
    driver: str
    port: str
    location: str
    comment: str
    is_default: bool
    connection: str


@dataclass
class PrintJobInfo:
    job_id: int
    document: str
    user: str
    status: str
    size: int | None
    pages: int | None
    submitted: str
