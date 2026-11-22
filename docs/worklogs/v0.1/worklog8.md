# Worklog 8 (v0.1) | Prev: [[worklog7]]
- **Estado:** PASS
- **Invariantes Cubiertos:** `pcb_spec.py`, `drc.py` y PDFs intactos; esquinas XY redondeadas (`CORNER_RADIUS_XY = 6.50 mm`, `20` seg/esquina); transiciones Y-Z curvas (`PROFILE_FILLET_YZ >= 4.50 mm`, `16` seg/arco); chaflán inferior `45°` de `1.20 mm` en `base`; bajorrelieve de `0.60 mm` con los 4 nombres (`LEONARDO MONTER`, `RENATA BELLO`, `ADRIAN RUIZ`, `ALONSO MADRIGAL`) centrado en el panel inclinado dejando pared remanente `1.80 mm >= 1.60 mm`; mallas `watertight` sin caras degeneradas; `0 mm³` colisión con `SWITCH_KEEP_OUT`/`ESP32_KEEP_OUT`/PCB/ESCs y entre `base`/`top_shell`; `M3 ±0.05 mm`; dimensiones `<= 200×200×150 mm`.
- **Archivos Modificados:**
  - `hardware/enclosure/enclosure_spec.py` — constantes de redondeo (`CORNER_RADIUS_XY`, `PROFILE_FILLET_YZ`, `BOTTOM_CHAMFER_MM`) y tipografía (`TEAM_NAMES`, `ENGRAVE_DEPTH_MM`, `MIN_REMAINING_WALL_MM`)
  - `hardware/enclosure/build_enclosure.py` — perfiles redondeados XY/Y-Z, chaflán `45°`, `build_engraved_text_manifold`, limpieza manifold `_simplify_slivers` y acercamiento en `render_enclosure_preview`
  - `hardware/tests/test_enclosure.py` — agregada `test_ergonomic_curves_and_engraved_names_wall_thickness`
  - `hardware/output/enclosure_base.stl`, `hardware/output/enclosure_top_shell.stl`, `hardware/output/enclosure_preview.png` — regenerados
- **Verificación Ejecutada:** `.\host\.venv\Scripts\python.exe -m pytest hardware/tests/test_enclosure.py -q --tb=short` -> `4 passed in 2.87s` (`0 failed`)
- **Acción Usuario (Human Gate):** Verificar visualmente `hardware/output/enclosure_preview.png` y laminar ambos `.stl` en Bambu Studio (`top_shell` apoyada en cara trasera `Y=96` para impresión sin soportes).
