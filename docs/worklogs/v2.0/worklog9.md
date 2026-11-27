# Worklog 9 (v2.0) | Prev: [[worklog8]]
- **Estado:** PASS
- **Invariantes Cubiertos:** Rama `reporte-final-dsp-control` creada desde `version-final-opcional` (`dafdd31`, con `DSP_FILTER_MODE 2` intacto); minería bibliográfica local verificada en `C:\dev\dsp-lab\DOCUMENTOS` y `CONTROL\MATERIAL` (sin copiar autores de `Practica_2_ctrl.pdf`); modelado matemático reproducible en `reporte/scripts/modelado_y_figuras.py`; 6 figuras IEEE vectoriales (`.pdf` + `.png` 300 DPI) verificadas visualmente sin recortes; `reporte/dossier_maestro.md` completo; commit y push exitosos a `origin/reporte-final-dsp-control`.

---

## 1. Bibliografía Local Consultada
- **`C:\dev\dsp-lab\DOCUMENTOS\` (9 PDFs):**
  - J. Vignolo Barchiesi, *Apuntes de Procesamiento Digital de Señales*: `01_Introduccion (2).pdf`, `02_Secuencias (2).pdf`, `03_Sistemas (1) (1).pdf`, `04_DTFT (1).pdf`, `05_RespFrec (1) (1).pdf`, `06_Muestreo (1).pdf` (pp. 10–12), `11_DisFIR (1).pdf`, `12_DisIIR (1).pdf` (pp. 26–31).
  - M.I. A. J. Eslava Escobar, `Control Digital unidad 1, 2 y 3 (4).pdf` (pp. 5, 11; citando E. J. Taconi & R. J. Mantz y Bertram, Friedland & Franklin, 1952).
- **`C:\Users\Ruiza\Desktop\ANAHUAC\SEMESTRE 8 AGO-DIC 2026\CONTROL\MATERIAL\` (10 PDFs):**
  - I. Cayetano, ing. microtechn. dipl. EPF, MSc.: `1_Introduction_Control.pdf`, `2_Response_Analysis.pdf`, `3_Stability.pdf`, `4_PID_Control.pdf` (p. 9 Åström & Hägglund), `5_Digital_Control.pdf`, `6_Digital_Signal_Processing.pdf` (p. 27 `butter`, p. 28 Vetterli & Prandoni EPFL 2017, Vesin EPFL 2016), `6_IntermittentControl_InstrumentationDiagrams.pdf`, `7_StateSpace.pdf`, `8_Advanced_Control.pdf`, `Control_Theory_Review.pdf` (citando Barbastathis MIT 2.04A 2013 y Douglas 2019).
- **Referencia de estilo únicamente:** `Practica_2_ctrl.pdf` (3 págs., secciones IEEE `I..V`; autores no copiados).

---

## 2. Resumen de Ecuaciones Obtenidas (`reporte/scripts/resultados_modelado.json`)
- **Planta continua identificada (vuelo real `dsp_suite_2_butter2.csv`, $R^2 = 0.9250$, $\text{RMSE} = 16.646\text{ mm}$):**
  $$G(s) = \frac{20.1797}{s^2 + 1.1718\,s + 4.3514} \quad (K_{\text{dc}}=4.6375\text{ mm/\%},\;\omega_n=2.086\text{ rad/s},\;\zeta=0.2809,\;u_{\text{eq}}=45.492\%)$$
- **Planta discreta ($T_s = 0.05\text{ s}$, ZOH):**
  $$G(z) = \frac{0.024717\,z^{-1} + 0.024239\,z^{-2}}{1 - 1.932538\,z^{-1} + 0.943094\,z^{-2}}, \qquad z_{1,2} = 0.96627 \pm j\,0.09705\; (|z|=0.97113)$$
- **Filtro ganador (`Median3 + Butter2 1.5 Hz`, $f_s = 20\text{ Hz}$):**
  $$y[k] = 0.04125354\,x[k] + 0.08250707\,x[k-1] + 0.04125354\,x[k-2] + 1.34896775\,y[k-1] - 0.51398189\,y[k-2]$$
  Polos en $z_{1,2} = 0.67448 \pm j\,0.24301$ ($|z| = 0.71693$).
- **Espacio de estados 2-DOF ($\mathbf{x} = [z, \dot{z}, \theta, \dot{\theta}]^T$):** Controlabilidad = rango `4/4`, Observabilidad = rango `4/4`, eigenvalores discretos $|z| = \{0.97113, 0.97113, 1.00000, 0.94176\}$.

---

## 3. Inventario de Figuras Generadas (`reporte/figuras/`, `.pdf` + `.png` 300 DPI)
1. `fig1_diagrama_retroalimentado.{pdf,png}` — Lazo cerrado digital 2-DOF con bloque DSP ganador.
2. `fig2_espectro_fft_ruido.{pdf,png}` — Señal cruda VL53L0X con saltos impulsivos + PSD por bandas.
3. `fig3_comparativa_filtros.{pdf,png}` — Bode digital (`20 Hz`) + barras `STD`/`P2P`/`Score` en vuelo real.
4. `fig4_vuelo_ganador_senoidal.{pdf,png}` — Respuesta temporal completa de `Median3 + Butter2 (1.5 Hz)` (altura, ángulo `0°`, PWM).
5. `fig5_identificacion_y_polos.{pdf,png}` — Ajuste $G(s)/G(z)$ ($R^2 = 0.925$) + plano $z$ (polos planta y filtro).
6. `fig6_evolucion_proyecto.{pdf,png}` — Línea de tiempo de iteraciones del proyecto.

---

## 4. Verificación Focalizada y Git
- **Archivos Creados:**
  - `reporte/dossier_maestro.md`
  - `reporte/scripts/modelado_y_figuras.py`
  - `reporte/scripts/resultados_modelado.json`
  - `reporte/figuras/fig{1..6}_*.{pdf,png}` (12 archivos, todos `> 36 KB`)
  - `docs/worklogs/v2.0/worklog9.md`
- **Verificación Ejecutada:** `.\.venv\Scripts\python.exe reporte\scripts\modelado_y_figuras.py` -> `exit 0` (`ALL_6_FIGURES_GENERATED_OK`), inspección visual de `fig1`, `fig3` y `fig5` sin encimamientos.
- **Commit y Push:** Ejecutado en rama `reporte-final-dsp-control` hacia `origin/reporte-final-dsp-control`.
