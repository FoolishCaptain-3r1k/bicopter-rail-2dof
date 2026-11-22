# BNO055: diagnóstico independiente por Serial y Wi-Fi

Proyecto PlatformIO para ESP32 DevKit y BNO055. No incluye VL53, ESC, PWM ni control de motores. Usa la biblioteca Adafruit BNO055 1.6.4 y Arduino ESP32. El módulo físico del equipo y sus niveles eléctricos aún deben confirmarse.

## Cableado y primera prueba

Con USB desconectado, identificar el fabricante y referencia exacta del breakout. Consultar su ficha para confirmar alimentación, pull-ups de SDA/SCL y conversión de niveles. Solo si el módulo acepta **3.3 V de alimentación y bus I2C de 3.3 V** conectar: ESP32 `3V3 → VCC/VIN`, `GND → GND`, `GPIO21 → SDA`, `GPIO22 → SCL`. Para dirección `0x28`, conectar `ADR/ADD → GND` únicamente si el fabricante lo especifica; `0x29` se detecta como alternativa, pero puede chocar con un VL53 futuro. No aplicar 5 V a GPIO del ESP32. Verificar continuidad de GND y ausencia de cortos antes de conectar USB. Mantener ESC, motores, hélices y LiPo desconectados. Consultar [seguridad](../../docs/WIRING_AND_SAFETY.md).

En VS Code con PlatformIO, abrir este repositorio y seleccionar `sensor-tests/bno055` como proyecto. Desde PowerShell en la raíz:

```powershell
pio run -d sensor-tests/bno055
powershell -NoProfile -ExecutionPolicy Bypass -File sensor-tests/bno055/tests/run_native.ps1
```

Solo tras autorizar y verificar la sesión física: `pio run -d sensor-tests/bno055 -t upload` y `pio device monitor -b 115200`. El ESP32 anuncia `Bicopter-IMU-Test`, la contraseña de **prueba pública** `BicopterIMU2026!`, la IP del AP y el estado HTTP. Conectar el teléfono/PC a esa red y abrir la IP mostrada (normalmente `http://192.168.4.1/`). No necesita internet ni CDN. Para usar otra contraseña, definir `BNO_AP_PASSWORD` como build flag **local** de 8–63 caracteres; no subir credenciales privadas al repositorio. El código usa WPA2 mediante `WiFi.softAP` con contraseña. `BNO_USE_NDOF=0` selecciona IMUPLUS; cambiar el flag a `1` y recompilar solo para ensayos posteriores.

## Lecturas y convenciones

El driver devuelve Euler `x=heading/yaw`, `y=roll`, `z=pitch`, en grados; `VECTOR_GYROSCOPE` devuelve °/s y `VECTOR_LINEARACCEL` m/s². Se publican en el marco **del sensor**, sin remapeo de montaje. Euler, cuaternión y aceleración lineal provienen de la fusión interna; la velocidad angular proviene del giróscopo. El cuaternión se muestra como `w,x,y,z` y evita la singularidad de Euler. En IMUPLUS no hay norte magnético absoluto, así que yaw puede derivar. Los cuatro niveles de calibración van de 0 a 3; el magnético puede permanecer bajo en IMUPLUS. Convenciones verificadas contra el [código de Adafruit](https://github.com/adafruit/Adafruit_BNO055/blob/master/Adafruit_BNO055.cpp) y su [guía](https://learn.adafruit.com/adafruit-bno055-absolute-orientation-sensor).

Serial a 115200 publica la cabecera `ts_ms,roll_deg,pitch_deg,yaw_deg,gx_dps,gy_dps,gz_dps,ax_ms2,ay_ms2,az_ms2,cal_sys,cal_gyro,cal_accel,cal_mag,status` a 20 Hz objetivo. Solo marca `OK` si hay una muestra nueva y reciente; de lo contrario publica `INVALID` con `NA`. La adquisición intenta 50 Hz y el navegador consulta `/api/imu` a 10 Hz. La API entrega `data:null` si la muestra es inválida, caducó (>200 ms) o el sensor se desconectó. Ante pérdida I2C reintenta inicialización cada 2 s. La frecuencia efectiva se calcula con timestamps; la tasa real requiere comprobación física.

La página tiene orientación numérica, vista esquemática de roll/pitch, ejes de giro/aceleración, calibración y diagnóstico. La vista no representa una actitud absoluta del bicóptero: verificar el montaje y los signos antes de usarla como referencia. El servidor HTTP corre en núcleo 0 y las lecturas I2C en el bucle del núcleo 1, con intercambio breve de una copia de datos. `WebServer` y las transferencias I2C pueden bloquear en su propio núcleo; no se garantiza 50 Hz hasta medirlo. RAM estática de compilación: consultar resultado de PlatformIO; la página reside en flash y no hay librerías web externas.

## Aceptación física pendiente

**PASS** si el módulo y niveles están documentados, se detecta en `0x28` o `0x29`, Serial y web muestran lecturas nuevas durante al menos 60 s, la orientación cambia coherentemente al girar el sensor en cada eje, la calibración se informa, y las tasas medidas se aproximan a 50/20/10 Hz sin muestras caducadas persistentes. Desconectar brevemente solo el sensor con USB apagado y repetir para comprobar recuperación. **FAIL** si hay datos `OK` caducados, ejes incoherentes, fallos persistentes o AP inseguro. Registrar modelo del breakout, dirección, capturas, tiempos y errores. Estas comprobaciones no se han realizado aquí.

## Evidencia de software

- **PASS** `pio run -d sensor-tests/bno055`: `SUCCESS`; RAM 13.9 % (45568/327680 B), flash 61.1 % (801113/1310720 B).
- **PASS** `tests/run_native.ps1`: `PASS: axes, serialization, invalid and stale states`.
- Sin carga ni validación física en esta entrega.
