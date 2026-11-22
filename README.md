# Bicopter Rail 2-DOF

Monorepo colaborativo para el banco de pruebas de bicóptero 2-DOF sobre riel vertical (ESP32 + PlatformIO + Host Python).

## Estructura

- `firmware/`: Proyecto PlatformIO para ESP32 (`esp32dev`, framework Arduino).
- `host/`: Paquete Python (`bicopter_host`) para telemetría, análisis y futuro control/HIL.
- `docs/`: Documentación de cableado, seguridad, flujo Git y worklogs.

## Inicio rápido

### Firmware
```powershell
pio run -d firmware
```

### Host Python
```powershell
cd host
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pytest -q
```

Ver [docs/WIRING_AND_SAFETY.md](docs/WIRING_AND_SAFETY.md) antes de energizar cualquier componente.
