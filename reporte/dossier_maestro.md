# Dossier Maestro — Bicóptero 2-DOF en Riel: Control Digital y Filtrado DSP

> **Rama de trabajo:** `reporte-final-dsp-control` (derivada de `version-final-opcional` en commit `dafdd31`)
> **Colaboradores detectados en historial Git (bloque editable para portada IEEE):**
> - Leonardo Monter Rizo (`git log`)
> - *Agregar nombre completo del compañero / segundo autor aquí*
> - *Universidad Anáhuac — Control / Procesamiento Digital de Señales (Semestre 8, Ago–Dic 2026)*

---

## 1. Propuesta de Estructura IEEE del Reporte Final (6–8 páginas, cero paja)
Inspirada en el estándar de formato IEEE de referencia (`Practica_2_ctrl.pdf`), pero más completa en evidencia experimental y modelado:

1. **Resumen (Abstract) y Palabras Clave** (~150 palabras): problema físico (ruido ToF + acoplamiento 2-DOF), arquitectura digital `20 Hz`, benchmark de 5 filtros en vuelo real y resultado cuantitativo (`Butter2 1.5 Hz`: `-38.3%` ruido pico-a-pico vs EMA, modelo $G(s)$ con $R^2 = 0.925$).
2. **I. Introducción y Evolución del Prototipo** (~0.8 pág.): alcance del banco de 20 cm, cronología honesta de iteraciones (`fig6_evolucion_proyecto.pdf`) y decisiones de ingeniería tomadas en laboratorio.
3. **II. Arquitectura del Sistema y Lazo Cerrado Digital** (~1.0 pág.): hardware (`ESP32`, `BNO055` `0x28`, `VL53L0X` `0x29`, ESCs `50 Hz` en `GPIO25/26`), protocolo serial `115200` baud y diagrama de bloques completo (`fig1_diagrama_retroalimentado.pdf`).
4. **III. Modelado Matemático: Planta, Ecuaciones en Diferencias y Espacio de Estados** (~1.5 págs.): identificación experimental $G(s)/G(z)$ (`fig5_identificacion_y_polos.pdf`), ley PID discreta con banda muerta continua y anti-windup, y formulación 2-DOF en espacio de estados continuo/discreto.
5. **IV. Identificación Espectral y Diseño DSP de Filtros Pasabajas** (~1.5 págs.): espectro FFT/PSD del vuelo real (`fig2_espectro_fft_ruido.pdf`), comparación Bode + vuelo real de los 5 filtros (`fig3_comparativa_filtros.pdf`) y ecuación en diferencias del filtro ganador.
6. **V. Validación Experimental en Vuelo Real** (~1.2 págs.): respuesta senoidal completa del ganador (`fig4_vuelo_ganador_senoidal.pdf`), tabla comparativa de los 5 vuelos reales + rematch `Butter2` vs `EMA`, y lección de hardware sobre failsafe de ESCs (`FILTER,0..4`).
7. **VI. Conclusiones y Trabajo Futuro** (~0.4 pág.) + **Referencias** (~0.4 pág., citas locales verificadas).

---

## 2. Banco de Citas Verificadas (Prioridad a Fuentes Locales)

### 2.1 Fuentes Locales Verificadas (`C:\dev\dsp-lab\DOCUMENTOS` y `CONTROL\MATERIAL`)
1. **[Vignolo-DSP]** J. Vignolo Barchiesi, *Apuntes de Procesamiento Digital de Señales*, Caps. 3 (*Sistemas en tiempo discreto*), 4 (*Espectro de frecuencia de secuencias / DTFT*), 5 (*Respuesta de frecuencia de filtros digitales*), 6 (*Muestreo de señales análogas*, pp. 10–12: filtro Butterworth), 11 (*Diseño de filtros digitales tipo FIR*) y 12 (*Diseño de filtros digitales tipo IIR*, pp. 26–31: diseño Butterworth y Chebyshev). Archivo local: `C:\dev\dsp-lab\DOCUMENTOS\12_DisIIR (1).pdf`.
2. **[Eslava-CD]** A. J. Eslava Escobar, *Control Digital — Unidad 1, 2 y 3* (estabilidad en el plano $z$, sistemas muestreados), citando a E. J. Taconi y R. J. Mantz, *Análisis y Diseño de Sistemas de Control Digital*, y E. Bertram, B. Friedland y G. F. Franklin (1952), *Sampled-Data Control Systems* (pp. 5, 11). Archivo local: `C:\dev\dsp-lab\DOCUMENTOS\Control Digital unidad 1, 2 y 3 (4).pdf`.
3. **[Cayetano-Resp]** I. Cayetano, *Response Analysis in Control Systems* (sistemas de 2° orden: subamortiguado, críticamente amortiguado y sobreamortiguado, 16 pp.) y *Stability in Control Systems* (17 pp.), Material de Curso de Control, Universidad Anáhuac, 2026. Citando G. Barbastathis, *MIT 2.04A Systems and Controls* (2013) y B. Douglas, *The Fundamentals of Control Theory* (2019).
4. **[Cayetano-PID]** I. Cayetano, *PID Control: Proportional-Integral-Derivative* (17 pp., p. 9 citando K. J. Åström y T. Hägglund sobre sintonización y anti-windup) y *Introduction to Digital Control* (19 pp.), Universidad Anáhuac, 2026.
5. **[Cayetano-DSP]** I. Cayetano, *Digital Signal Processing* (28 pp., p. 27 diseño Butterworth `butter(n, fd, type)`), citando M. Vetterli y P. Prandoni, *Digital Signal Processing*, EPFL (2017), y J. Vesin, *Biomedical Signal Processing Course Notes*, EPFL (2016).
6. **[Cayetano-SS]** I. Cayetano, *Introduction to State Space* (15 pp., representación $\dot{\mathbf{x}}=\mathbf{A}\mathbf{x}+\mathbf{B}\mathbf{u}$, eigenvalores, controlabilidad y observabilidad), Universidad Anáhuac, 2026.

