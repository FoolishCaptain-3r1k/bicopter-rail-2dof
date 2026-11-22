# BNO055: diagnóstico independiente por Serial y Wi-Fi

Proyecto PlatformIO para ESP32 DevKit y módulo **GY-BNO055**. No incluye VL53, ESC, PWM ni control de motores. Usa la biblioteca Adafruit BNO055 1.6.4 y Arduino ESP32. El cableado GPIO21/22 y ADD a GND, junto con la detección `0x28` en IMUPLUS, fueron confirmados por el equipo; aún se debe comprobar la ficha eléctrica del breakout concreto.

## Diagnóstico I2C actual (predeterminado)

El entorno `esp32dev` compila con `BNO_DIAG_MODE=1`, `BNO_ENABLE_WIFI=0`, adquisición y Serial objetivo **10 Hz**, I2C **100 kHz**. En VS Code abrir `sensor-tests/bno055` como proyecto PlatformIO, seleccionar `env:esp32dev`, ejecutar **Build** y luego **Upload** solo con ESP32 + GY-BNO055 conectados y cableado verificado. Abrir **Monitor** a 115200. Equivalentes desde la raíz: `pio run -d sensor-tests/bno055 -e esp32dev`, `pio run -d sensor-tests/bno055 -e esp32dev -t upload` y `pio device monitor -b 115200`.

La salida informa `CHIP address=0x28 id=0xA0`, modo, reloj y si usa STOP entre selección de registro y lectura. En el modo diagnóstico, por muestra imprime `STATUS system=... selftest=... error=...` y `RAW Euler=... accel=... gyro=... quat=... norm=...`, además del CSV habitual. Ambas variantes leen **aceleración total**, incluida la gravedad. `I2C_FAIL reg=... phase=write/read` identifica el registro y el tramo fallido. `INVALID reason=...` identifica un error del sistema, una transacción I2C, una variable no finita o `quaternion_norm` fuera de 0.5–1.5. Una muestra fallida nunca aparece como `OK`; el programa reintenta iniciar cada 2 s tras una pérdida de comunicación.

La lectura del Chip ID se realiza al iniciar, no antes de cada muestra. El diagnóstico configura el modo con escrituras I2C directas y usa STOP por defecto (`BNO_I2C_RESTART=0`) al leer registros; `1` permite comparar repeated-start en otra compilación. La biblioteca Adafruit usa repeated-start en sus lecturas internas y no propaga el fallo de `readLen()` a `getVector()`/`getQuat()`, motivo por el que el modo diagnóstico comprueba cada transacción directamente. El reloj queda en 100 kHz hasta medir resultados físicos; `BNO_I2C_HZ=50000UL` es una comparación posterior si continúan los fallos tras revisar alimentación, tierra y pull-ups. **Compilar no demuestra que STOP o 50 kHz solucionen el problema.**

Para usar el dashboard, seleccionar `env:esp32dev_wifi` (`BNO_DIAG_MODE=0`, `BNO_ENABLE_WIFI=1`) y compilar/cargar esa configuración. Reutiliza la misma inicialización y lectura I2C directa del diagnóstico, con STOP entre selección de registro y lectura a 100 kHz; reduce únicamente el detalle de las líneas de depuración. Ambas variantes tienen adquisición y Serial objetivo de 10 Hz; la página consulta la API a 10 Hz. No se aplica ningún filtro.

## Cableado y primera prueba

Con USB desconectado, identificar el fabricante y referencia exacta del breakout. Consultar su ficha para confirmar alimentación, pull-ups de SDA/SCL y conversión de niveles. Solo si el módulo acepta **3.3 V de alimentación y bus I2C de 3.3 V** conectar: ESP32 `3V3 → VCC/VIN`, `GND → GND`, `GPIO21 → SDA`, `GPIO22 → SCL`. Para dirección `0x28`, conectar `ADR/ADD → GND` únicamente si el fabricante lo especifica; `0x29` se detecta como alternativa, pero puede chocar con un VL53 futuro. No aplicar 5 V a GPIO del ESP32. Verificar continuidad de GND y ausencia de cortos antes de conectar USB. Mantener ESC, motores, hélices y LiPo desconectados. Consultar [seguridad](../../docs/WIRING_AND_SAFETY.md).

