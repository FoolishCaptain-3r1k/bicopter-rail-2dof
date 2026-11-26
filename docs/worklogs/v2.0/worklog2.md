# Worklog 2 (v2.0) | Prev: [[worklog1]]
- **Estado:** PASS
- **Invariantes Cubiertos:** Entorno `.venv` con `pyserial==3.5`; detección de `COM4`; compilación y flasheo exitoso de `version-prueba-v9` en ESP32; validación de telemetría real (`STATE,READY`, `IMU=OK`, `TOF` válido con `deviceStatus=11`, motores en `0.00%` / `OFF`); servidor HTTP local activo en puerto `8080` y `dashboard.html` abierto en Microsoft Edge.

---

## 1. Entorno Python y Dependencias
- **Entorno Virtual:** Creado en `.venv` (`Python 3.11.7`).
- **Dependencias Instaladas:** `.\.venv\Scripts\pip.exe install -r version-prueba-v9\requirements.txt` -> `pyserial==3.5` instalado correctamente.

---

## 2. Detección de Puerto y Flasheo Firmware
- **Puerto Detectado:** `COM4` — `Silicon Labs CP210x USB to UART Bridge (COM4)`, `USB VID:PID=10C4:EA60 SER=0001 LOCATION=1-2`.
- **Compilación y Carga:** `C:\Users\Ruiza\.platformio\penv\Scripts\pio.exe run -d version-prueba-v9 -t upload --upload-port COM4` -> **`[SUCCESS]`** (38.39 s).
  - Dependencia descargada: `pololu/VL53L0X @ 1.3.1`.
  - Uso de memoria: RAM `6.8%` (`22312 / 327680 bytes`), Flash `25.4%` (`333497 / 1310720 bytes`).
  - Chip detectado: `ESP32-D0WD-V3 (revision v3.1)`, MAC `ec:e3:34:1a:74:c4`.

---

## 3. Validación Serial Real (`COM4` @ `115200` baud, 5.5 s, sin armar)
Captura ejecutada con `.\.venv\Scripts\python.exe` y `pyserial` (`203` líneas recibidas; puerto cerrado al finalizar para dejarlo libre al navegador):

```text
# RAIL_PID_USB v8 HEIGHT_SCALE=10 BNO055=0x28 VL53L0X=0x29 I2C_HZ=100000 timeout_ms=50
# BNO chip=0xA0 address=0x28 init=OK
# TOF model=VL53L0X address=0x29 budget_us=50000 output_ms=50 init=OK
STATE,READY
IMU,5247,86.38,-1.31,0.00,0.06,-0.12,0.00,9.61,0.25,0.57,0,3,0,0,OK
IMU,5297,86.38,-1.31,0.00,0.00,0.12,-0.06,9.62,0.22,0.56,0,3,0,0,OK
TOF,5202,151,OK,11
TOF,5302,147,OK,11
CTRL,5249,0,1,-29.33,0.00,86.38,0.00,0.00,0.00,1,IDLE,OFF,86.38
CTRL,5299,0,1,-29.33,0.00,86.38,0.00,0.00,0.00,1,IDLE,OFF,86.38
```

- **Confirmaciones:**
  - `STATE,READY` recibido y `originReady=1` en `CTRL`.
  - `IMU` (`74` tramas): estado `OK`, `cal_gyro=3`, `roll` estable en `86.38°` (se toma como `0°` relativo al armar).
  - `TOF` (`38` tramas): `distance_mm=145..151` (`< 8190`), estado `OK`, `device_status_raw=11`.
  - Motores en `0.00%` (`1000 µs`), `armed=0`, `mode=IDLE`, `power=OFF`.

---

## 4. Servidor Local, UI y Cliente Alternativo
- **Servidor HTTP:** `.\.venv\Scripts\python.exe -m http.server 8080 --directory version-prueba-v9` corriendo en segundo plano (`PID=13712`).
- **URL Activa:** `http://localhost:8080/dashboard.html` — verificado con `Invoke-WebRequest` -> `HTTP 200` y abierto en **Microsoft Edge**.
- **Cliente Alternativo Tkinter (opcional, cerrar conexión Web Serial antes de usarlo):**
  ```powershell
  .\.venv\Scripts\python.exe version-prueba-v9\keyboard_control.py COM4
  ```

---

## 5. Ganancias Conservadoras Recomendadas para Primer Armado (Sin Hélices / Prueba Inicial)
Dado que el firmware exige `Kp > 0` en ambos ejes (`H` en unidades escaladas `HEIGHT_SCALE=10`, `A` en grados) y la salida de cada PID se suma a `BASE_PERCENT = 58%` (`1580 µs`) con saturación de `±40%` y rampa de `20%/s`:

- **PID de Altura (`H`, mm escalados):** `Kp = 0.05`, `Ki = 0.00`, `Kd = 0.02`
  *(Con `Kp = 0.05`, un error de `100` unidades aporta `+5%` (`+50 µs`) sobre la base de `1580 µs`, evitando saltos bruscos).*
- **PID de Rotación (`A`, grados):** `Kp = 0.30`, `Ki = 0.00`, `Kd = 0.05`
  *(Con `Kp = 0.30`, un error de `10°` aporta `±3%` diferencial entre motor izquierdo y derecho).*

---

## 6. Verificación Focalizada
- **Archivos Modificados:** `docs/worklogs/v2.0/worklog2.md` — registro completo de instalación, flasheo, telemetría y arranque de UI.
- **Verificación Ejecutada:**
  - `pio.exe run -d version-prueba-v9 -t upload --upload-port COM4` -> `SUCCESS` (`38.39 s`).
  - Captura serial en `COM4` (`5.5 s`, `115200` baud) -> `STATE,READY`, `IMU=OK`, `TOF=OK (11)`, `CTRL` con `originReady=1`, `sensors_valid=1`, `0.00%` (`OFF`).
  - `Invoke-WebRequest http://localhost:8080/dashboard.html` -> `200` (`PID=13712`), Edge abierto.
- **Acción Usuario (Human Gate):** En Edge (`http://localhost:8080/dashboard.html`), seleccionar modo, pulsar **Conectar por USB** -> elegir **COM4**, ingresar ganancias conservadoras y probar sin hélices antes de prueba de vuelo en riel.
