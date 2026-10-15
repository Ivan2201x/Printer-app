"""Escaneo WIA — Windows."""

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from app.scanner_models import ScannerDevice, ScannerError

logger = logging.getLogger(__name__)

WIA_DEVICE_TYPE_SCANNER = 1
WIA_IPS_XRES = 6151
WIA_IPS_YRES = 6152
WIA_IPS_CUR_INTENT = 6146

COLOR_MODE_MAP = {
    "Color": 1,
    "Escala de grises": 2,
    "Blanco y negro": 4,
}


def _wia_manager():
    import win32com.client

    return win32com.client.Dispatch("WIA.DeviceManager")


def list_scanners() -> list[ScannerDevice]:
    try:
        dm = _wia_manager()
    except Exception as e:
        logger.error("WIA DeviceManager: %s", e)
        raise ScannerError("No fue posible acceder a WIA.") from e

    devices: list[ScannerDevice] = []
    try:
        count = dm.DeviceInfos.Count
    except Exception as e:
        logger.error("DeviceInfos.Count: %s", e)
        return devices

    for i in range(1, count + 1):
        try:
            info = dm.DeviceInfos.Item(i)
        except Exception as e:
            logger.warning("DeviceInfos.Item(%s): %s", i, e)
            continue
        try:
            dtype = int(info.Type)
        except Exception:
            continue
        if dtype != WIA_DEVICE_TYPE_SCANNER:
            continue
        try:
            dev_id = str(info.DeviceID)
            name = str(info.Properties("Name").Value)
        except Exception:
            continue
        manufacturer = "—"
        status = "—"
        try:
            manufacturer = str(info.Properties("Manufacturer").Value)
        except Exception:
            pass
        try:
            status = str(info.Properties("Port").Value)
        except Exception:
            pass
        devices.append(
            ScannerDevice(
                device_id=dev_id,
                name=name,
                manufacturer=manufacturer or "—",
                status=status or "—",
            )
        )
    return devices


def _find_item_by_name(items, name: str):
    for i in range(1, items.Count + 1):
        it = items.Item(i)
        try:
            if it.Properties("Item Name").Value == name:
                return it
        except Exception:
            pass
    return items.Item(1) if items.Count >= 1 else None


def _set_property_if_writable(item, prop_id: int, value: Any) -> bool:
    try:
        prop = item.Properties(prop_id)
    except Exception:
        return False
    try:
        if not prop.IsReadOnly:
            prop.Value = value
            return True
    except Exception as e:
        logger.debug("Propiedad %s: %s", prop_id, e)
    return False


def scan_to_temp_file(
    device_id: str,
    dpi: int,
    color_mode: str,
    use_feeder: bool = False,
) -> Path:
    del use_feeder
    dm = _wia_manager()
    device = None
    for i in range(1, dm.DeviceInfos.Count + 1):
        info = dm.DeviceInfos.Item(i)
        if str(info.DeviceID) == device_id:
            device = info.Connect()
            break
    if device is None:
        raise ScannerError("El escáner seleccionado no está disponible.")

    items = device.Items
    if items.Count < 1:
        raise ScannerError("El dispositivo no expone ítems de escaneo.")
    item = _find_item_by_name(items, "Flatbed") or items.Item(1)
    for res_prop in (WIA_IPS_XRES, WIA_IPS_YRES):
        _set_property_if_writable(item, res_prop, dpi)
    intent = COLOR_MODE_MAP.get(color_mode, 1)
    _set_property_if_writable(item, WIA_IPS_CUR_INTENT, intent)

    fd, tmp_path = tempfile.mkstemp(suffix=".jpg", prefix="wia_scan_")
    os.close(fd)
    try:
        os.unlink(tmp_path)
    except OSError:
        pass
    out_path = Path(tmp_path)

    try:
        image = item.Transfer()
    except Exception as e:
        logger.error("WIA Transfer: %s", e)
        msg = str(e).lower()
        if "busy" in msg or "use" in msg:
            raise ScannerError("El dispositivo está siendo utilizado por otra aplicación.") from e
        raise ScannerError("No fue posible iniciar el escaneo.") from e

    try:
        image.SaveFile(str(out_path))
    except Exception as e:
        logger.error("SaveFile: %s", e)
        raise ScannerError("No fue posible guardar el documento.") from e
    return out_path