### 2.2 Referencias Técnicas de Hardware (Hojas de Datos)
7. **[Bosch-BNO055]** Bosch Sensortec, *BNO055 Intelligent 9-axis Absolute Orientation Sensor — Datasheet*, Doc. BST-BNO055-DS000 (modo fusión `IMUPLUS 0x08`, registros Euler `0x1A..0x1F` y cuaternión `0x20..0x27`).
8. **[ST-VL53L0X]** STMicroelectronics, *VL53L0X World's Smallest Time-of-Flight Ranging and Gesture Detection Sensor — Datasheet*, DocID029104 (modo continuo `50 ms`, estado de rango `deviceStatus == 11`).
9. **[Espressif-ESP32]** Espressif Systems, *ESP32 Technical Reference Manual*, Cap. LED PWM Controller (LEDC `50 Hz`, resolución `16-bit`, `65536` cuentas por `20 ms`).

---

## 3. Crónica Real del Proyecto (Worklogs + Ramas Git)
El proyecto evolucionó en seis etapas concretas documentadas en `docs/worklogs/v0.1/` (`worklog1..29`), `docs/worklogs/v2.0/` (`worklog1..8`) y el árbol Git:

1. **Base Segura, PCB 1-Capa y Consola 3D (`main`, `v0.1` WL1–WL14):** Arranque seguro garantizado (`armed=false`, `1000 µs`), pinout consolidado (`I2C SDA=21/SCL=22`, `BNO055=0x28`, `VL53L0X=0x29`, `ESC=GPIO25/26`), PCB monocapa auditada a 300 DPI y carcasa impresa en 3D.
2. **Estabilidad de Sensores y Gimbal Lock → Cuaternión (`v0.1` WL15–WL27):** Pruebas progresivas sobre USB (`sensor-tests/bno055`, `dual-usb`) a `100 kHz` I2C. En `WL27` se descubrió *gimbal lock* al leer ángulos de Euler cerca de 90° y se validó la lectura desde cuaternión normalizado en el banco experimental.
3. **Arquitectura V8/V9 con Modos Manual, Automático y Gestos (`version-final-opcional`, `548022e`):** Integración en `version-prueba-v9/` del controlador dual-PID a `20 Hz` (`BASE_PERCENT = 58%`, rampa `1450 µs` en `1 s`, slew `200 µs/s`), dashboard Web Serial, logger CSV (`capture.js`) y control offline por palma con MediaPipe (`hand-control.js`).
4. **Decisión Pragmática: Reversión del Filtro de Kalman (`v2.0` WL5–WL6):** Aunque inicialmente se evaluó un filtro de Kalman de 3 estados para altura, se descartó en laboratorio por complejidad de sintonización frente a la tasa real del ToF (`~10.6 Hz`) y picos no gaussianos; se adoptó la arquitectura modular `Median3` (rechazo no lineal de picos impulsivos) + pasabajas lineal + banda muerta continua de `±2.0 mm`, logrando `-72.0%` de ruido estático (`std = 0.346 mm`).
5. **Panel de 4 Rutinas de Amortiguamiento en 1 Clic (`v2.0` WL5):** Se añadió `#autoPanel` en `dashboard.html`/`dashboard.js` con calibración de tope físico (`20 cm`) y reescalado automático de ganancias (`200 / topeReal`) para ejecutar en 1 clic: *No amortiguado (Senoidal)*, *Subamortiguado*, *Críticamente amortiguado* y *Sobreamortiguado* (ángulo fijo `0°`).
6. **Failsafe de ESCs al Reflashear → Solución `FILTER,0..4` sin Reset (`v2.0` WL7–WL8):** Durante las pruebas dinámicas se detectó que reflashear el ESP32 entre filtros cortaba la señal `1000 µs` por `~15 s`, metiendo los ESCs en failsafe. Se resolvió agregando el comando serial `FILTER,0..4` en `controller.h` + apertura serial `dtr=False, rts=False` + guardia *no-liftoff* en `dsp_auto_bench.py`, permitiendo volar los **5 filtros en vivo sin reiniciar el ESP32** mientras se visualizaba todo en tiempo real en `dsp_live.html` (SSE en puerto `8090`).

