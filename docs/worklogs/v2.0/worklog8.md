# Worklog 8 (v2.0) | Prev: [[worklog7]]
- **Estado:** PASS
- **Invariantes Cubiertos:** Solución definitiva al failsafe de ESCs mediante cambio de filtro en tiempo de ejecución (`FILTER,0..4`) y apertura serial sin reset (`dtr=False, rts=False`) + corte automático *no-liftoff*; ejecución exitosa de **los 5 filtros en vuelo real** (`12 s` c/u, `liftoff_ok=True` en los 5) en `COM4` streameados en vivo a `http://localhost:8090/dsp_live.html`; selección y activación del ganador real (**`Median3 + Butterworth 2° orden, fc = 1.5 Hz`**) en el ESP32 y como default en `controller.h`.

---

## 1. Arquitectura Sin Reset (`FILTER,0..4` + `dtr=False, rts=False`)
- En el primer intento de Fase C, re-flashear entre filtros dejó `GPIO25/26` sin señal `1000 µs` durante `~15 s`, disparando el failsafe de los ESCs.
- **Solución implementada:**
  - `version-prueba-v9/include/controller.h`: se habilitó el comando serial en desarmado `FILTER,<0..4>` (responde `ACK,FILTER,<mode>`) para alternar en vivo entre los 5 filtros (`0=EMA 0.30`, `1=SMA N=5`, `2=Butter2 1.5Hz`, `3=Bessel2 2.0Hz`, `4=Cheby1-2 1.8Hz`) con reinicio limpio de estados internos (`resetTofFilters()`).
  - `version-prueba-v9/dsp_auto_bench.py`: apertura del puerto con `dtr=False, rts=False` (`open_serial_no_reset()`), subcomando `suite` que corre los 5 filtros seguidos sin reiniciar el ESP32 (`3 s` de pausa entre vuelos) y guardia automática *no-liftoff* (aborta con `STOP` si `PWM > 75%` por `> 2.5 s` con `max_h < 40`).

---

## 2. Análisis Espectral FFT/PSD del Vuelo Real (`datos_pruebas/dsp_flight_baseline.csv`)
- **Tasas reales medidas:** `fs_ctrl = 21.28 Hz`, `fs_imu = 21.28 Hz`, **`fs_tof = 10.64 Hz`**.
- **Ruido dinámico crudo:** `std = 2.821 mm`, `p2p = 15.561 mm`; **`33` saltos `>= 5 mm`** y **`5` saltos `>= 10 mm`** en `12 s`.
- **Distribución de energía (ventana Hann):** `0–1 Hz: 20.29%`, `1–2 Hz: 33.28%`, `2–5 Hz: 26.56%`, `5–10 Hz: 19.88%`.

---

## 3. Comparativa Definitiva en Vuelo Real — 5 Filtros (`COM4`, 12 s senoidal c/u)
Parámetros idénticos en los 5 vuelos: `START,AUTO,500,0,0.048,0.002,0.0,0.35,0.02,0.08`, referencia $h(t)=500+300\sin(2\pi \cdot 0.35\,t) \in [150, 850]$, `angleTarget = 0°`. **Todos despegaron correctamente (`liftoff_ok = True`) y terminaron en `power = OFF`:**

| # | Filtro (`COM4` en vivo) | Modo | Orden | `fc` (Hz) | `max_h` | `std_mm` | `p2p_mm` | `rmse_mm` | `PWM_jitter` | Score | CSV |
| :-: | :--- | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :--- |
| **1** | **`Median3 + Butter2 (1.5 Hz)`** | **`2`** | `2` | `1.50` | `878.97` | **`1.692`** | **`7.369`** | `50.202` | `0.9895` | **`54.7` (GANADOR)** | `dsp_suite_2_butter2.csv` |
| 2 | `Median3 + SMA (N=5)` | `1` | `4` | `1.77` | `899.67` | `1.874` | `9.307` | `49.814` | `0.9918` | `50.3` | `dsp_suite_1_sma5.csv` |
| 3 | `Median3 + EMA (α=0.30)` | `0` | `1` | `1.36` | `745.78` | `1.895` | `11.945` | `44.263` | `0.9882` | `48.5` | `dsp_suite_0_ema.csv` |
| 4 | `Median3 + Bessel2 (2.0 Hz)` | `3` | `2` | `2.00` | `987.30` | `2.579` | `17.967` | `55.023` | `0.9876` | `29.4` | `dsp_suite_3_bessel2.csv` |
| 5 | `Median3 + Cheby1-2 (1.8 Hz)` | `4` | `2` | `1.80` | `1108.0` | `3.447` | `25.306` | `57.360` | `0.9863` | `9.1` | `dsp_suite_4_cheby2.csv` |

---

## 4. Filtro Ganador y Conclusión Ingenieril
- **Ganador en vuelo real:** **`Median3 + Butterworth 2° orden (fc = 1.5 Hz)` (`DSP_FILTER_MODE = 2`)**.
- **Coeficientes exactos instalados en `version-prueba-v9/include/controller.h` (Forma Directa II Transpuesta, `fs = 20 Hz`, ganancia DC unitaria):**
  - `b = [0.04125354f, 0.08250707f, 0.04125354f]`
  - `a = [1.0f, -1.34896775f, 0.51398189f]`
- **Por qué ganó en vuelo real:** El espectro FFT mostró que `46.4%` del ruido vive por encima de `2 Hz` y `33.3%` entre `1–2 Hz`. `Butter2 (1.5 Hz)` ofrece banda pasante máximamente plana (cero rizado en `0.35 Hz`) con caída rápida `-40 dB/dec`, reduciendo el ruido pico-a-pico en **`-38.3%`** vs EMA (`7.369 mm` vs `11.945 mm`) y **`-20.8%`** vs SMA (`9.307 mm`), manteniendo el recorrido dentro de `879` unidades (mientras `Cheby1-2` y `Bessel2` amplificaron/dejaron pasar vibraciones hasta `1108` y `987`).

---

## 5. Verificación Final
- **ESP32 (`COM4`):** `FILTER,2` confirmado (`ACK,FILTER,2`) sin reiniciar (ESCs siguen armados, motores en `OFF`, `COM4` libre). `#define DSP_FILTER_MODE 2` guardado como default en `version-prueba-v9/include/controller.h`.
- **Tablero DSP (`http://localhost:8090/dsp_live.html`):** Tabla completa de los 5 vuelos reales actualizada con `LIVE · Median3+Butter2(1.5Hz)` resaltado en verde (`GANADOR`).
- **Servidores activos:** `127.0.0.1:8080` (`dashboard.html`) y `127.0.0.1:8090` (`dsp_live.html`).
- **Acción Usuario (Human Gate):** Ninguna; el sistema quedó listo con `Median3 + Butter2 (1.5 Hz)` activo tanto en el ESP32 como en el código fuente.
