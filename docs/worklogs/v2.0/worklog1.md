# Worklog 1 (v2.0) | Prev: None
- **Estado:** PASS
- **Invariantes Cubiertos:** Sincronización exacta con `origin/version-final-opcional` (`548022e`); preservación de cambios locales previos en `git stash`; auditoría caja blanca del 100% de módulos activos (firmware ESP32, protocolo serial, UI Web Serial, control por gestos MediaPipe, logger CSV y cliente Python).

---

## 1. Sincronización Git y Estado del Entorno
- **Rama remota localizada:** `origin/version-final-opcional` -> commit `548022ef2b1466a16ce9500c5ddc6e06fcdb0139` (*"Publica la V9 opcional con control por gestos y flechas manuales"*).
- **Resguardo de estado previo:** Antes de cambiar de rama, `main` (`0cd62af`, +16 commits locales respecto a `origin/main`) tenía 16 archivos modificados sin commitear. Se guardaron íntegramente en `git stash` bajo el mensaje `pre-sync-version-final-opcional`. Los archivos no rastreados previos (`datos_pruebas/`, `docs/P2_PWM/`, `docs/worklogs/v0.1/worklog13..29.md`, `host/scripts/`, `host/ui/`, etc.) permanecen intactos en el working tree.
- **Checkout aplicado:** `git checkout -B version-final-opcional origin/version-final-opcional`.
- **Entorno Python (`.venv`):** `Test-Path .\.venv\Scripts\python.exe` -> `False` (no existe `.venv` en la raíz del repo). `version-prueba-v9/requirements.txt` declara únicamente `pyserial==3.5`.

---

## 2. Mapa del Repositorio (`version-final-opcional`)
- **Módulo principal vigente (`version-prueba-v9/` — 24 archivos):**
  - Firmware ESP32: `platformio.ini`, `src/main.cpp`, `include/controller.h`, `include/diagnostic.h`, `include/telemetry.h`.
  - Interfaz Web Serial + Visión: `dashboard.html`, `dashboard.js`, `dashboard-view.js`, `hand-control.js`, `hand-worker.js`, `capture.js`, `motorlab.css`, `mode-menu.css`.
  - Runtime offline MediaPipe (`vision/`): `vision_bundle.mjs`, `hand_landmarker.task` (FP16 v1, ~7.8 MB), `wasm/vision_wasm_internal.{js,wasm}`, `wasm/vision_wasm_nosimd_internal.{js,wasm}`, `LICENSE.txt`.
  - Cliente Python auxiliar: `keyboard_control.py`, `requirements.txt`, `README.md`, `.gitignore`.
- **Línea base V8 (`version-final-codigo-v8/`):** Idéntica en firmware (`src/main.cpp`, `include/*.h`, `platformio.ini`), `capture.js` y `keyboard_control.py`; carece de `hand-control.js`, `hand-worker.js`, `mode-menu.css` y `vision/`.
- **Otros directorios rastreados (esqueletos y pruebas históricas):**
  - `firmware/` (`platformio.ini`, `include/config.h`, `src/main.cpp`): stub inicial de arranque seguro (no controla motores).
  - `host/` (`pyproject.toml`, `src/bicopter_host/__init__.py`, `tests/test_smoke.py`): esqueleto de paquete Python (`pyserial>=3.5`, `numpy>=1.26`, `matplotlib>=3.8`, `pytest>=8.0`).
  - `control-tests/auto-height/`, `motor-tests/{arrow-control,gpio26-only,near-full-throttle}/`, `sensor-tests/{bno055,dual-usb,dual-usb-origin}/`, `docs/WIRING_AND_SAFETY.md`, `docs/worklogs/v0.1/worklog1.md`.

---

