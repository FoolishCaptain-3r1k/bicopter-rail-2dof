# Worklog 10 (v2.0) | Prev: [[worklog9]]
- **Estado:** PASS
- **Invariantes Cubiertos:** Redacción completa en LaTeX IEEE doble columna (`reporte/reporte_final_bicopter.tex` + `reporte/referencias.bib`) sin copiar autores de `Practica_2_ctrl.pdf` (con marca `% EDITAR AUTORES AQUI`); compilación limpia con `Tectonic 0.17.0` (compatible también con `pdfLaTeX`/Overleaf); `0` errores, `0` `Overfull \hbox`, `0` referencias `??`; auditoría visual de todas las páginas; limpieza de archivos temporales; PDF abierto en Microsoft Edge; commit y push a `origin/reporte-final-dsp-control`.

---

## 1. Resumen Editorial y Métricas del Documento
- **Archivo PDF generado:** `reporte/reporte_final_bicopter.pdf` (`333.4 KiB`, **`7` páginas** en formato `\documentclass[conference]{IEEEtran}` en español con `Palabras clave`).
- **Compilador utilizado:** `Tectonic 0.17.0` (`%LOCALAPPDATA%\Programs\tectonic\tectonic.exe`, multi-pass XeTeX + BibTeX automático). El preámbulo usa `\usepackage{iftex}` para compilar igualmente sin cambios en `pdfLaTeX` / Overleaf.
- **Inventario del contenido:**
  - **Secciones:** Resumen + Palabras clave + `I` a `VI` + Referencias.
  - **Citas bibliográficas (`referencias.bib`):** `10` referencias citadas y resueltas (`[1]`–`[10]`, 7 de fuentes locales en `C:\dev\dsp-lab\DOCUMENTOS` y `CONTROL\MATERIAL` + 3 hojas de datos de hardware `ESP32`, `VL53L0X`, `BNO055`).
  - **Figuras vectoriales integradas:** `6` (`fig1` a `fig6` en `.pdf`).
  - **Tablas:** `1` (`Tabla I`: comparativa de los 5 filtros en vuelo real en `COM4`).
  - **Ecuaciones numeradas:** `8` (filtro `Butter2`, banda muerta continua, derivada EMA, mixer, $G(s)$, $G(z)$, espacio de estados continuo y discreto).

---

## 2. Auditoría Visual y Correcciones Aplicadas
- Primera compilación detectó `4` `Overfull \hbox` (`Tabla I`, `Ec. 1`, `Ec. 7`, `Ec. 8`). Se corrigieron mediante `\resizebox{\textwidth}{!}` en `Tabla I`, redondeo a 5 decimales en `Ec. 1` y diseño en dos filas (`aligned` + `\footnotesize`) para las matrices 4×4 $\mathbf{A}, \mathbf{B}, \mathbf{C}$ y $\mathbf{\Phi}, \mathbf{\Gamma}$.
- Inspección visual de todas las páginas renderizadas vía `pypdfium2`:
  - Se tradujo `Index Terms` a `Palabras clave` vía `\addto\captionsspanish`.
  - Se promovió `fig2_espectro_fft_ruido.pdf` a `figure*` (`0.88\textwidth`) para máxima legibilidad de las bandas PSD.
  - Se compactó el espaciado en `Ec. 4` para mantener el número de ecuación en línea.
- Recompilación final: **`EXIT=0`**, **`OVERFULL=0`**, **`7` páginas**, temporales eliminados (`.aux`, `.log`, `.out`, `.bbl`, `.blg`) y PDF abierto en Microsoft Edge.

---

## 3. Verificación Focalizada y Git
- **Archivos agregados en este paso:**
  - `reporte/reporte_final_bicopter.tex`
  - `reporte/referencias.bib`
  - `reporte/reporte_final_bicopter.pdf`
  - `docs/worklogs/v2.0/worklog10.md`
- **Verificación Ejecutada:** Compilación limpia (`Tectonic 0.17.0` -> `EXIT=0`, `OVERFULL=0`, `7` págs.), apertura visual en Edge y `git push origin reporte-final-dsp-control`.
- **Acción Usuario (Human Gate):** Revisar el PDF abierto en Edge y actualizar el nombre del colaborador en la línea `% EDITAR AUTORES AQUI` de `reporte/reporte_final_bicopter.tex` si corresponde.