En VS Code con PlatformIO, abrir este repositorio y seleccionar `sensor-tests/bno055` como proyecto. Desde PowerShell en la raíz:

```powershell
pio run -d sensor-tests/bno055
powershell -NoProfile -ExecutionPolicy Bypass -File sensor-tests/bno055/tests/run_native.ps1
```

En el entorno `esp32dev_wifi`, el ESP32 anuncia `Bicopter-IMU-Test`, la contraseña de **prueba pública** `BicopterIMU2026!`, la IP del AP y el estado HTTP. Conectar el teléfono/PC a esa red y abrir la IP mostrada (normalmente `http://192.168.4.1/`). No necesita internet ni CDN. Para usar otra contraseña, definir `BNO_AP_PASSWORD` como build flag **local** de 8–63 caracteres; no subir credenciales privadas al repositorio. El código usa WPA2 mediante `WiFi.softAP` con contraseña. `BNO_USE_NDOF=0` selecciona IMUPLUS; cambiar el flag a `1` y recompilar solo para ensayos posteriores.

## Lecturas y convenciones

Los registros entregan Euler `heading/yaw`, `roll`, `pitch` en grados, giróscopo en °/s y aceleración total en m/s². Se publican en el marco **del sensor**, sin remapeo de montaje. Euler y cuaternión provienen de la fusión interna; la aceleración total incluye gravedad. El cuaternión se muestra como `w,x,y,z` y evita la singularidad de Euler. En IMUPLUS no hay norte magnético absoluto, así que yaw puede derivar. Los cuatro niveles de calibración van de 0 a 3; el magnético puede permanecer bajo en IMUPLUS.

Serial a 115200 publica la cabecera `ts_ms,roll_deg,pitch_deg,yaw_deg,gx_dps,gy_dps,gz_dps,ax_ms2,ay_ms2,az_ms2,cal_sys,cal_gyro,cal_accel,cal_mag,status` a 10 Hz objetivo. Solo marca `OK` si hay una muestra nueva y reciente; de lo contrario publica `INVALID` con `NA`. La adquisición intenta 10 Hz y el navegador consulta `/api/imu` a 10 Hz. La API entrega `data:null` si la muestra es inválida, caducó (>200 ms) o el sensor se desconectó. Ante pérdida I2C reintenta inicialización cada 2 s. La frecuencia efectiva se calcula con timestamps.

La página tiene orientación numérica, vista esquemática de roll/pitch, ejes de giro/aceleración, calibración y diagnóstico. La vista no representa una actitud absoluta del bicóptero: verificar el montaje y los signos antes de usarla como referencia. El servidor HTTP corre en núcleo 0 y las lecturas I2C en el bucle del núcleo 1, con intercambio breve de una copia de datos. RAM estática de compilación: consultar resultado de PlatformIO; la página reside en flash y no hay librerías web externas.

## Aceptación física pendiente

**PASS final** si el módulo y niveles están documentados, se detecta en `0x28` o `0x29`, Serial y web muestran lecturas nuevas durante al menos 60 s, la orientación cambia coherentemente al girar el sensor en cada eje, la calibración se informa, y las tasas medidas se aproximan a 10 Hz sin muestras caducadas persistentes. Probar recuperación ante desconexión del sensor solo con USB apagado. **FAIL** si hay datos `OK` caducados, ejes incoherentes o fallos persistentes. Registrar modelo del breakout, dirección, capturas, tiempos y errores. La respuesta controlada de los tres ejes y la consulta HTTP física siguen pendientes.

## Evidencia de software