## 3. Auditoría Caja Blanca — Firmware ESP32 (`version-prueba-v9/`)
### 3.1 Plataforma y Dependencias (`platformio.ini`)
- `platform = espressif32@7.1.3`, `board = esp32dev`, `framework = arduino`, `monitor_speed = 115200`.
- `build_flags`: `-Wall -Wextra -DBNO_I2C_RESTART=0`.
- `lib_deps`: `pololu/VL53L0X@1.3.1`.

### 3.2 Pines GPIO, Periféricos y PWM
- **Bus I2C (`src/main.cpp`):** `Wire.begin(21, 22)` (`SDA=GPIO21`, `SCL=GPIO22`), `Wire.setClock(100000)` (100 kHz), `Wire.setTimeOut(50)` (50 ms).
- **IMU BNO055 (`0x28`, pin `ADD` a `GND`):**
  - `diagnostic::configure(0x28, false)` en `include/diagnostic.h`: reset por software (`reg 0x3F = 0x20`), espera `650 ms` + polling `reg 0x00 == 0xA0` (timeout `1200 ms`), modo energía normal (`0x3E = 0x00`), página 0 (`0x07 = 0x00`), modo fusión **`0x08` (IMUPLUS, 6-DOF accel+gyro; magnetómetro deshabilitado)**.
  - Lectura (`diagnostic::sample`): verifica registros de estado (`0x39`, `0x36`, `0x3A`, `0x35`) y realiza burst de 32 bytes desde `0x08` (`accel`, `mag` sin usar, `gyro`, `Euler`, `quaternion`). Valida finitud de todos los canales y norma cuadrática del cuaternión `0.5 < norm < 1.5`.
- **ToF VL53L0X (`0x29`):**
  - `initTof()`: verifica `reg 0xC0 == 0xEE`, configura `setTimeout(100)`, `setMeasurementTimingBudget(50000)` (50 ms) y `startContinuous(50)`.
  - `sampleTof()`: polling `reg 0x13` (`ready & 7`), lectura de 12 bytes desde `0x14` (`mm = (frame[10]<<8)|frame[11]`, `deviceStatus = (frame[0]&0x78)>>3`), limpieza de interrupción `0x0B = 1`. Timeout de datos listos: `1500 ms`. Acepta muestra solo si `mm < 8190 && deviceStatus == 11`.
- **ESCs (`include/controller.h`):**
  - Canales LEDC `0` (`GPIO 25`, motor izquierdo) y `1` (`GPIO 26`, motor derecho) a **`50 Hz`**, resolución **`16 bits`** (`65536` cuentas / `20000 µs`).
  - Mapeo `pulseCounts(percent)`: `pulseUs = 1000 + 1000 * (percent / 100)`, redondeo hacia arriba `ceilf(pulseUs * 65536 / 20000)`. Rango permitido: `0%` (`1000 µs`) a `MAX_PERCENT = 99%` (`1990 µs`).

### 3.3 Calibración, Filtrado y Fórmulas de Estado
- **Cero de altura (`control::distance(mm)`):** Al iniciar, acumula `30` muestras válidas consecutivas de ToF cuya dispersión `originMax - originMin <= 10 mm` (si excede, reinicia contador). Fija `origin = originSum / 30` y emite `STATE,READY`.
- **Altura:** `height = HEIGHT_SIGN * HEIGHT_SCALE * (mm - origin)` con `HEIGHT_SIGN = -1.0f`, `HEIGHT_SCALE = 10.0f` (calibración empírica documentada: desplazamiento crudo de `9` -> `90 mm` físicos).
- **Ángulo:** `USE_ROLL = true`, `ANGLE_SIGN = 1.0f`. `mapEuler` toma `roll_y` (reg `0x1C..0x1D`, `/ 16.0f` en °). Al armar (`control::start`), captura `angleOrigin = rawAngle()`. La variable controlada es `angle() = rawAngle() - angleOrigin`.
- **Velocidades (filtro EMA sobre derivada discreta en `tick()`):**
  - `velocity = 0.7f * velocity + 0.3f * (height - previousHeight) / dt`
  - `angularVelocity = 0.7f * angularVelocity + 0.3f * (angle() - previousAngle) / dt`

