# Primera prueba: flechas y ambos motores

Esta carpeta contiene un firmware ESP32 independiente y un [HTML local](index.html). **Habilitar** mantiene ambos ESC en 1000 µs. El primer ↑ sube a 1100 µs; las siguientes pulsaciones ↑/↓ cambian **ambos ESC a la vez** en pasos de 10 µs, con límite de 1350 µs. `Esc`, **Detener**, perder el foco de la página o 250 ms sin mensajes USB devuelven la señal a 1000 µs y deshabilitan el control.

El botón **Máximo seguro: 1350 µs** lleva ambos ESC directamente al límite seguro documentado para este proyecto. No representa la potencia máxima nominal del motor o ESC; esa cifra requiere sus modelos y especificaciones.

## Uso

1. Retira las hélices. Verifica GND común entre ESP32 y ESC, y que la LiPo alimente solo los ESC. Consulta [cableado y seguridad](../../docs/WIRING_AND_SAFETY.md).
2. Conecta las señales de los ESC a GPIO25 (izquierdo) y GPIO26 (derecho).
3. Compila y carga este proyecto PlatformIO en el ESP32:

   ```powershell
   pio run -d motor-tests/arrow-control -t upload --upload-port COM6
   ```

   Cambia `COM6` por el puerto real. Cierra el monitor Serial antes de abrir la página.
4. Abre [index.html](index.html) en Chrome o Edge de escritorio, pulsa **Conectar ESP32**, elige su puerto USB y luego **Habilitar motores**. Usa ↑ y ↓. Pulsa **Detener** al terminar.

Si el navegador no permite Web Serial desde el archivo local, desde la raíz del repositorio ejecuta:

```powershell
py -3 -m http.server 8000 --bind 127.0.0.1 --directory motor-tests/arrow-control
```

Abre `http://localhost:8000/index.html`.

El número en la página es la **orden enviada**, no una medición de velocidad ni confirmación del ESC. Esta prueba no lee los sensores ni aplica límites de ángulo o posición del riel. Confirma físicamente la respuesta y el sentido de giro sin hélices antes de avanzar.
