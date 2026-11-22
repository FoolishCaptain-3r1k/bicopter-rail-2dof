# BNO055 + VL53L0X: origen desde el dashboard

Variante de [dual-usb](../dual-usb/README.md) con origen de distancia y de ángulos **independientes**. La versión base se conserva. La nueva interfaz es [dashboard.html](dashboard.html).

## Uso

1. Mantener el firmware de `dual-usb` ya cargado y el cableado verificado de ambos sensores. Cerrar el HTML anterior y cualquier monitor Serial que use COM6.
2. Abrir este nuevo HTML en Chrome/Edge de escritorio, pulsar **Conectar ESP32** y elegir COM6 / CP210x, a 115200 baudios.
3. Situar el sistema en la posición de referencia y esperar lecturas válidas.
4. Pulsar **Fijar origen de distancia** para tomar la lectura actual del VL53L0X como cero. La distancia mostrada es `distancia_original − origen_mm`. Un aumento de la distancia sensor–blanco es positivo; una disminución es negativa. No se presupone la dirección positiva del riel.
5. Pulsar **Fijar origen de ángulos** para tomar roll, pitch y yaw actuales como cero. Cada ángulo se muestra como su diferencia con el origen, normalizada a `[-180°, 180°)`. Por ejemplo, de yaw 359° a 1° muestra +2°.
6. **Restaurar distancia** y **Restaurar ángulos** eliminan cada referencia por separado. Se puede fijar un origen nuevo en cualquier momento con muestras válidas recientes.

Los valores originales permanecen visibles debajo de cada indicador. Gráficas y vista esquemática usan la referencia seleccionada; el historial del sensor correspondiente se limpia al fijar/restaurar su origen para empezar un tramo nuevo. Giro, aceleración y calibración conservan sus valores originales.

Los botones no toman muestras caducadas ni inválidas: máximo 500 ms para la IMU y 1500 ms para ToF, con conexión activa. Ajustar el origen no crea una muestra nueva ni modifica sus timestamps o su validez.

El origen se guarda únicamente en memoria de la página durante esta conexión. Se borra al desconectar, recargar la página, reconectar o detectar un reinicio/vuelta del timestamp del ESP32. Un fallo temporal de lectura oculta los valores y bloquea la captura de origen; la referencia se conserva hasta recuperar lecturas o detectar un reinicio. No hay filtros ni escritura de calibración, EEPROM o comandos USB. La diferencia de ángulos Euler es una referencia numérica; no representa una transformación exacta de actitud 3D entre marcos. La vista sigue siendo ilustrativa y yaw puede derivar en IMUPLUS.

Si abrir el archivo directamente no habilita Web Serial, desde la raíz:

```powershell
py -3 -m http.server 8000 --bind 127.0.0.1 --directory sensor-tests/dual-usb-origin
```

Abrir `http://localhost:8000/dashboard.html` en Chrome o Edge. El ESP32 continúa comunicándose solo por USB.

## Firmware y cableado

El [platformio.ini](platformio.ini) apunta explícitamente a `../dual-usb/src` y `../dual-usb/include`: utiliza el mismo programa de adquisición y protocolo. Si ya funciona la versión base, **no hace falta volver a cargar** para cambiar de dashboard. Se conserva BNO055 en `0x28` (ADD a GND), VL53L0X en `0x29`, SDA GPIO21, SCL GPIO22, I2C 100 kHz y timeout Wire 50 ms. XSHUT no se controla.

Para compilar o cargar este entorno, cuando sea necesario:

```powershell
pio run -d sensor-tests/dual-usb-origin -e esp32dev
pio run -d sensor-tests/dual-usb-origin -e esp32dev -t upload --upload-port COM6
```

Consultar el [cableado y seguridad de la base](../dual-usb/README.md) antes de alimentar. Mantener ESC, motores y LiPo desconectados. No se modifica el control ni se envía el origen a un controlador.

## Verificación

```powershell
node --test sensor-tests/dual-usb-origin/tests/*.test.cjs
```

- **PASS:** cinco pruebas Node: protocolo y ciclo USB simulado, independencia de referencias, valores originales, distancia negativa, cruce de yaw, restauración, rechazo de lecturas inválidas/caducadas y borrado al desconectar/reiniciar.
- **PASS:** PlatformIO `esp32dev` compila el firmware compartido con SUCCESS.
- **PARTIAL:** botones y gráficas con origen pendientes de ensayo físico en navegador conectado al ESP32. La confirmación del usuario sobre la versión base no sustituye esta comprobación de la variante nueva.

Aceptación manual: fijar cada origen, comprobar cero en su indicador manteniendo intactos los originales, desplazar/girar y verificar signo y magnitud; restaurar un origen sin afectar al otro. Desconectar USB y confirmar que no se mantienen datos actuales ni referencias para la siguiente conexión. Repetir con una lectura inválida para comprobar que no permite fijarla como origen.