### 3.4 Lazo de Control, Máquina de Estados y Seguridad (`control::tick()`)
- **Frecuencia y `dt`:** Periodo mínimo `50 ms` (`20 Hz` nominal). `dt = (now - lastTick) / 1000.0f` (inicial `0.05f`). Para limitar rampas si hubo retraso en I2C, usa `outputDt = fminf(dt, 0.05f)`.
- **PID (`struct PID`):**
  - `P = kp * error`, `D = -kd * rate` (derivada sobre medición filtrada).
  - `candidate = constrain(integral + ki * error * dt, -40.0f, 40.0f)`. Anti-windup local: solo actualiza `integral = candidate` si `fabsf(raw) < 40 || raw * error < 0`. Salida acotada a `[-40, 40]`.
  - Validación al configurar/armar: ganancias finitas en `[0, 100]` y `kp > 0` obligatorio en ambos ejes.
- **Mixer motor izquierdo / derecho (`Power::PID`):**
  - `common = BASE_PERCENT (58.0f) + heightPid.step(target - height, velocity, dt)` (base `1580 µs`).
  - `diff = MIX_SIGN (1.0f) * anglePid.step(angleTarget - angle(), angularVelocity, dt)`.
  - `l = common - diff`, `r = common + diff`.
  - Aplicado con limitación de pendiente `gradualOutputs(l, r, CONTROL_RATE=20.0f, outputDt)` (`±20%/s` = `±200 µs/s` por motor).
  - **Anti-windup acoplado por saturación/slew:** Tras aplicar `gradualOutputs`, calcula `residualL = l - left`, `residualR = r - right`. Congela `heightPid.integral` si `(newH - oldH)*(residualL + residualR) > 0` y `anglePid.integral` si `MIX_SIGN*(newA - oldA)*(residualR - residualL) > 0`.
- **Máquina de estados (`Power`):**
  - `Off` (`0%` / `1000 µs`) -> `Ramp` (al armar: sube ambos motores a `START_PERCENT = 45%` / `1450 µs` a `START_RATE = 45%/s`, ~1 s) -> `Standby` (`READY`, si `target == 0` mantiene `45%`) o `PID` (si `target != 0`) -> `Down` (cuando `target == 0`: limpia integrales y baja a `0%` a `20%/s`) -> `Off`.
- **Watchdogs (`checkRunningLimits`):**
  - Sensores (`fresh()`): exige `originReady && imuValid && tofValid && (now - imuTime < 200) && (now - tofTime < 200)` -> si falla, `stop("SENSOR_INVALID_OR_STALE")`.
  - Comunicación: si `now - lastHB > 350 ms` -> `stop("LINK_TIMEOUT")`.

### 3.5 Protocolo Serial Exacto (`115200` baud, `\n`, buffer máx. 159 bytes)
- **Comandos RX (Host -> ESP32):**
  - `STOP`: paro inmediato (`STATE,STOP,USER`).
  - `HB`: refresca `lastHB`.
  - `ARM`: arma en `Manual` con `h=0, a=0` usando ganancias ya cargadas.
  - `START,<MANUAL|AUTO>,<h>,<a>,<hKp>,<hKi>,<hKd>,<aKp>,<aKi>,<aKd>`: valida sensores, `kp > 0`, ganancias `[0..100]`, y en `AUTO` exige `h != 0`.
  - `TARGET,<h>,<a>`: actualiza consignas en modo `AUTO` armado (`h == 0` pasa a `Power::Down`). Responde `ACK,TARGET`.
  - `U` / `D` / `L` / `R`: solo `MANUAL` armado; `target ±= 10` (`target == 0` pasa a `Power::Down`), `angleTarget ±= 1`; también refresca `lastHB`.
  - `PID,<H|A>,<kp>,<ki>,<kd>`: solo desarmado; responde `ACK,PID`.
