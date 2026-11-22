# Bicopter Rail 2-DOF

Monorepo colaborativo para el banco de pruebas de bicóptero 2-DOF sobre riel vertical (ESP32 + PlatformIO + Host Python).

## Estructura

- `firmware/`: Proyecto PlatformIO para ESP32 (`esp32dev`, framework Arduino).
- `host/`: Paquete Python (`bicopter_host`) para telemetría, análisis y futuro control/HIL.
- `docs/`: Documentación de cableado, seguridad, flujo Git y worklogs.

## Inicio rápido

### Clonar y colaborar
```powershell
git clone https://github.com/FoolishCaptain-3r1k/bicopter-rail-2dof.git
cd bicopter-rail-2dof
```

Flujo mínimo de colaboración:
1. Actualizar `main`: `git checkout main && git pull origin main`
2. Crear rama por módulo: `git checkout -b feature/<modulo>`
3. Desarrollar, verificar compilación/tests y hacer commit atómico.
4. Subir rama y abrir Pull Request hacia `main`.

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
