# Fabricación de PCB 1 Capa (`B.Cu`) — Bicopter Rail 2-DOF

Placa de distribución planar en **1 sola capa de cobre (`B.Cu`)**, **0 puentes (jumpers)** y **0 componentes pasivos externos**, diseñada para placa fenólica virgen de `100 × 100 mm` (recorte final `92.0 × 88.0 mm`).

---

## 1. Archivos Generados (`hardware/output/`)

- `pcb_bottom_toner_1to1.pdf` / `.svg`: Máscara monocromática negro puro sobre blanco a escala física **`1:1`** lista para impresión láser en papel couché y planchado directo sobre el cobre inferior (`B.Cu`).
  - **Invariante de espejeado:** Los pads y pistas eléctricas están en coordenadas de **Vista Superior** (al voltear el papel couché boca abajo sobre la cara inferior de cobre `B.Cu`, quedan exactamente alineados con los pines insertados desde arriba). El **emblema Anáhuac México y los 4 nombres** están **espejeados horizontalmente** en este archivo para que, tras planchar el tóner sobre el cobre, se lean al derecho.
- `pcb_top_assembly_1to1.pdf` / `.svg`: Plano de ensamble en **Vista Superior** (sin espejear) con silueta del ESP32 (conector USB hacia el borde inferior), etiquetas de todos los pines (`J_TOF`, `J_IMU`, ESCs), nota del puente `ADD–GND` en el `GY-BNO055` (`0x28`), y esquema del switch externo.
- `pcb_drill_map.svg`: Mapa `1:1` de barrenos con guía de diámetros de broca.

---

## 2. Verificación Previa en Hoja Blanca (Escala `1:1`)

1. Imprimir `pcb_bottom_toner_1to1.pdf` en una hoja blanca común configurando el visor PDF en **`Tamaño real` / `Escala 100 %`** (desactivar *"Ajustar a página"*).
2. Medir con vernier o regla metálica la línea **`50.0 mm CALIBRATION RULER (1:1)`**: debe medir exactamente `50.0 mm ± 0.1 mm`.
3. Presentar físicamente el **ESP32 DevKit V1 (30 pines)** sobre la impresión verificando paso `2.54 mm` y separación entre hileras de **`25.40 mm`**.

---

## 3. Transferencia de Tóner (Papel Couché) y Atacado Químico

1. **Preparación del cobre:** Cortar o marcar la placa fenólica (`100 × 100 mm` → `92 × 88 mm`), lijar suavemente con lija al agua grano `1000–1200` hasta brillo uniforme y desengrasar con alcohol isopropílico o acetona.
2. **Impresión en couché:** Imprimir `pcb_bottom_toner_1to1.pdf` en **impresora láser** (tóner negro al máximo, sin ahorro de tóner, escala `100 %`) sobre papel couché brillante (`130–150 g/m²`).
3. **Planchado:** Colocar el papel couché **boca abajo** (cara con tóner contra el cobre) y planchar a temperatura alta (sin vapor) durante `3–5 minutos` aplicando presión firme y uniforme.
4. **Desprendimiento:** Sumergir la placa en agua tibia durante `10 minutos` y retirar el papel suavemente con la yema de los dedos hasta dejar solo el tóner adherido.
5. **Atacado con cloruro férrico ($FeCl_3$):** Sumergir en solución tibia de cloruro férrico agitando suavemente hasta disolver el cobre expuesto (`10–20 min`). Enjuagar con abundante agua y retirar el tóner con acetona.
6. **Taladrado manual (usando los puntos guía blancos centrales):**
   - Headers `2.54 mm` (`ESP32`, `J_TOF`, `J_IMU`): broca **`0.8 – 0.9 mm`** (`39` barrenos).
   - Señal y tierra de señal ESC (`ESC_L_SIG`, `ESC_R_SIG`, `ESC_L_GND_SIG`, `ESC_R_GND_SIG`): broca **`1.0 mm`** (`4` barrenos).
   - Pads de potencia (`BAT_VBAT_IN`, `BAT_GND_IN`, `ESC_L_VBAT`, `ESC_R_VBAT`, `ESC_L_GND_PWR`, `ESC_R_GND_PWR`): broca **`1.6 mm`** (`6` barrenos).
   - Esquinas de montaje `M3`: broca **`3.2 mm`** (`4` barrenos).

---

## 4. Switch Externo de Potencia y Notas de Ensamble

- **Cotas del switch externo (para futura carcasa 3D):** **`30.0 × 20.0 × 20.0 mm`** (largo × ancho × profundidad).
- **Conexión en serie:** El cable positivo `+VBAT` de la LiPo 2S (`7.4–8.4 V`) pasa por el switch externo antes de soldarse al pad `BAT_VBAT_IN` (red `+VBAT_SW`).
- **Aislamiento de `VIN`:** El pin `ESP32_VIN` (pin 15 izquierdo) queda **estrictamente aislado** en la PCB; el ESP32 se alimenta únicamente por su puerto USB inferior.
- **Puente `ADD–GND` en `GY-BNO055`:** Asegurar que el pin `ADD` (o `ADR`) del módulo `GY-BNO055` esté conectado a `GND` para fijar su dirección I2C en `0x28`.
