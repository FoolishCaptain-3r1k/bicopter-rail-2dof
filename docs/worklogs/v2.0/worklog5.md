# Worklog 5 (v2.0) | Prev: [[worklog4]]
- **Estado:** PASS
- **Invariantes Cubiertos:** Auditoría caja blanca de `include/controller.h` y `src/main.cpp` (sin cambios al firmware); panel `#autoPanel` de 4 rutinas de amortiguamiento en 1 clic con ángulo fijo en `0°`; calibración de tope físico `20 cm` con reescalado automático de ganancias PID invariante a `HEIGHT_SCALE=10`; generador senoidal a `100 ms` acotado estrictamente a `[15%, 85%]` (jamás `0`) y limpieza total en todos los eventos de paro.

---

## 1. Auditoría Caja Blanca del Firmware (`version-prueba-v9/`)
Se verificó en `include/controller.h` y `src/main.cpp` que **no se requiere modificar ni reflashear el firmware**:

1. **Relación ToF crudo -> `height` / `target` / `velocity`:**
   - `sampleTof()` lee `mm = (frame[10] << 8) | frame[11]` (milímetros crudos del VL53L0X) y llama a `control::distance(mm)`.
   - `control::distance()` fija `origin` como el promedio de 30 muestras consecutivas con dispersión `<= 10 mm` y calcula:
     `height = HEIGHT_SIGN * HEIGHT_SCALE * (mm - origin) = -10.0f * (mm - origin)`
   - Al subir el carro hacia el sensor superior, `mm` disminuye (`mm - origin < 0`), por lo que `height > 0`.
   - `velocity` es la derivada filtrada (EMA `0.7 / 0.3`) en unidades de `height / s`. Si `20 cm` físicos corresponden a `20` cuentas crudas (`height = 200`) o a `200` cuentas crudas (`height = 2000`), tanto `error = target - height` como `velocity` escalan linealmente con `topeReal`.
2. **Transición `START,AUTO` -> `Ramp` -> `PID`:**
   - `START,AUTO,<h>,0,...` (con `h != 0` y `Kp > 0`) arma el sistema en `Power::Ramp`: sube ambos ESC de `0%` (`1000 µs`) a `START_PERCENT = 45%` (`1450 µs`) a `45%/s` (~`1 s`).
   - Al alcanzar `45%` con `target != 0`, pasa a `Power::PID`: `common = BASE_PERCENT (58%) + heightPid.step(...)`, `diff = anglePid.step(...)`, saturación PID individual en `[-40, +40]%` y rampa máxima por motor `CONTROL_RATE = 20%/s` (`200 µs/s`).
3. **Actualización dinámica `TARGET,<h>,0` cada `100 ms`:**
   - `TARGET,<h>,0` actualiza `target` y `angleTarget` **sin reiniciar** `heightPid.integral` ni `anglePid.integral`.
   - No refresca `lastHB` (`LINK_TIMEOUT = 350 ms`), por lo que el lazo de `100 ms` en `dashboard.js` envía siempre `HB` primero y luego `TARGET,<h>,0` solo tras confirmar `row.power === 'PID'`.
   - `h == 0` dispara `Power::Down`; el generador senoidal acota `h(t)` estrictamente a `[max(1, 0.15 * top), 0.85 * top]`.

---

## 2. Justificación Matemática de las 4 Rutinas (Invariantes al Escalado ToF)
Las ganancias de altura se definen para una referencia nominal `topeRef = 200` ($H_{\text{mid}} = 100$) y se reescalan automáticamente por `scale = 200 / topeReal` (`computeRoutineGains()`). Así, el impulso proporcional inicial $P_0 = K_p \cdot H_{\text{mid}}$ y el frenado derivativo $D = -K_d \cdot v$ producen **exactamente el mismo porcentaje PWM** sea cual sea el `topeReal` capturado (`200`, `1000`, `2000`, etc.), garantizando que nunca se sature `±40%` en el escalón inicial y dejando margen debajo de `MAX_PERCENT = 99%` para nivelación angular.

- **Nivelación angular fija en las 4 rutinas (`angleTarget = 0°`):** `AKp = 0.35`, `AKi = 0.02`, `AKd = 0.08` (aporta `±3.5%` diferencial a `10°` de inclinación).

