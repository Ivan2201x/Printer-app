"""Pruebas: contraseñas y campos sensibles no se registran en claro."""

import unittest
from unittest.mock import MagicMock

from app.activity_sanitize import (
    is_password_entry,
    is_sensitive_context,
    looks_like_password_payload,
    mask_text,
    redact_for_log,
    sanitize_literal,
)


class TestActivitySanitize(unittest.TestCase):
    def test_password_entry_detected_by_show(self):
        w = MagicMock()
        w.cget.return_value = "*"
        self.assertTrue(is_password_entry(w))

    def test_sensitive_field_name(self):
        self.assertTrue(is_sensitive_context(field_name="telemetry_api_key"))

    def test_sanitize_literal_masks(self):
        self.assertEqual(sanitize_literal("hola", allowed=True), "h***a")

    def test_sanitize_literal_blocked_when_not_allowed(self):
        self.assertIsNone(sanitize_literal("MySecretPass123!", allowed=False))

    def test_mask_never_returns_full_password(self):
        pwd = "SuperSecretPassword99!"
        masked = mask_text(pwd)
        self.assertNotEqual(masked, pwd)
        self.assertIn("***", masked)

    def test_looks_like_password_payload(self):
        self.assertTrue(looks_like_password_payload("MyP@ssw0rd1234"))

    def test_redact_strips_sensitive_keys(self):
        dirty = {
            "literal_sample": "api_key=sk-live-abcdef",
            "key_press_count": 10,
        }
        clean = redact_for_log(dirty)
        self.assertIsNone(clean.get("literal_sample"))

    def test_corporate_metrics_record_has_no_raw_password_field(self):
        """Simula payload de métricas: no debe incluir texto de contraseña en claro."""
        record = {
            "type": "activity_metrics",
            "payload": {
                "modules": {
                    "Configuración": {
                        "key_press_count": 5,
                        "shortcuts": {"Ctrl+v": 1},
                        "literal_samples": [mask_text("x")],
                    }
                },
                "metrics_only": True,
            },
        }
        samples = record["payload"]["modules"]["Configuración"]["literal_samples"]
        for s in samples:
            self.assertNotIn("password", s.lower())
            self.assertIn("***", s)


if __name__ == "__main__":
    unittest.main()
