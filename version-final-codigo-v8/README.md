# Versión final del código v8 — Riel de dos grados de libertad

Proyecto independiente para ESP32 DevKit (`esp32dev`). El firmware se identifica por USB como `RAIL_PID_USB v8 HEIGHT_SCALE=10`.

## Abrir en VS Code

Abrir esta carpeta completa mediante **Archivo → Abrir carpeta**. La extensión **PlatformIO IDE** reconoce `platformio.ini` y permite compilar con **Build** y cargar con **Upload**. Las dependencias se descargan automáticamente en la primera compilación.

Desde una terminal PowerShell situada en esta carpeta también se puede ejecutar:

```powershell
& "$env:USERPROFILE/.platformio/penv/Scripts/pio.exe" run
& "$env:USERPROFILE/.platformio/penv/Scripts/pio.exe" device list
& "$env:USERPROFILE/.platformio/penv/Scripts/pio.exe" run -t upload --upload-port COM6
```

Elegir el puerto real indicado por `device list`. Cerrar la conexión USB del dashboard antes de cargar. La programación se realiza con la batería de motores desconectada.

## Abrir en PyCharm

Abrir esta misma carpeta como proyecto. El firmware C++ se compila y carga con los comandos PlatformIO anteriores desde la terminal del IDE. El cliente Python opcional se instala y ejecuta con:

```powershell
python -m pip install -r requirements.txt
python keyboard_control.py COM6
```

El cliente Python y el dashboard utilizan el mismo puerto USB. Conectar un cliente a la vez.

## Dashboard HTML

Abrir `dashboard.html` en Chrome o Edge de escritorio. Sus recursos están incluidos en esta carpeta:

- `motorlab.css`
- `dashboard.js`
- `dashboard-view.js`
- `capture.js`

Para servir el panel en localhost:

```powershell
python -m http.server 8765 --bind 127.0.0.1
```

Abrir [el dashboard local](http://127.0.0.1:8765/dashboard.html), pulsar **Conectar por USB** y elegir el ESP32. El HTML se ejecuta en la computadora y se comunica con el firmware a 115200 baudios.

## Firmware y conexiones

- `src/main.cpp` contiene la adquisición de sensores y el programa principal.
- `include/controller.h` contiene los dos PID, las rampas, la mezcla de motores y el protocolo.
- `include/diagnostic.h` y `include/telemetry.h` contienen el acceso al BNO055 y sus datos.
- I²C SDA GPIO21 y SCL GPIO22, BNO055 en 0x28 y VL53L0X en 0x29.
- Señal ESC GPIO25 y GPIO26, 50 Hz, con tierra común.

Al encender, el sistema queda desarmado a 1000 µs y toma el origen de altura con el riel abajo e inmóvil. La altura usa `10 × (distancia_origen − distancia_actual)`. Al armar se toma la posición angular actual como cero. Ambos motores suben hasta 1450 µs en aproximadamente un segundo. El PWM posterior cambia hasta 200 µs/s por motor, siguiendo los PID. Paro, sensores inválidos y pérdida de comunicación cortan inmediatamente.

En manual, ↑/↓ cambian la consigna vertical en 10 mm y ←/→ la angular en 1°. En automático se introducen ambas consignas. La v8 admite consignas finitas sin topes de altura o ángulo. La consigna vertical cero conserva su función de reducir gradualmente el mando al mínimo después de entrar al control.

Las ganancias arrancan en cero y deben introducirse antes de armar, con Kp positivo en ambos ejes. La base del control es 1580 µs. El sistema sigue pendiente de identificación experimental para calcular las ganancias.

## Registro de pruebas

En **Registro de pruebas**, iniciar la grabación antes de armar. Marcar cada tramo como referencia, cambio de altura, cambio de inclinación o regreso. Finalizar y descargar el CSV antes de cerrar o recargar el panel. El registro conserva las señales medidas, PWM aplicado, comandos y eventos.
