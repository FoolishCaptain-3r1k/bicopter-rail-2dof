# Worklog 7 (v2.0) | Prev: [[worklog6]]
- **Estado:** PASS
- **Invariantes Cubiertos:** Creación del servidor puente SSE sin dependencias externas (`version-prueba-v9/dsp_live_server.py` en `127.0.0.1:8090`) y visualizador DSP en tiempo real (`version-prueba-v9/dsp_live.html` en Canvas vanilla 60 fps); validación sintáctica Python + JS; daemon persistente coexistiendo con el servidor de `dashboard.html` en `8080`; prueba en vivo de endpoints y ráfaga demo en Microsoft Edge.

---

## 1. Contratos y Endpoints del Servidor SSE (`127.0.0.1:8090`)
- **`GET /` y `GET /dsp_live.html`:** Sirve `version-prueba-v9/dsp_live.html` con `Cache-Control: no-store`.
- **`GET /events` (`text/event-stream`):** Stream SSE con keepalive cada `15 s` y reconexión automática. Al conectar un cliente nuevo, emite inmediatamente `event: snapshot` con `stage` actual, buffer reciente (últimas `300` muestras) y `results` acumulados.
- **`POST /api/sample`:** Recibe JSON `{t, raw_h, filt_h, ref_h, raw_a, filt_a, pwm_l, pwm_r}`, almacena en `deque(maxlen=300)` y difunde `event: sample`.
- **`POST /api/stage`:** Recibe JSON `{filter_name, phase, note}` (`CAPTURANDO | ANALIZANDO | FLASHEANDO | COMPLETADO | DEMO`) y difunde `event: stage`.
- **`POST /api/result`:** Recibe JSON `{filter_name, order, fc_hz, std_mm, p2p_mm, lag_ms, rmse_mm, smoothness_score, winner}`, actualiza la tabla comparativa (resaltando el ganador) y difunde `event: result`.
- **`POST /api/reset`:** Limpia el buffer de gráficas (opcionalmente `{"clear_results": true}`) y difunde `event: reset`.
- **`POST /api/demo` (y flag CLI `--demo`):** Ejecuta en hilo dedicado una ráfaga sintética de `6 s` (`20 Hz`, onda senoidal `0.35 Hz` + picos impulsivos `±10 mm` + señal filtrada `Median3+EMA` + fila de resultado) para probar el tablero sin hardware.

---

## 2. Visualizador en Vivo (`version-prueba-v9/dsp_live.html`)
- Banner superior con nombre del filtro activo, insignia de fase codificada por color, estado SSE, contador de muestras, tasa `Hz` y botones rápidos (`Ejecutar Demo 6 s`, `Limpiar Gráficas`).
- 5 KPIs en vivo: `STD Ruido (ToF Crudo)`, `STD Altura Filtrada`, `Error Actual (Ref − Filt)`, `Ángulo (Filt / Crudo)` y `PWM ESC (GPIO25 / 26)`.
- Dos gráficas Canvas a 60 fps (`ventana deslizante 15 s`):
  1. **Altura:** `ToF Crudo` (rojo translúcido), `Altura Filtrada` (cian sólido) y `Referencia Senoidal` (ámbar punteado).
  2. **Ángulo y PWM:** `Ángulo Crudo` vs `Ángulo Filt` (`°`, eje izquierdo) y `PWM 25` / `PWM 26` (`%`, eje derecho).
- Tabla comparativa acumulada en vivo con resaltado verde en el filtro ganador (`winner: true`).

---

## 3. Verificación Focalizada
- **Archivos Modificados:**
  - `version-prueba-v9/dsp_live_server.py` — servidor puente SSE (`ThreadingHTTPServer` stdlib).
  - `version-prueba-v9/dsp_live.html` — tablero DSP en vivo (HTML/CSS/Canvas vanilla).
  - `docs/worklogs/v2.0/worklog7.md` — documentación de endpoints y verificación.
- **Verificación Ejecutada:**
  - `.\.venv\Scripts\python.exe -m py_compile version-prueba-v9\dsp_live_server.py` + `node --check` sobre JS extraído -> `SYNTAX_OK`.
  - `Get-NetTCPConnection -LocalPort 8080,8090 -State Listen` -> `127.0.0.1:8090 Listen (PID 10164)` y `127.0.0.1:8080 Listen (PID 30016)`.
  - `GET /dsp_live.html` -> `200`, `POST /api/sample` -> `200`, `POST /api/result` -> `200`, `POST /api/demo` -> `200`.
  - Microsoft Edge abierto en `http://localhost:8090/dsp_live.html` animando la ráfaga demo de `6 s`.
- **Acción Usuario (Human Gate):** Ninguna; el visualizador DSP en vivo quedó listo en `http://localhost:8090/dsp_live.html` para recibir la mega-directiva.
