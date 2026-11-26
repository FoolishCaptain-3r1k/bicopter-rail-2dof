# V9 experimental · Control del riel con la palma

La V9 añade visión al dashboard y utiliza el protocolo de la V8 final. Si el ESP32 ya tiene esa versión, puedes usar directamente este panel. La copia incluida del firmware se identifica por USB como `RAIL_PID_USB v8 HEIGHT_SCALE=10`.

## Probar la cámara

Desde esta carpeta, inicia el servidor local con Python.

```powershell
python -m http.server 8769 --bind 127.0.0.1
```

1. Abre el [dashboard V9](http://127.0.0.1:8769/dashboard.html) en Chrome o Edge de escritorio. En **Gestos**, pulsa **Activar cámara** y acepta el permiso.
2. Muestra una sola palma de frente, derecha o izquierda, con los dedos hacia arriba. La vista en espejo dibuja 21 puntos. El contorno verde indica una palma válida y el ámbar pide corregir la orientación.
3. Cada vez que el panel adquiere la palma, la consigna empieza en 0 mm. Mantén el centro de la palma por encima de la franja marcada para sumar 10 mm aproximadamente cada cuarto de segundo. Por debajo se restan 10 mm con el mismo ritmo. Al volver a la franja se conserva el valor alcanzado. La consigna admite alturas positivas y negativas sin topes de software. La escala de la vista previa se ajusta a la consigna.
4. Inclina los dedos como una aguja de reloj para probar la rotación hasta ±20°. Observa **Consigna de la mano** para probar ambos ejes sin USB. Para mover el banco, pulsa **Conectar por USB**, introduce las ganancias de ambos PID, lleva la consigna a una altura distinta de cero y pulsa **Armar con gestos**. Los indicadores de **Mediciones** muestran la respuesta real del ESP32.

Durante el control por gestos, el panel solicita paro si pierde la palma, aparece otra mano, se interrumpe la cámara o la última imagen válida tiene más de medio segundo. Para reanudar el movimiento, vuelve a mostrar la palma y pulsa **Armar con gestos**. **Esc** y **PARO** siguen disponibles.

El navegador procesa el video en la computadora. La carpeta `vision/` incluye el [SDK MediaPipe Tasks Vision 0.10.21](https://www.npmjs.com/package/@mediapipe/tasks-vision/v/0.10.21), su runtime WebAssembly y el [modelo Hand Landmarker FP16 v1](https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task). La prueba funciona sin conexión a Internet.

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