---

## 4. Modelado Matemático de Control y DSP (Números Verificados en Vuelo Real)

### 4.1 Parámetros Exactos del Vuelo Senoidal (Sin Amortiguar en Altura)
- **Recorrido del riel:** `20 cm` físicos (`200 mm`) mapeados a `top = 1000` unidades de altura (`1 u. = 0.20 mm` físicos).
- **Trayectoria de referencia:**
  $$r_h[k] = \text{clamp}\!\left(500 + 300\sin(2\pi \cdot 0.35\,t_k),\; 150,\; 850\right), \qquad r_\theta[k] = 0^\circ$$
- **Ganancias PID usadas (`scale = 200 / 1000 = 0.20`):**
  - Eje Altura: `HKp = 0.048`, `HKi = 0.002`, `HKd = 0.0` (`BASE_PERCENT = 58%` = `1580 µs`).
  - Eje Ángulo: `AKp = 0.35`, `AKi = 0.02`, `AKd = 0.08`.
- **Por qué esas ganancias:** Con un escalón inicial de $e_0 = 500$ u., el aporte proporcional es $0.048 \times 500 = +24\%$ sobre la base `58%` (`82%` total), evitando saturar el límite individual del PID (`±40%`) y dejando margen debajo de `MAX_PERCENT = 99%` para nivelar el ángulo en `0°`.

### 4.2 Identificación Experimental de la Planta $G(s)$ y $G(z)$
Ajustada por mínimos cuadrados no lineales (`reporte/scripts/modelado_y_figuras.py`) directamente sobre el vuelo ganador (`dsp_suite_2_butter2.csv`, entrada $\Delta u_{\text{col}} = \frac{u_L+u_R}{2} - u_{\text{eq}}$ en `%`, salida $z$ en `mm` físicos):

- **Parámetros identificados:** $K_{\text{dc}} = 4.6375\text{ mm/\%}$, $\omega_n = 2.0860\text{ rad/s}$, $\zeta = 0.2809$, $u_{\text{eq}} = 45.492\%$.
- **Calidad del ajuste (transparente):** **$R^2 = 0.9250$**, **$\text{RMSE} = 16.65\text{ mm}$** sobre un recorrido total de `200 mm`.
- **Función de transferencia continua:**
  $$G(s) = \frac{Z(s)}{\Delta U_{\text{col}}(s)} = \frac{20.1797}{s^2 + 1.1718\,s + 4.3514}$$
- **Equivalente discreto ($T_s = 0.05\text{ s}$, retenedor de orden cero ZOH):**
  $$G(z) = \frac{0.024717\,z^{-1} + 0.024239\,z^{-2}}{1 - 1.932538\,z^{-1} + 0.943094\,z^{-2}}$$
  Polos discretos en $z_{1,2} = 0.96627 \pm j\,0.09705$ ($|z| = 0.97113 < 1$, dentro del círculo unitario).

### 4.3 Ecuaciones en Diferencias Implementadas en el ESP32 (`controller.h`)

#### A) Filtro Ganador: `Median3 + Butterworth 2° orden` ($f_c = 1.5\text{ Hz}$, $f_s = 20\text{ Hz}$)
1. **Pre-filtro no lineal de mediana de 3** (elimina saltos aislados `≥ 5 mm` sin añadir retardo de fase):
   $$m[k] = \text{mediana}\!\big(d[k],\; d[k-1],\; d[k-2]\big), \qquad x[k] = m[k] - d_{\text{origen}}$$
