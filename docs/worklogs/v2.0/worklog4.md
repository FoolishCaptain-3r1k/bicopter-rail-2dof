# Worklog 4 (v2.0) | Prev: [[worklog3]]
- **Estado:** PASS
- **Invariantes Cubiertos:** Diagnóstico completo del bloqueo percibido en modo `MANUAL` (`"Desarmado · tomando cero de altura"`, botón `Armar manual` fuera del viewport superior y ganancias PID en `0`); corrección mínima en `version-prueba-v9/dashboard.html` y `dashboard.js`; validación sintáctica JS y recarga en Edge sobre `http://localhost:8080/dashboard.html`.

---

## 1. Diagnóstico (Causa Exacta)
1. **Estado `"Desarmado · tomando cero de altura"` (`dashboard.js` L48-50 + `controller.h` L79-89):**
   - Al abrir el puerto Web Serial, el ESP32 se reinicia y `control::distance()` requiere **30 muestras consecutivas** de VL53L0X con dispersión `originMax - originMin <= 10 mm` (`~1.5–3 s` con el riel inmóvil) antes de emitir `STATE,READY` (`originReady = 1`).
   - Mientras `originReady == 0`, `fresh()` retorna `false` (`row.valid == 0`), por lo que `#start` (`Armar manual`) y `#directionPad` (flechas) permanecen deshabilitados. Si el riel se mueve o el ToF no recibe lecturas válidas (`< 8190` y `deviceStatus == 11`), el cero no se completa.
2. **Botón `Armar manual` y campos PID ocultos bajo el osciloscopio (`dashboard.html` L78-87, L144-153):**
   - En modo `MANUAL`, `#manualPanel` (arriba) solo mostraba el texto y el pad de flechas (`#directionPad`), mientras el botón `#start` (`Armar manual`) y `#loops` (`PID de altura` y `PID de rotación`) quedaban al final de la página debajo de `.scope` (`min-height: 500px`).
3. **Ganancias PID por defecto en `0` (`dashboard.js` L20-23):**
   - Todos los inputs (`HKp`, `HKi`, `HKd`, `AKp`, `AKi`, `AKd`) iniciaban en `0`. Como `controller.h` (`control::start`) y `dashboard.js` L230 exigen `Kp > 0` en ambos ejes, pulsar `Armar manual` sin bajar a editarlos arrojaba `ERR` / `"Introduce un Kp positivo para cada eje."`.

---

## 2. Corrección Aplicada (`version-prueba-v9/`)
- **`dashboard.html`:** Se agregó dentro de `#manualPanel` (visible arriba junto al pad de flechas) el indicador de estado `#manualStatus` y el botón primario `#manualArm` (`Armar manual`).
- **`dashboard.js`:**
  - Ganancias PID inicializadas por defecto con valores conservadores seguros (`Kp > 0`): `HKp = 0.05`, `HKi = 0`, `HKd = 0.02` y `AKp = 0.30`, `AKi = 0`, `AKd = 0.05` (sincronizados automáticamente con los sliders en `dashboard-view.js`).
  - `render()` actualiza `#manualArm.disabled` en sincronía con `#start.disabled` y muestra en `#manualStatus` el progreso exacto del cero ToF / sensores / armado.
  - `#manualArm.onclick` dispara `#start.click()` enviando `START,MANUAL,0,0,<ganancias>`.

---

## 3. Cómo Operar el Armado en `Control manual`
1. En Edge (`http://localhost:8080/dashboard.html`), seleccionar **Manual** -> pulsar **Conectar por USB** -> elegir `COM4`.
2. Mantener el riel abajo e inmóvil `~2–3 s` hasta que `#manualStatus` cambie de *"Tomando cero de altura..."* a **"Sensores y cero listos · pulsa Armar manual."** (y se habilite **Armar manual**).
3. Opcionalmente ajustar `Kp/Ki/Kd` abajo (ya vienen precargados `H: 0.05 / 0 / 0.02` y `A: 0.30 / 0 / 0.05`).
4. Pulsar **Armar manual**: el ESP32 sube ambos ESC a `1450 µs` en `1 s` y habilita inmediatamente las flechas en pantalla y teclado (`↑/↓` ±10 mm, `←/→` ±1°, `Esc` o `Espacio` para **PARO**).

---

## 4. Verificación Focalizada
- **Archivos Modificados:**
  - `version-prueba-v9/dashboard.html` — `#manualStatus` y `#manualArm` en `#manualPanel`.
  - `version-prueba-v9/dashboard.js` — `defaultGains`, sincronización de `#manualArm`/`#manualStatus` en `render()` y click handler.
- **Verificación Ejecutada:**
  - `node --check version-prueba-v9\dashboard.js` -> `exit 0` (sin errores de sintaxis).
  - `Get-NetTCPConnection -LocalPort 8080 -State Listen` -> `127.0.0.1:8080 Listen (PID 14960)`.
  - `Invoke-WebRequest http://127.0.0.1:8080/dashboard.html` -> `200`.
  - `Start-Process msedge.exe "http://localhost:8080/dashboard.html"` -> abierto/recargado en Edge.
- **Acción Usuario (Human Gate):** Refrescar o usar la pestaña abierta en Edge, conectar `COM4`, esperar 2-3 s al cero de altura y pulsar **Armar manual**.
