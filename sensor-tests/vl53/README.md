# Prueba individual de VL53 con ESP32

Proyecto PlatformIO independiente de `firmware/`. Solo usa USB, I2C y Serial; no configura GPIO25/GPIO26, ESC ni motores. **El modelo físico del sensor del equipo no está confirmado.** La presencia de un dispositivo en la dirección I2C de 7 bits `0x29` no distingue VL53L0X de VL53L1X.

## Identificar el módulo antes de conectarlo

1. Leer la serigrafía del chip, la etiqueta y la referencia exacta de la placa; contrastarlas con la ficha o esquema del fabricante del *módulo*, no solo del chip. Una placa marcada únicamente `VL53` o `0x29` sigue sin identificar el modelo ni sus niveles eléctricos.
2. Confirmar en esa ficha el rango de **entrada de alimentación**, los pull-ups de SDA/SCL y si incorpora regulador y conversores de nivel. Si cualquiera de esos datos falta, **no conectar ni alimentar** el módulo. No conectar 5 V a GPIO del ESP32 ni usar la LiPo 2S en esta prueba.
3. Tras verificar el cableado, el programa lee los registros de identificación **antes** de iniciar una librería: `0x010F = 0xEA` corresponde a VL53L1X; `0xC0 = 0xEE` corresponde a VL53L0X. Si no coincide, imprime `ERROR UNKNOWN_MODEL` y no intenta medir. Estos valores están documentados por [ST para VL53L1X](https://www.st.com/resource/en/datasheet/vl53l1x.pdf) y [ST para VL53L0X](https://www.st.com/resource/en/datasheet/vl53l0x.pdf).

## Cableado para un módulo **verificado** de lógica I2C 3.3 V

Desconectar USB antes de cablear. Para un *carrier* que explícitamente acepte entrada de 3.3 V y presente SDA/SCL a 3.3 V (por ejemplo, los carriers [Pololu VL53L0X](https://www.pololu.com/product/2490) o [Pololu VL53L1X](https://www.pololu.com/product/3415)), usar:

| ESP32 `esp32dev` | Módulo VL53 | Condición |
| --- | --- | --- |
| `3V3` | `VIN` o `VCC` | Solo si la ficha del **módulo** confirma entrada de 3.3 V. No confundir `VIN` con `VDD` de salida de un regulador. |
| `GND` | `GND` | Tierra común obligatoria. |
| `GPIO21` | `SDA` | Pull-up del bus a 3.3 V; nunca a 5 V en el lado ESP32. |
| `GPIO22` | `SCL` | Pull-up del bus a 3.3 V; nunca a 5 V en el lado ESP32. |
| `GPIO19` | `XSHUT` (opcional) | Solo tras confirmar su nivel tolerado. Este programa **no lo controla**; puede quedar sin conectar si el módulo lo mantiene habilitado con pull-up propio. |

Si es un chip o breakout sin regulador/conversores, **no aplicar esta tabla automáticamente**: las tensiones del chip y de su interfaz pueden diferir de las del ESP32. Los carriers Pololu citados desplazan SDA/SCL al nivel de `VIN`, mientras que `XSHUT` no pasa por ese conversor; revisar su ficha antes de conectarlo. Esta prueba usa I2C a `100 kHz` para facilitar el diagnóstico, y Serial a `115200` baudios.

Antes de energizar, verificar con multímetro la continuidad de GND y la ausencia de cortos entre `3V3` y `GND`. Mantener ESC, motores, batería LiPo y hélices desconectados. Seguir también [la guía de seguridad del repositorio](../../docs/WIRING_AND_SAFETY.md).

## Compilar, cargar y observar

Desde la raíz del repositorio:

```powershell
pio run -d sensor-tests/vl53
```

Los siguientes pasos **solo** corresponden a una sesión física autorizada, con el módulo y niveles confirmados:

```powershell
pio run -d sensor-tests/vl53 -t upload
pio device monitor -b 115200
```

Seleccionar el puerto con la opción `-p` si PlatformIO no lo encuentra. No cargar esta prueba en un ESP32 todavía conectado a ESC o motores: este programa no genera pulsos PWM y `LOW`/alta impedancia no equivale a una consigna segura para cualquier ESC.

Salida esperada: `DETECTED model=...`, `READY model=...` y una tabla CSV a 115200 baudios:

```text
ts_ms,model,distance_raw_mm,distance_filtrada_mm,status
1234,VL53L0X,101,NA,OK_WARMUP
1334,VL53L0X,99,NA,OK_WARMUP
1434,VL53L0X,100,100.00,OK_FILTERED
```

El tiempo `ts_ms` se toma tras la lectura. El periodo nominal es **100 ms** y el timing budget configurado es **50 ms**; el programa comprueba que el periodo sea al menos tan largo como el budget y que la librería acepte este último. La cadencia real y la duración de lectura requieren medición en hardware. `OK_WARMUP` indica que aún faltan lecturas para la mediana de tres y `distance_filtrada_mm=NA`. `OK_FILTERED` indica una lectura válida incorporada al filtro. Una lectura inválida produce `INVALID_RANGE`, un timeout `TIMEOUT` y una pérdida I2C `I2C_LOST`, siempre con valor filtrado `NA`. Las líneas de diagnóstico de inicialización empiezan por `ERROR`. Ante pérdida/timeout se intenta detectar de nuevo cada ~2 s.

## Filtro y ajuste

El filtro aplica primero una **mediana móvil de 3 lecturas válidas** y luego una **EMA**: `y[n] = α·mediana[n] + (1−α)·y[n−1]`. La primera EMA se inicializa con la primera mediana completa. `α = 0.4` se configura en `platformio.ini` mediante `-DVL53_EMA_ALPHA=0.4f`; cambiarlo a un valor `>0` y `<=1` y recompilar. Un valor menor suaviza más pero responde más lento; `1.0` conserva solo la mediana. Tras rango inválido, timeout, pérdida I2C o reinicialización, el filtro se reinicia: hacen falta tres lecturas **nuevas y válidas** antes de volver a mostrar un valor filtrado.

Comparación a 100 ms nominales con la señal simulada `100, 100, 100, 200, 200, 200` mm: la lectura sin filtrar salta a **200 mm** en la cuarta muestra; la mediana+EMA produce **100, 140, 164 mm** en las muestras cuarta a sexta. El cambio aparece tras la segunda muestra del nuevo nivel, aproximadamente **100 ms después** del primer salto raw, y la EMA continúa acercándose a 200 mm. Un pico aislado `1000` mm entre lecturas de `100` mm deja la salida filtrada en `100` mm. Son resultados simulados, no mediciones del VL53L0X. El retardo real depende de la cadencia efectiva, de la lectura I2C y del blanco; comparar columnas raw/filtrada y timestamps en el banco antes de ajustar `α` o el periodo.

Las pruebas del filtro C++ real, sin hardware, se ejecutan en Windows con Visual Studio C++ Build Tools:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File sensor-tests/vl53/tests/run_filter_sim.ps1
```

## Criterios de aceptación en banco

- **PASS de software:** `pio run -d sensor-tests/vl53` termina con `SUCCESS`. Esto no confirma el sensor físico.
- **PASS físico:** referencia exacta del módulo y niveles documentados; un único modelo identificado; al menos 10 líneas `OK_FILTERED` consecutivas; con un blanco mate a 100 mm y 200 mm medidos desde el sensor, las medianas de 10 lecturas **raw** en cada posición difieren en el sentido correcto y quedan dentro de ±30 mm de cada referencia. Comparar también la dispersión y el retardo de la columna filtrada frente a raw. Registrar modelo, módulo, alimentación, distancia de referencia, medianas, timestamps y errores.
- **FAIL:** modelo desconocido, `ERROR` persistente, lecturas ausentes, incoherentes o fuera del criterio anterior. Detener la prueba y revisar cableado, nivel I2C, alimentación y ficha del módulo antes de repetir. No inferir compatibilidad por compilación o ACK en `0x29`.

## Evidencia de la versión inicial del PR #2

- **PASS:** rama `feature/vl53-test` basada en `main` `0d15505`; `pio run -d sensor-tests/vl53` terminó en `SUCCESS` con PlatformIO Espressif32 `7.1.3`, Arduino y librerías Pololu `1.3.1` para ambos modelos.
- **PASS:** `pio run -d firmware` terminó en `SUCCESS`; el proyecto principal no fue modificado.
- **PARTIAL:** la detección por registro, el manejo de errores y las distancias se compilaron, pero no se ejecutaron en ESP32.
- **BLOCKED:** modelo físico, esquema eléctrico del módulo, carga y criterios de banco pendientes de identificación del módulo y sesión física autorizada. No se conectó hardware ni se energizaron motores.

## Evidencia de la actualización del filtro

- **PASS:** `powershell -NoProfile -ExecutionPolicy Bypass -File sensor-tests/vl53/tests/run_filter_sim.ps1` ejecutó el mismo filtro C++ con señales simuladas de ruido, pico, escalón y fallo: `PASS: noise, spike, step, sensor failure simulations`.
- **PASS:** `pio run -d sensor-tests/vl53` terminó en `SUCCESS` con periodo configurado a 100 ms, timing budget a 50 ms y `α = 0.4`.
- **PARTIAL:** no se ha medido la cadencia, precisión ni retardo con un ESP32 y VL53 reales. No se cargó firmware ni se conectaron ESC o motores.