2. **Ecuación en diferencias IIR (Forma Directa II Transpuesta, ganancia DC unitaria):**
   $$y[k] = 0.04125354\,x[k] + 0.08250707\,x[k-1] + 0.04125354\,x[k-2] + 1.34896775\,y[k-1] - 0.51398189\,y[k-2]$$
   Sus polos están en $z_{1,2} = 0.67448 \pm j\,0.24301$ ($|z| = 0.71693 < 1$, estable con holgura) y tiene un doble cero en $z = -1$ (atenuación infinita en Nyquist, `10 Hz`).

#### B) Ley de Control PID Discreta (`T_s = 0.05 s`)
1. **Banda muerta continua en altura (`±2.0 mm` = `±20` u., evita perseguir ruido residual sin dar escalones):**
   $$e_{\text{db}}[k] = \begin{cases} 0, & |e[k]| \le 20 \\ e[k] - 20\,\text{sgn}(e[k]), & |e[k]| > 20 \end{cases}$$
2. **Derivada sobre medición filtrada (evita *derivative kick* al cambiar la consigna):**
   $$v[k] = 0.7\,v[k-1] + 0.3\,\frac{h[k] - h[k-1]}{\Delta t}$$
3. **Salida PID con anti-windup condicional y saturación `±40%`:**
   $$I_{\text{cand}}[k] = \text{sat}_{[-40,40]}\!\big(I[k-1] + K_i\,e_{\text{db}}[k]\,\Delta t\big), \qquad u_{\text{raw}}[k] = K_p\,e_{\text{db}}[k] + I_{\text{cand}}[k] - K_d\,v[k]$$
   Se actualiza $I[k] = I_{\text{cand}}[k]$ solo si $|u_{\text{raw}}[k]| < 40$ o $u_{\text{raw}}[k]\,e_{\text{db}}[k] < 0$.
4. **Mixer y limitador de pendiente (`CONTROL_RATE = 20%/s` = `200 µs/s`):**
   $$u_L[k] = \text{slew}\!\big(58 + u_H[k] - u_A[k]\big), \qquad u_R[k] = \text{slew}\!\big(58 + u_H[k] + u_A[k]\big)$$

### 4.4 Análisis en Espacio de Estados (Explicado sin Jerga Innecesaria)
En lugar de ver altura y ángulo por separado, el **espacio de estados** guarda una "fotografía instantánea" del bicóptero en un solo vector de 4 números:
$$\mathbf{x}(t) = \begin{bmatrix} z(t) \\ \dot{z}(t) \\ \theta(t) \\ \dot{\theta}(t) \end{bmatrix}, \qquad \mathbf{u}(t) = \begin{bmatrix} \Delta u_{\text{col}}(t) \\ u_{\text{diff}}(t) \end{bmatrix}, \qquad \mathbf{y}(t) = \begin{bmatrix} z(t) \\ \theta(t) \end{bmatrix}$$
Donde $z$ es la altura (`mm`), $\dot{z}$ su velocidad vertical (`mm/s`), $\theta$ la inclinación (`°`) y $\dot{\theta}$ su velocidad angular (`°/s`).

- **Modelo continuo ($\dot{\mathbf{x}} = \mathbf{A}\mathbf{x} + \mathbf{B}\mathbf{u}$, $\mathbf{y} = \mathbf{C}\mathbf{x}$):**
  $$\mathbf{A} = \begin{bmatrix} 0 & 1 & 0 & 0 \\ -4.3514 & -1.1718 & 0 & 0 \\ 0 & 0 & 0 & 1 \\ 0 & 0 & 0 & -1.2000 \end{bmatrix}, \quad \mathbf{B} = \begin{bmatrix} 0 & 0 \\ 20.1797 & 0 \\ 0 & 0 \\ 0 & 31.5330 \end{bmatrix}, \quad \mathbf{C} = \begin{bmatrix} 1 & 0 & 0 & 0 \\ 0 & 0 & 1 & 0 \end{bmatrix}$$
- **Modelo discreto ZOH ($T_s = 0.05\text{ s}$, $\mathbf{x}[k+1] = \mathbf{\Phi}\mathbf{x}[k] + \mathbf{\Gamma}\mathbf{u}[k]$):**
  $$\mathbf{\Phi} = \begin{bmatrix} 0.99467 & 0.04848 & 0 & 0 \\ -0.21094 & 0.93787 & 0 & 0 \\ 0 & 0 & 1.00000 & 0.04853 \\ 0 & 0 & 0 & 0.94176 \end{bmatrix}, \quad \mathbf{\Gamma} = \begin{bmatrix} 0.02472 & 0 \\ 0.97822 & 0 \\ 0 & 0.03864 \\ 0 & 1.53028 \end{bmatrix}$$