- **PASS** `pio run -d sensor-tests/bno055 -e esp32dev`: `SUCCESS`; RAM 6.7 %, flash 22.3 %.
- **PASS** `pio run -d sensor-tests/bno055 -e esp32dev_wifi`: `SUCCESS`; RAM 13.9 %, flash 61.2 %.
- **PASS** `tests/run_native.ps1`: `PASS: axes, serialization, invalid and stale states`, incluidas razones `gy` y `quaternion_norm`.
- **PASS** se cargó `.pio/build/esp32dev_wifi/firmware.bin` en COM6; esptool verificó el hash y terminó en `SUCCESS`.
- **PARTIAL** se observó el sensor por Serial más de 60 s en ambas variantes. La prueba controlada de roll, pitch y yaw, la ficha eléctrica del breakout y la respuesta HTTP del dashboard siguen pendientes.

## Verificación en COM6 (22 de noviembre de 2026)

Se compiló desde cero `env:esp32dev` y PlatformIO cargó `.pio/build/esp32dev/firmware.bin` por COM6; esptool verificó los hashes y terminó en `SUCCESS`. El monitor a 115200 mostró `diagnostic=1 wifi=0 I2C=100000`, Chip ID `0xA0` en `0x28`, `system=5`, autoprueba `0x0F` y error `0`.

La primera observación expuso una dirección equivocada en el propio diagnóstico: `0x3B` es `UNIT_SEL`, no `SYS_ERR`; las direcciones correctas de Adafruit son `SELFTEST=0x36`, `SYS_STAT=0x39` y `SYS_ERR=0x3A`. Después de corregirlas, el cuaternión seguía temporalmente en cero. Se restituyó el reset e inicio de modo que utiliza la biblioteca y se dejó de reiniciar por una muestra inválida sin fallo I2C. Tras el arranque aparecieron lecturas `OK` con norma `1.0000`, por ejemplo a `7056 ms`: roll `-2.50°`, pitch `1.12°`, yaw `359.94°`, aceleración total `(-0.42,-0.20,10.17) m/s²`. Los timestamps de muestras consecutivas rondaron 109–110 ms, aproximadamente 9.1 Hz en esta observación. Los NACK `code=2` durante el reset se observaron antes de la recuperación del Chip ID; no se atribuyen a muestras válidas.

**Nueva observación diagnóstica:** captura Serial de 75 s: 677 muestras válidas entre `940` y `74766 ms` (73.8 s), 50 fallos `I2C_FAIL reg=0x00 phase=write code=2` durante el reinicio del chip. La captura resumida no separó los fallos anteriores y posteriores a la primera muestra válida. Los valores observados cubrieron roll `-58.94` a `25.50°`, pitch `-21.12` a `33.62°` y yaw `0` a `359.94°`; esos cambios no constituyen una prueba de movimiento controlado ni validan los signos de los ejes.

**Variante Wi-Fi:** se compiló y cargó `env:esp32dev_wifi` por COM6; esptool verificó el hash y terminó en `SUCCESS`. Captura Serial de 65 s después de abrir el puerto: `AP=Bicopter-IMU-Test ... IP=192.168.4.1 status=OK`, `HTTP server ready port=80`, Chip ID `0xA0` en `0x28`, 581 líneas `OK`, cuatro `INVALID` iniciales y 48 `I2C_FAIL` de reinicio antes de la primera muestra válida. No hubo fallos I2C después de esa primera muestra en la captura; las muestras válidas abarcaron `1039` a `64654 ms` (63.6 s), cerca de 9.1 Hz. El PC solo detectó su red `MeshMR1` durante el escaneo, por lo que no se comprobó una petición real a `/api/imu` ni la actualización visual del dashboard. La publicación del AP y el inicio del servidor solo quedaron verificados por Serial.

**Estado:** PASS compilación, pruebas nativas, carga y telemetría Serial sostenida; PARTIAL estabilidad I2C por los NACK durante reset y falta de ensayo controlado de ejes; BLOCKED verificación HTTP física desde este PC mientras el AP no sea visible. No se conectaron motores ni ESC.
