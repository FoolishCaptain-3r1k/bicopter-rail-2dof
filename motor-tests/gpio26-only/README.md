# Prueba aislada del motor en GPIO26

Este proyecto controla **solo el ESC conectado a GPIO26**. GPIO25 no genera PWM. El ESP32 informa por USB `GPIO26_ONLY,READY` al arrancar y `PWM,<microsegundos>,<estado>` cuando cambia la orden.

El botón **Habilitar motores** mantiene 1000 µs. El primer ↑ sube a 1100 µs; después ↑/↓ cambia 10 µs por pulsación hasta un máximo de 1350 µs. **Detener**, `Esc`, perder el foco de la página o 250 ms sin comunicación vuelven a 1000 µs.

## Carga y uso

1. Retira las hélices, verifica GND común y alimenta el ESP32 solo por USB. La batería alimenta el ESC. Consulta [cableado y seguridad](../../docs/WIRING_AND_SAFETY.md).
2. Cierra el HTML y cualquier monitor Serial que use COM6.
3. Carga este proyecto en PlatformIO:

   ```powershell
   pio run -d motor-tests/gpio26-only -t upload --upload-port COM6
   ```

4. Abre [index.html](index.html) en Chrome o Edge, conecta el puerto, habilita y pulsa ↑ gradualmente. El número visible es la orden enviada; confirma físicamente el giro del motor.

Si el archivo local no permite Web Serial, sirve esta carpeta con `py -3 -m http.server 8000 --bind 127.0.0.1 --directory motor-tests/gpio26-only` y abre `http://localhost:8000/index.html`.

El reporte Serial confirma la orden procesada por el firmware, no la velocidad ni la respuesta mecánica del motor. Esta prueba no usa sensores ni límites de ángulo o posición del riel.

Para repetir la prueba automática de órdenes USB y corte por watchdog, sin hélices y con el HTML cerrado:

```powershell
& "$env:USERPROFILE\.platformio\penv\Scripts\python.exe" motor-tests/gpio26-only/serial_probe.py COM6
```
