# BNO055 + VL53L0X por USB

Prueba integrada independiente para ESP32 DevKit, Arduino y PlatformIO. Publica orientación y distancia por el mismo USB a **115200 baudios**. Incluye [dashboard.html](dashboard.html) con estados independientes, vista de orientación, gráficas de 20 s, aceleración total, giro y calibración. Sin Wi-Fi, filtros externos, control, ESC ni motores.

## Conectar ambos sensores

Desconectar USB antes de cablear. Verificar en las fichas de los **módulos concretos** que admitan alimentación y bus de 3.3 V. Revisar reguladores, conversores y pull-ups: al poner dos placas en paralelo sus pull-ups también quedan en paralelo. No aplicar 5 V a GPIO del ESP32. Confirmar tierra común y ausencia de cortos.

| ESP32 | BNO055 | VL53L0X |
| --- | --- | --- |
| 3V3 | VCC/VIN compatible con 3.3 V | VCC/VIN compatible con 3.3 V |
| GND | GND y ADD/ADR | GND |
| GPIO21 | SDA | SDA |
| GPIO22 | SCL | SCL |

**ADD a GND es obligatorio en esta integración:** BNO055 en `0x28`, VL53L0X en `0x29`. No se intenta mover direcciones automáticamente. `GPIO19/XSHUT` queda sin conectar si el módulo mantiene el sensor habilitado; comprobar su ficha. El firmware no controla XSHUT ni GPIO25/26. Mantener batería LiPo, ESC, motores y hélices desconectados; seguir [seguridad](../../docs/WIRING_AND_SAFETY.md).

Se comprueba BNO055 Chip ID `0xA0` en `0x28` y VL53L0X ID `0xEE` en `0x29` antes de inicializar. **VL53L1X no está soportado** en esta prueba integrada; se rechaza un ID diferente. No inferir el modelo por el ACK o la dirección.

## Cargar desde VS Code

Abrir `sensor-tests/dual-usb` como proyecto PlatformIO y seleccionar `env:esp32dev`. Cerrar el monitor Serial y desconectar el HTML del puerto antes de **Build / Upload**. Desde la raíz del repositorio:

```powershell
pio run -d sensor-tests/dual-usb -e esp32dev
pio run -d sensor-tests/dual-usb -e esp32dev -t upload --upload-port COM6
```

Solo cargar después de revisar el cableado anterior. Esta carga sustituye la prueba individual que esté grabada en el ESP32.

## Abrir la interfaz

Abrir [dashboard.html](dashboard.html) en Chrome o Edge de escritorio, pulsar **Conectar ESP32** y seleccionar COM6 / CP210x. Cerrar otros monitores: solo una aplicación puede usar el puerto. Esperar el arranque; abrir el puerto puede reiniciar el ESP32. El HTML solo lee datos, sin enviar comandos ni requerir internet o bibliotecas externas.

Si el navegador no permite Web Serial al abrir directamente el archivo:

```powershell
py -3 -m http.server 8000 --bind 127.0.0.1 --directory sensor-tests/dual-usb
```

Abrir `http://localhost:8000/dashboard.html`. El servidor solo entrega la página. Pulsar **Desconectar** antes de volver a cargar firmware. Para inspeccionar texto en lugar del HTML:

```powershell
pio device monitor --port COM6 --baud 115200
```

## Muestreo, fallos y protocolo

Bus compartido a **100 kHz**, timeout Wire explícito de **50 ms por transacción**. Todas las operaciones del bus se ejecutan secuencialmente en el bucle principal. Los periodos son objetivos; una inicialización o pérdida del bus puede retrasar ambos sensores. Esta prueba no garantiza plazos para un lazo de control.

