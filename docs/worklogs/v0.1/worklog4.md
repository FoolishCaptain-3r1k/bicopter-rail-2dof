# Worklog 4 (v0.1) | Prev: [[worklog3]]
- **Estado:** PASS
- **Invariantes Cubiertos:** `pcb_spec.py` y `drc.py` intactos; `.svg` individuales sin cambios; PDFs `pcb_bottom_toner_1to1.pdf` y `pcb_top_assembly_1to1.pdf` en US Letter exacto (`612.0 × 792.0 pt` = `215.9 × 279.4 mm ± 0.1 mm`) con panelizado `2×2` (`4` copias), cero solapamientos, marcas de corte, reglas `50.0 mm` H/V (`±0.1 mm`), aviso `"CARTA 1:1 - IMPRIMIR AL 100% (NO AJUSTAR A PAGINA)"` y quiralidad de planchado preservada en las 4 copias.
- **Archivos Modificados:**
  - `hardware/render.py` — `compute_letter_tiling`, `compute_letter_layout`, `_transform_point` (`det = +1`), `_draw_letter_chrome` y panelizado US Letter en `export_bottom_toner_pdf` / `export_top_assembly_pdf`
  - `hardware/tests/test_pcb_drc.py` — verificación MediaBox US Letter, rejilla `2×2`, no solapamiento, reglas `50.0 mm` H/V en stream PDF y espejeado por copia
  - `hardware/output/pcb_bottom_toner_1to1.pdf` — regenerado US Letter `2×2` (4 copias)
  - `hardware/output/pcb_top_assembly_1to1.pdf` — regenerado US Letter `2×2` (4 copias)
- **Verificación Ejecutada:** `.\host\.venv\Scripts\python.exe -m pytest hardware/tests/test_pcb_drc.py -q --tb=short` -> `5 passed in 4.52s` (`0 failed`)
- **Acción Usuario (Human Gate):** Imprimir `hardware/output/pcb_bottom_toner_1to1.pdf` en hoja Tamaño Carta al `100 %` y verificar con vernier `50.0 mm` tanto en la regla horizontal como en la vertical antes de planchar en papel couché.