- **Telemetría TX (ESP32 -> Host, ~20 Hz):**
  - `CTRL,<ms>,<armed>,<originReady>,<height>,<target>,<angle>,<angleTarget>,<left_pct>,<right_pct>,<fresh>,<IDLE|AUTO|MANUAL>,<OFF|RAMP|READY|PID|DOWN>,<rawAngle>` (14 campos).
  - `IMU,<ts_ms>,<roll>,<pitch>,<yaw>,<gx>,<gy>,<gz>,<ax>,<ay>,<az>,<cal_sys>,<cal_gyro>,<cal_accel>,<cal_mag>,<OK|INVALID>` (16 campos).
  - `TOF,<ts_ms>,<mm|NA>,<status>,<deviceStatus|NA>` (5 campos).
  - Eventos: `STATE,READY`, `STATE,ARMED`, `STATE,STOP,<reason>`, `ACK,TARGET`, `ACK,PID`, `ERR,<clave>`, `# <diag>`.

---

## 4. Auditoría Caja Blanca — Host, UI y Scripts (`version-prueba-v9/`)
- **Dashboard Web Serial (`dashboard.html`, `dashboard.js`, `dashboard-view.js`):**
  - Menú inicial de 3 modos (`GESTURE`, `MANUAL`, `AUTO`). Conexión Web Serial a `115200` baud (`Chrome`/`Edge` escritorio).
  - Sliders + inputs numéricos para ganancias PID (`[0..100]`, default `0`) y consignas (`h` slider `[-250, 250]` auto-escalable, `a` slider `[-90, 90]`).
  - Osciloscopio Canvas de últimos `15 s` (`Altura`, `Ángulo`, `Objetivo mm`, `Objetivo °`), dial angular con ticks cada `5°`, indicadores PWM en `%` y `µs`.
  - Lazo de `100 ms` (`setInterval`): verifica `HandControl.checkAge()`, envía `HB` mientras está armado y en pestaña activa/enfocada; en modo `GESTURE` envía `TARGET,<h>,<a>` cada vez que cambia la consigna de la mano.
  - Paro automático (`STOP`) ante: `Esc`, `Space` (si armado), `blur`, `pagehide`, `visibilitychange` (`hidden`), pérdida de frescura (`> 300 ms`), o pérdida de palma (`HandControl.onLoss`).
  - Cola `manualSteps` en `dashboard.js`: descarta pulsaciones de flecha retenidas `>= 250 ms` si hubo stall USB.
- **Control por Gestos (`hand-control.js`, `hand-worker.js`, `vision/`):**
  - Captura cámara frontal (`640x480 @ 24 fps`) vía `MediaStreamTrackProcessor({maxBufferSize: 1})` y ejecuta inferencia MediaPipe `HandLandmarker` (`numHands: 2`) en Web Worker separado (`hand-worker.js`) para no bloquear `USB`/`STOP`.
  - Criterios de palma válida (`accepted`): exactamente 1 mano detectada, `score >= 0.75`, `facingCamera()` (producto cruz `wrist->indexMCP x wrist->pinkyMCP` > `0.55 * |n|`, ajustado por lateralidad), y `|angle| < 85°`.
  - Consigna vertical: promedio `y` de puntos `[0, 5, 9, 13, 17]`; si `y < 0.42` suma `+10 mm` cada `250 ms`; si `y > 0.58` resta `-10 mm` cada `250 ms`; dentro de `[0.42, 0.58]` mantiene altura. Inicia en `0 mm` cada vez que adquiere la palma.
  - Consigna angular: `atan2` muñeca-MCP medio (`[0]` a `[9]`), banda muerta `< 3°`, clamp `[-20°, +20°]`, suavizado exponencial `tau = 75 ms`, redondeado a entero.
  - Timeout de imagen (`maxAge = 500 ms`) o pérdida de palma -> `resetPose()` -> `onLoss()` -> `STOP`.
