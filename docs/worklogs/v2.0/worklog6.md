# Worklog 6 (v2.0) | Prev: [[worklog5]]
- **Estado:** PASS
- **Invariantes Cubiertos:** Estado base limpio de `version-prueba-v9` (`20 Hz`, protocolo `CTRL`/`IMU`/`TOF` intacto, sin `kalman_altitude.h`); filtrado digital en firmware (`median3 + EMA` en VL53L0X, `EMA` ligero en BNO055) y banda muerta continua en error de altura; compilación y flasheo exitoso en `COM4`; reducción cuantitativa real de ruido (`std` `-72.0%`, `p2p` `-67.9%`); `COM4` liberado y servidor HTTP activo en `127.0.0.1:8080` (`HTTP 200`).

---

## 1. Constantes y Cambios de Firmware (`version-prueba-v9/`)
- **`version-prueba-v9/include/controller.h`:**
  - Constantes configurables añadidas en `namespace control`:
    - `TOF_LPF_ALPHA = 0.30f`
    - `ANGLE_LPF_ALPHA = 0.70f`
    - `HEIGHT_DEADBAND_MM = 2.0f` (`deadbandUnits = HEIGHT_DEADBAND_MM * HEIGHT_SCALE = 20.0f` unidades)
  - **Cadena ToF (`control::distance(float mm)`):**
    - Buffer circular de 3 muestras + `median3(a, b, c)` para rechazar picos aislados sin retraso de fase.
    - Calibración de `origin` preservada (30 muestras consecutivas con dispersión `<= 10 mm`, emitiendo `STATE,READY`) e inicialización directa `tofFilteredMm = origin` al completarse `originReady` (cero transitorio inicial).
    - Pasa-bajos EMA firme: `tofFilteredMm = TOF_LPF_ALPHA * mmMed + (1.0f - TOF_LPF_ALPHA) * tofFilteredMm`; `height = HEIGHT_SIGN * HEIGHT_SCALE * (tofFilteredMm - origin)`.
  - **Filtro Ángulo BNO055 (`control::updateImu(const ImuSample& s)`):**
    - Inicializa `angleFiltered = rawAngle()` en la primera muestra válida y luego aplica `angleFiltered = ANGLE_LPF_ALPHA * raw + (1.0f - ANGLE_LPF_ALPHA) * angleFiltered`.
    - `control::start()` captura `angleOrigin` desde `angleFiltered`, y `angle()` devuelve `angleFiltered - angleOrigin` (mientras `CTRL` sigue reportando `rawAngle()` en el campo 14).
  - **Banda muerta continua en error de altura (`control::tick()` en `Power::PID`):**
    - Si `fabsf(heightErr) <= deadbandUnits`, `heightErr = 0.0f`; en caso contrario `heightErr -= copysignf(deadbandUnits, heightErr)` (sin escalón al salir de la banda muerta).
- **`version-prueba-v9/src/main.cpp`:**
  - `sampleImu()` invoca `control::updateImu(s)` cuando `s.valid` es verdadero.

---

## 2. Compilación y Flasheo en `COM4`
- **Comando:** `C:\Users\Ruiza\.platformio\penv\Scripts\pio.exe run -d version-prueba-v9 -t upload --upload-port COM4`
- **Resultado:** **`[SUCCESS]`** (`20.20 s`, cero warnings).
- **Memoria:** RAM `6.8%` (`22344 / 327680 bytes`), Flash `25.5%` (`333897 / 1310720 bytes`).

---

## 3. Comparativa Cuantitativa Crudo vs Filtrado (`COM4` @ `115200` baud, 6 s post-`STATE,READY`)
Captura real sin armar motores (`462` líneas totales, `STATE,READY=True`, `IMU_OK=178`, `TOF_POST=62`, `CTRL_POST=119`, `deviceStatus=[11]`, motores `0.00%` / `OFF`; puerto `COM4` cerrado al terminar):

| Señal | Media | Desviación estándar (`std`) | Pico a pico (`p2p`) | Reducción vs Crudo |
| :--- | :---: | :---: | :---: | :---: |
| **ToF crudo (`distance_mm`)** | `139.774 mm` | `1.237 mm` (`12.368` u. x10) | `5.000 mm` (`50.000` u. x10) | Referencia |
| **Altura filtrada (`height`)** | `2.106` u. (`0.211 mm`) | **`3.457` u. (`0.346 mm`)** | **`16.070` u. (`1.607 mm`)** | **`std -72.0%` · `p2p -67.9%`** |
| **Ángulo crudo (`rawAngle`)** | `88.690°` | `0.000°` | `0.000°` | Referencia |
| **Ángulo filtrado (`angle`)** | `88.690°` | `0.000°` | `0.000°` | Sin saltos / estable |

Últimas 2 tramas `CTRL` verificadas:
```text
CTRL,10401,0,1,0.08,0.00,88.69,0.00,0.00,0.00,1,IDLE,OFF,88.69
CTRL,10451,0,1,0.15,0.00,88.69,0.00,0.00,0.00,1,IDLE,OFF,88.69
```

- **Nota de prueba:** El ruido pico a pico filtrado (`1.607 mm`) queda completamente contenido dentro de la banda muerta continua de `±2.0 mm` (`±20` unidades), evitando que el lazo PID persiga ruido residual al estacionarse en `H_mid` durante **Críticamente amortiguado** y **Sobreamortiguado**.

---

## 4. Verificación Focalizada
- **Archivos Modificados:**
  - `version-prueba-v9/include/controller.h` — `TOF_LPF_ALPHA`, `ANGLE_LPF_ALPHA`, `HEIGHT_DEADBAND_MM`, `median3`, `updateImu`, filtrado ToF/IMU y banda muerta continua en `Power::PID`.
  - `version-prueba-v9/src/main.cpp` — llamada a `control::updateImu(s)`.
  - `docs/worklogs/v2.0/worklog6.md` — documentación y métricas reales.
- **Servidor HTTP y Edge:** `127.0.0.1:8080 Listen` (`PID 30016`), `Invoke-WebRequest http://127.0.0.1:8080/dashboard.html` -> `200`, `COM4` libre para Web Serial en Microsoft Edge.
- **Acción Usuario (Human Gate):** En Edge (`http://localhost:8080/dashboard.html`), reconectar `COM4`, capturar el tope de `20 cm` y probar las 4 rutinas de amortiguamiento con el nuevo filtrado activo.
