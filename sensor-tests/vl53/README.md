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

Salida esperada: `DETECTED model=...`, `READY model=...` y líneas `DATA model=... distance_mm=... status=OK` cada ~500 ms. Los errores tienen prefijo `ERROR`: ausencia o pérdida de respuesta I2C, identificador desconocido, inicialización fallida, timeout o rango inválido. Ante pérdida/timeout se intenta detectar de nuevo cada ~2 s; una línea `DATA` solo se emite para una lectura considerada válida por la librería.

## Criterios de aceptación en banco

- **PASS de software:** `pio run -d sensor-tests/vl53` termina con `SUCCESS`. Esto no confirma el sensor físico.
- **PASS físico:** referencia exacta del módulo y niveles documentados; un único modelo identificado; al menos 10 líneas `DATA ... status=OK` consecutivas; con un blanco mate a 100 mm y 200 mm medidos desde el sensor, las medianas de 10 lecturas en cada posición difieren en el sentido correcto y quedan dentro de ±30 mm de cada referencia. Registrar modelo, módulo, alimentación, distancia de referencia, medianas y errores.
- **FAIL:** modelo desconocido, `ERROR` persistente, lecturas ausentes, incoherentes o fuera del criterio anterior. Detener la prueba y revisar cableado, nivel I2C, alimentación y ficha del módulo antes de repetir. No inferir compatibilidad por compilación o ACK en `0x29`.

## Evidencia de esta entrega

- **PASS:** rama `feature/vl53-test` basada en `main` `0d15505`; `pio run -d sensor-tests/vl53` terminó en `SUCCESS` con PlatformIO Espressif32 `7.1.3`, Arduino y librerías Pololu `1.3.1` para ambos modelos.
- **PASS:** `pio run -d firmware` terminó en `SUCCESS`; el proyecto principal no fue modificado.
- **PARTIAL:** la detección por registro, el manejo de errores y las distancias se compilaron, pero no se ejecutaron en ESP32.
- **BLOCKED:** modelo físico, esquema eléctrico del módulo, carga y criterios de banco pendientes de identificación del módulo y sesión física autorizada. No se conectó hardware ni se energizaron motores.
