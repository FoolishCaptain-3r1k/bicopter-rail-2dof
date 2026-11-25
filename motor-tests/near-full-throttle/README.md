# Prueba de acelerador al 99 %

Proyecto independiente para los ESC en GPIO25 y GPIO26. Supone ESC PWM con recorrido de 1000 a 2000 µs; el 99 % corresponde a **1990 µs**. Esto expresa una orden de aceleración, no una medición de potencia eléctrica o mecánica. Supera el límite absoluto de 1500 µs documentado para el banco; úsalo solo si el modelo de ambos ESC admite este rango y sin hélices.

Al iniciar, el ESP32 envía 1000 µs. El botón **Habilitar motores** conserva ese mínimo. El botón **99 %: 1990 µs** envía la orden alta a ambos ESC. **Detener**, `Esc`, perder el foco o 250 ms sin mensajes USB devuelven la señal a 1000 µs y deshabilitan el control.

Para cargar desde la raíz del repositorio:

```powershell
pio run -d motor-tests/near-full-throttle -t upload --upload-port COM6
```

Abre [index.html](index.html) en Chrome o Edge. Si Web Serial no funciona desde archivo local, sirve la carpeta con `py -3 -m http.server 8000 --bind 127.0.0.1 --directory motor-tests/near-full-throttle` y abre `http://localhost:8000/index.html`. Cierra el monitor Serial antes de conectar el navegador. La cifra en la página es la orden enviada, no una lectura de velocidad o potencia.