- **Qué nos dice este modelo en español llano:**
  1. **Controlabilidad = rango `4/4`:** Con los dos motores (`u_col` y `u_diff`) podemos llevar tanto la altura como el ángulo (y sus velocidades) a cualquier punto deseado del riel.
  2. **Observabilidad = rango `4/4`:** Midiendo únicamente altura ($z$ con VL53L0X) y ángulo ($\theta$ con BNO055) basta para conocer completamente el estado interno del sistema (incluyendo velocidades).
  3. **Eigenvalores (polos naturales):**
     - Verticales: $s = -0.5859 \pm j\,2.002$ ($|z| = 0.9711 < 1$) $\rightarrow$ el riel tiende a oscilar suavemente y amortiguarse por sí solo alrededor del equilibrio.
     - Angulares: $s = 0$ ($z = 1.0$) y $s = -1.2$ ($z = 0.9418$) $\rightarrow$ el ángulo es un integrador puro (si no hay control, se queda inclinado hacia donde lo empujes), por eso **el lazo angular con `Kp > 0` es indispensable**.

---

## 5. Resultados Experimentales (Suite de 5 Filtros + Rematch en Vuelo Real)

### 5.1 Suite Completa de los 5 Filtros en Vuelo Real (`COM4`, 12 s senoidal c/u, sin reset)
| # | Filtro (`COM4` en vivo) | Modo | Orden | `fc` (Hz) | `max_h` (u.) | `std_mm` | `p2p_mm` | `rmse_mm` | `PWM_jitter` | Score |
| :-: | :--- | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: |
| **1** | **`Median3 + Butter2 (1.5 Hz)`** | **`2`** | 2 | 1.50 | `878.97` | **`1.692`** | **`7.369`** | `50.202` | `0.9895` | **`54.7` (GANADOR)** |
| 2 | `Median3 + SMA (N=5)` | `1` | 4 | 1.77 | `899.67` | `1.874` | `9.307` | `49.814` | `0.9918` | `50.3` |
| 3 | `Median3 + EMA (α=0.30)` | `0` | 1 | 1.36 | `745.78` | `1.895` | `11.945` | `44.263` | `0.9882` | `48.5` |
| 4 | `Median3 + Bessel2 (2.0 Hz)` | `3` | 2 | 2.00 | `987.30` | `2.579` | `17.967` | `55.023` | `0.9876` | `29.4` |
| 5 | `Median3 + Cheby1-2 (1.8 Hz)` | `4` | 2 | 1.80 | `1108.0` | `3.447` | `25.306` | `57.360` | `0.9863` | `9.1` |

### 5.2 Rematch Cabeza a Cabeza (`Butter2 1.5 Hz` vs `EMA 0.30`)
- `Median3 + Butter2 (1.5 Hz)`: `std = 1.586 mm`, `p2p = 7.857 mm`, `max_h = 763.5` (siguió casi toda la amplitud senoidal hasta `800`).
- `Median3 + EMA (0.30)`: `std = 1.390 mm`, `p2p = 7.248 mm`, `max_h = 639.9` (atenuó más la propia onda senoidal útil).
- **Decisión final instalada en flash (`#define DSP_FILTER_MODE 2`):** **`Median3 + Butterworth 2° orden (1.5 Hz)`**, por ofrecer el mejor equilibrio entre rechazo de ruido (`-38.3%` p2p en la suite de 5 filtros), respuesta plana en `0.35 Hz` y seguimiento fiel sin rebasar el tope.

---

## 6. Inventario de Figuras Generadas (`reporte/figuras/`, `.pdf` vectorial + `.png` 300 DPI)
1. `fig1_diagrama_retroalimentado.{pdf,png}` — Diagrama de bloques completo del lazo cerrado digital 2-DOF.
2. `fig2_espectro_fft_ruido.{pdf,png}` — Señal cruda VL53L0X con saltos impulsivos marcados + PSD por bandas de frecuencia.
3. `fig3_comparativa_filtros.{pdf,png}` — Bode digital (magnitud y fase a `20 Hz`) + barras de `STD`, `P2P` y `Score` en vuelo real.
4. `fig4_vuelo_ganador_senoidal.{pdf,png}` — Respuesta temporal completa del ganador (altura, ángulo `0°`, PWM `GPIO25/26`).
5. `fig5_identificacion_y_polos.{pdf,png}` — Validación del modelo $G(s)/G(z)$ ($R^2 = 0.925$) + mapa de polos/ceros en el plano $z$.
6. `fig6_evolucion_proyecto.{pdf,png}` — Línea de tiempo de las iteraciones y ramas del proyecto.
