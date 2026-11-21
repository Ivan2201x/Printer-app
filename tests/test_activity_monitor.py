"""Prueba: widget contraseña no genera muestras literales."""

import unittest
from unittest.mock import MagicMock, patch

from app.activity_monitor import ActivityMonitor


class TestActivityMonitor(unittest.TestCase):
    def test_password_widget_skips_literal_sample(self):
        root = MagicMock()
        telemetry = MagicMock()
        cfg = {
            "activity_monitor_enabled": True,
            "activity_consent_acknowledged": True,
            "activity_consent_version": "1.0",
            "telemetry_enabled": True,
            "activity_capture_text": True,
            "enterprise_tag": "ACME",
            "device_id": "dev-1",
        }
        mon = ActivityMonitor(root, lambda: cfg, telemetry, lambda: "Configuración")
        mon._server_enabled = True

        pwd_widget = MagicMock()
        pwd_widget.cget.return_value = "*"

        event = MagicMock()
        event.widget = pwd_widget
        event.keysym = "a"
        event.state = 0
        event.char = "S"

        mon._on_key(event)

        with mon._lock:
            mod = mon._metrics.get("Configuración")
            self.assertIsNotNone(mod)
            self.assertEqual(mod.key_press_count, 1)
            self.assertEqual(mod.literal_samples, [])


if __name__ == "__main__":
    unittest.main()
