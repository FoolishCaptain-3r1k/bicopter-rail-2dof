# BNO055: prueba independiente por USB Serial

Proyecto PlatformIO/Arduino para ESP32 DevKit y GY-BNO055. El único entorno es `esp32dev`: sin Wi-Fi, AP, WebServer, Adafruit, filtros digitales externos ni control de motores. La interfaz de computadora se implementará después; esta prueba entrega diagnóstico y CSV por USB a **115200 baudios**.

## Cableado

Con USB desconectado, verificar la ficha del breakout concreto: alimentación admitida, regulador y pull-ups. Si acepta alimentación y bus de 3.3 V:

| ESP32 | GY-BNO055 |
| --- | --- |
| 3V3 | VCC/VIN compatible con 3.3 V |
| GND | GND |
| GPIO21 | SDA |
| GPIO22 | SCL |
| GND | ADD/ADR, para dirección 0x28 |

No aplicar 5 V a los GPIO. Revisar continuidad de GND y ausencia de cortos antes de conectar USB. Mantener LiPo, ESC, motores y hélices desconectados. Esta prueba usa **100 kHz** aunque el bus del firmware principal tenga otra configuración. Ver [seguridad](../../docs/WIRING_AND_SAFETY.md). La referencia y ficha eléctrica exacta del breakout siguen pendientes de registrar.

## Compilar, cargar y observar desde VS Code

Abrir `sensor-tests/bno055` como proyecto PlatformIO, seleccionar `env:esp32dev`, ejecutar **Build**, **Upload** y **Monitor**. Cerrar otros monitores que ocupen COM6. Equivalentes desde la raíz:

```powershell
pio run -d sensor-tests/bno055 -e esp32dev
pio run -d sensor-tests/bno055 -e esp32dev -t upload --upload-port COM6
pio device monitor --port COM6 --baud 115200
powershell -NoProfile -ExecutionPolicy Bypass -File sensor-tests/bno055/tests/run_native.ps1
```

El antiguo entorno `esp32dev_wifi` fue retirado. La rama conserva su nombre para continuar el PR #3 existente. No se necesita conectarse a ninguna red.

## Adquisición y validación

- I2C a 100 kHz, timeout explícito de **50 ms por transacción**, STOP entre selección de registro y lectura. El timeout individual no es una garantía del tiempo total de adquisición.
- Espera inicial de 700 ms antes de acceder al sensor. Tras reset por software, espera de 650 ms seguida de sondeo del Chip ID con límite de 1200 ms. El reset y la configuración pueden bloquear durante ese intervalo: este es un diagnóstico independiente, no un lazo de control.
- Detecta Chip ID `0xA0` en `0x28`; también admite `0x29` como alternativa, sin VL53 conectado. Inicializa IMUPLUS con escrituras directas; no comprueba Chip ID antes de cada muestra.
- Una ráfaga de 32 bytes desde `0x08` hasta `0x27` contiene acelerómetro, magnetómetro (no usado), giróscopo, Euler y cuaternión. Estado, autoprueba, error y calibración se leen por separado. Las lecturas se convierten a unidades físicas, sin mediana, EMA ni Kalman. La fusión interna IMUPLUS permanece activa.
- Adquisición y CSV a 10 Hz objetivo. Se imprime `STATUS system=... selftest=... error=...` y `RAW Euler=... accel=... gyro=... quat=... norm=...`. El campo `norm` representa la norma al cuadrado.
- `I2C_FAIL reg=... phase=...` identifica la transacción fallida. `INVALID reason=...` identifica error del sistema, variable no finita o norma al cuadrado fuera de `(0.5,1.5)`. Una transacción incompleta invalida toda la muestra. Los fallos de comunicación provocan reinicialización tras 2 s; una muestra inválida sin fallo de comunicación no reinicia el chip.
- El CSV solo marca `OK` para una muestra válida, nueva y con edad no mayor de 200 ms. En otro caso imprime `NA` e `INVALID`; nunca reutiliza una muestra anterior como nueva.

Cabecera CSV:

```text
ts_ms,roll_deg,pitch_deg,yaw_deg,gx_dps,gy_dps,gz_dps,ax_ms2,ay_ms2,az_ms2,cal_sys,cal_gyro,cal_accel,cal_mag,status
```

Euler se publica como roll, pitch y yaw en grados, giróscopo en grados/s y aceleración **total**, incluida gravedad, en m/s². El cuaternión se imprime W/X/Y/Z en el diagnóstico RAW. No hay remapeo de montaje. En IMUPLUS yaw puede derivar porque no tiene referencia magnética absoluta. Los niveles de calibración son 0–3; el magnetómetro no participa en IMUPLUS.

## Criterios de aceptación

**PASS:** Chip ID y modo correctos, estado sin error, lecturas nuevas por al menos 60 s, sin errores de comunicación durante la adquisición estable; roll, pitch y yaw responden coherentemente al girar cada eje de forma controlada. Registrar tasa real y comprobar invalidación/recuperación ante pérdida del sensor, cambiando el cableado solo con USB desconectado.

**FAIL:** errores persistentes, datos corruptos publicados como OK, muestras caducadas reutilizadas, cuaternión inválido persistente o signos/ejes incoherentes.

**PARTIAL:** compila y entrega datos, pero faltan movimientos controlados, comprobación eléctrica o ensayo de recuperación. Una captura Serial no demuestra que una caída de alimentación haya sido la causa del problema previo.

## Evidencia de esta revisión

- **PASS** compilación `esp32dev`: SUCCESS, RAM 21896 bytes (6.7 %), flash 290641 bytes (22.2 %). Dependencia detectada: únicamente Wire.
- **PASS** pruebas nativas: `PASS: axes, serialization, invalid and stale states`. Verifican conversión de ejes, CSV, valores no finitos, norma de cuaternión y caducidad; no simulan un bus I2C real.
- **PASS** carga explícita de `.pio/build/esp32dev/firmware.bin` por COM6: hashes verificados, reset mediante RTS y SUCCESS.
- **PASS** captura física de 65.01 s en COM6: 632 muestras OK entre 1630 y 64731 ms (63.101 s de muestras válidas), 10.00 Hz efectivos y cero fallos I2C registrados. Una muestra se rechazó por `quaternion_norm` y se publicó como INVALID. Evidencia: consultar [captura resumida](tests/evidence/usb-validation.json). Las capturas Wi-Fi anteriores pertenecen a otra versión y no validan esta revisión.
- **PARTIAL** movimiento controlado de los tres ejes, identificación eléctrica exacta del breakout y ensayo de desconexión/recuperación pendientes. No se accionaron ESC ni motores.