- **BNO055:** conserva las transacciones directas con STOP, reset, IMUPLUS y validaciones de la prueba USB aceptada en `1982717`. Ráfaga de 32 bytes; sin Adafruit. Adquisición objetivo de **100 ms**. Comprueba comunicación, error del sistema, valores finitos y norma de cuaternión. Los encabezados `include/diagnostic.h` y `telemetry.h` son copias de esa versión para mantener este proyecto compilable por sí solo.
- **VL53L0X:** inicialización Pololu 1.3.1 con timeout de 100 ms, timing budget **50 ms**, continuo con periodo solicitado de 50 ms y publicación cada **500 ms**, como la prueba individual sin filtros. Para leer resultados se comprueban directamente la longitud I2C, disponibilidad y limpieza de interrupción. Se rechazan distancia >=8190 y estado hardware distinto de 11. Esta comprobación es conservadora; no implementa las validaciones completas sigma/señal de la API PAL de ST. Los valores hardware no son los códigos de estado PAL. Ver [implementación ST de referencia](https://github.com/zephyrproject-rtos/hal_st/blob/master/sensor/vl53l0x/api/core/src/vl53l0x_api_core.c) y [Pololu 1.3.1](https://github.com/pololu/vl53l0x-arduino/tree/1.3.1).
- Un fallo de comunicación invalida el sensor afectado y programa reintento de inicio tras aproximadamente 2 s. VL53 sin resultado listo durante más de 1500 ms provoca reinicialización. Un dato numérico inválido no se publica como OK. Las inicializaciones pueden bloquear; una SDA retenida afecta físicamente a todo el bus y requiere revisar cableado/alimentación.
- El HTML oculta BNO055 tras 500 ms sin muestra nueva y distancia tras 1500 ms. INVALID y errores de comunicación ocultan inmediatamente el dato correspondiente. Un fallo ToF no invalida la IMU en la interfaz. Las gráficas conservan solo historial y separan los huecos; no suavizan lecturas.

Cada adquisición tiene su timestamp y estado; los sensores **no son muestras sincronizadas**. Nunca se vuelve a publicar una muestra guardada como nueva:

```text
IMU,ts_ms,roll,pitch,yaw,gx,gy,gz,ax,ay,az,cal_sys,cal_gyro,cal_accel,cal_mag,status
TOF,ts_ms,distance_mm,status,device_status_raw
```

Ejemplos de formato (ilustrativos):

```text
IMU,1630,-2.75,1.19,0.00,-0.06,-0.12,-0.06,-0.52,-0.23,10.21,0,0,0,0,OK
TOF,1700,245,OK,11
TOF,2200,NA,I2C_FAIL,NA
```

Euler en grados, giro en °/s, aceleración total en m/s² y distancia en mm. Las líneas de diagnóstico empiezan por `#`; se distinguen las de ToF con `# TOF`. La orientación es esquemática, sin remapeo de montaje; yaw puede derivar en IMUPLUS. La distancia no se convierte a altura del riel sin calibrar montaje y referencia.

## Pruebas y evidencia

```powershell
node --test sensor-tests/dual-usb/tests/dashboard.test.cjs
powershell -NoProfile -ExecutionPolicy Bypass -File sensor-tests/dual-usb/tests/run_native.ps1
```

- **PASS:** compilación PlatformIO `esp32dev`, SUCCESS; RAM 21840 bytes (6.7 %), flash 294885 bytes (22.5 %).
- **PASS:** 2 pruebas Node del protocolo y del ciclo USB simulado: fragmentación, CSV corrupto, duplicados, caducidad, invalidación independiente de ambos sensores, apertura/cierre y recuperación de la vista.
- **PASS:** pruebas C++ nativas de ejes, serialización, valores no finitos, cuaternión y caducidad.
- **PARTIAL:** no se cargó esta integración ni se probó con ambos sensores conectados; el bus I2C real, la frecuencia conjunta y el HTML con ambos sensores requieren ensayo físico. Las pruebas unitarias simulan el puerto USB y no el hardware I2C. Las pruebas físicas individuales anteriores no equivalen a validar esta integración.

**Aceptación física:** observar ambos sensores al menos 60 s, comprobar tasas, girar cada eje de la IMU y mover un blanco mate a distancias conocidas. Confirmar que la distancia y la orientación cambian coherentemente. Registrar errores, modelo de módulo y niveles. Con USB apagado, retirar un sensor y reiniciar para comprobar que el otro sigue mostrando datos y el ausente se reporta inválido. Restaurar el cableado con USB apagado y repetir. FAIL ante datos corruptos o caducados como OK, errores persistentes o bloqueo del bus. No accionar ESC ni motores.