- **Logger CSV (`capture.js`):**
  - Graba en memoria y exporta `rail-identification-<ISO>.csv` (BOM UTF-8, 22 columnas). Incluye fila `META` con parámetros físicos declarados (`mass_kg: 0.4`, `arm_each_m: 0.075`, `com_offset_toward_gpio26_m: 0.01`, `hover_us_each: 1580`, `height_scale: 10`) y marcadores `MARK` (`BASELINE`, `HEIGHT`, `ANGLE`, `RECOVERY`).
- **Cliente Python (`keyboard_control.py`):**
  - GUI Tkinter + `pyserial` (`115200` baud). Usa comandos `PID`, `ARM` (Manual `0,0`), `U/D/L/R` y `STOP`. Polling cada `100 ms`; envía `HB` si tiene foco, `STOP` si pierde foco o `last_rx > 1 s`.

---

## 5. Análisis Crítico y Recomendaciones para Lab
1. **Ausencia de topes de seguridad en firmware (Riesgo Físico Alto):** A diferencia de `firmware/include/config.h` (`ANGLE_CUTOFF_DEG = 55°`, `RAIL_MIN_MM = 0`, `RAIL_MAX_MM = 230`, `PWM_ABS_LIMIT_US = 1500`), el firmware V8/V9 permite `MAX_PERCENT = 99%` (`1990 µs`) y consignas sin límite (`validTarget` solo valida `isfinite`). Un error de signo o ganancia excesiva puede llevar el carro contra el tope mecánico o volcar el brazo a >55° sin corte automático. **Recomendación:** Agregar corte inmediato (`stop("LIMIT_EXCEEDED")`) si `|angle()| > 55°` o `height` excede el recorrido físico del riel, y acotar `MAX_PERCENT` según límite seguro de prueba.
2. **`delay()` bloqueante en `initImu()` (Riesgo Medio):** `diagnostic::configure()` bloquea el `loop()` ~`775 ms` (hasta `~1975 ms` en timeout) con `delay()`. Aunque un fallo de comunicación desarma antes por `fresh()` (`200 ms`), en arranque o reconexión congela el puerto serial y la telemetría.
3. **Calibración `HEIGHT_SCALE = 10`:** El VL53L0X entrega milímetros directamente (`mm`), por lo que multiplicar `(mm - origin)` por `10` implica que `1 mm` medido por el sensor se reporta como `10` unidades en `height` (el comentario indica que un desplazamiento crudo de `9` correspondió a `90 mm` físicos). **Recomendación:** Verificar con regla física antes de cerrar el lazo de altura para confirmar que `Kp/Ki/Kd` correspondan a la escala real.
4. **Uso exclusivo de `MediaStreamTrackProcessor` en `hand-control.js`:** API soportada en Chrome/Edge de escritorio (coincide con Web Serial), pero no en Firefox/Safari.
5. **Desfase documental I2C:** `docs/WIRING_AND_SAFETY.md` documenta `400 kHz`, mientras `src/main.cpp` opera a `100 kHz` (preferible mantener `100 kHz` en protoboard por robustez eléctrica).
6. **Flujo de armado en Modo Gestos:** Exige acumular altura `!= 0` con la palma antes de habilitar **Armar con gestos**, y el `START` arranca directamente en `AUTO` con la altura actual de la palma como primer objetivo. Verificar siempre con `kp` conservador y sin hélices en primera prueba.

---

## 6. Verificación Focalizada
- **Archivos Modificados:** `docs/worklogs/v2.0/worklog1.md` — auditoría completa de `version-final-opcional`.
- **Verificación Ejecutada:** `git log -1 --stat` -> `HEAD` en `version-final-opcional` (`548022ef2b1466a16ce9500c5ddc6e06fcdb0139`, `"Publica la V9 opcional con control por gestos y flechas manuales"`).
- **Acción Usuario (Human Gate):** Ninguna (solo recordar que tus cambios locales previos de `main` quedaron respaldados en `git stash@{0}` por si deseas recuperarlos después).