| Rutina | Referencia | `HKp` (`top=200`) | `HKi` (`top=200`) | `HKd` (`top=200`) | $P_0$ inicial (`%` PWM) | Comportamiento esperado |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **1. No amortiguado** | $h(t) = H_{\text{mid}} + 0.30\,\text{top}\sin(2\pi f t)$, $f \in [0.15, 0.80]\text{ Hz}$ (def. `0.35 Hz`) | `0.24` | `0.01` | `0.00` | `+24%` (`82%` total) | Oscilación continua acotada a `[20%, 80%]` del riel (`[40, 160]` para `top=200`), `Kd=0`. |
| **2. Subamortiguado** | Escalón fijo a $H_{\text{mid}}$, `0°` | `0.28` | `0.06` | `0.02` | `+28%` (`86%` total) | $\zeta \approx 0.25\text{–}0.35$: sobreimpulso claro y 2–3 oscilaciones amortiguadas sin golpear el tope. |
| **3. Críticamente amortiguado** | Escalón fijo a $H_{\text{mid}}$, `0°` | `0.18` | `0.025` | `0.10` | `+18%` (`76%` total) | $\zeta \approx 1.0$: relación $K_d/\sqrt{K_p}$ 6.2× mayor que subamortiguado; subida rápida sin rebote. |
| **4. Sobreamortiguado** | Escalón fijo a $H_{\text{mid}}$, `0°` | `0.10` | `0.008` | `0.18` | `+10%` (`68%` total) | $\zeta \approx 1.5\text{–}2.0$: ascenso lento y suave hasta $H_{\text{mid}}$ sin sobreimpulso. |

---

## 3. Archivos y Funciones Modificadas
- **`version-prueba-v9/dashboard.html`:** Se añadió `<section class="card auto-panel" id="autoPanel" hidden>` en la zona superior (sin scroll) dentro de `Control automático`, con `#railTop`, `#sineFreq`, `#captureTop`, `#autoCalSummary`, `#autoRoutineStatus` y los 4 botones `[data-routine]`.
- **`version-prueba-v9/motorlab.css`:** Estilos `.auto-panel`, `.auto-panel-head`, `.auto-cal`, `.auto-field`, `.auto-summary`, `.routine-grid`, `.routine-btn` (con estado `.active` y diseño responsivo).
- **`version-prueba-v9/dashboard.js`:**
  - Constantes `ANGLE_LEVEL_GAINS`, `AUTO_ROUTINES` y estado `activeRoutine`.
  - `getRailGeometry()`, `computeRoutineGains()`, `setInputWithSync()`, `clearActiveRoutine()`, `launchRoutine(id)`.
  - Sincronización en `render()` (visibilidad, resumen en vivo de `H_mid` y rangos, habilitación de `#captureTop` y botones `[data-routine]`).
  - Integración del generador senoidal en el `setInterval` de `100 ms` tras `await send(s, 'HB')` y `s.sample.power === 'PID'`.
  - Limpieza garantizada (`clearActiveRoutine()`) en `stop()`, `closePort()`, `STATE,STOP`, `ERR,` (desarmado) y `#backToMenu`.

---

## 4. Procedimiento de Calibración (`20 cm`) y Operación en 1 Clic
1. Abrir `http://localhost:8080/dashboard.html` en Microsoft Edge -> elegir **Automático** -> pulsar **Conectar por USB** -> seleccionar `COM4`.
2. Mantener el carro abajo e inmóvil `~2–3 s` hasta que el estado indique **"Listo · calibra el tope de 20 cm o haz clic en cualquiera de las 4 rutinas."** (`originReady=1`).
3. **Calibración del tope (desarmado):** Levantar manualmente el carro hasta el tope superior (`20 cm`) y pulsar **Capturar tope (20 cm)** (o editar `#railTop` a mano). Verificar en pantalla `H_mid` y el rango senoidal `[H_min, H_max]`. Bajar el carro al piso.
4. **Ejecución en 1 clic:** Hacer clic en cualquiera de los 4 botones (**No amortiguado**, **Subamortiguado**, **Críticamente amortiguado** o **Sobreamortiguado**). El panel carga las ganancias reescaladas, fija `H_mid` y `0°`, y envía `START,AUTO,...` automáticamente.
5. **Paro inmediato:** Pulsar **■ PARO**, `Esc` o `Espacio` detiene motores y generador senoidal al instante y deja los 4 botones listos para la siguiente rutina.

---

## 5. Verificación Focalizada
- **Sintaxis JS:** `node --check version-prueba-v9\dashboard.js` -> `exit 0`.
- **Comprobación matemática (Node):** Validado para `top = 50, 200, 1000, 2000` y `f = 0.15, 0.35, 0.80 Hz` -> `ALL_MATH_CHECKS_PASSED` (`P0 < 40%` siempre, ganancias en `[0.001..100]`, trama `START` `< 159` bytes, `h(t)` estrictamente dentro de `[15%, 85%]` y `> 0`).
- **Servidor HTTP y Edge:** `127.0.0.1:8080 Listen` (`PID 30016`, `IsDaemon=true`), `Invoke-WebRequest http://127.0.0.1:8080/dashboard.html` -> `200`, Microsoft Edge abierto.
- **Acción Usuario (Human Gate):** En Edge (`Control automático`), conectar `COM4`, capturar el tope de `20 cm` con el carro arriba (desarmado), bajar el carro y probar las 4 rutinas en 1 clic.
