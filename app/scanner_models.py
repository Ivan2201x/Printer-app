from dataclasses import dataclass


class ScannerError(Exception):
    pass


@dataclass
class ScannerDevice:
    device_id: str
    name: str
    manufacturer: str
    status: str
