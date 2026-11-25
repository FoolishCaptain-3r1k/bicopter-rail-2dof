# Altura automática: diagnóstico previo

Esta carpeta separa la integración de BNO055 y VL53L0X para el futuro control de altura. El firmware y el dashboard actuales son **solo lectura**; no generan PWM para los ESC. Se reutiliza la adquisición I²C de `sensor-tests/dual-usb` para confirmar la distancia real antes de permitir control cerrado.

## Estado medido

En la ESP32 por COM6, el 24 de noviembre de 2026, la carga del firmware de sensores terminó con `SUCCESS`, pero las lecturas reportaron:

- `# TOF I2C_FAIL reg=0xC0 phase=write code=2` y `TOF,...,NA,MODEL_OR_I2C,NA`.
- `# BNO ERROR expected BNO055 at 0x28` y muestras IMU `INVALID`.

No hay una muestra válida con la que calcular la separación desde abajo hasta la superficie superior. La longitud mecánica de riel documentada es 230 mm, pero esa cifra no sustituye una lectura del VL53L0X ni confirma su montaje.

## Condiciones para activar el control

Confirmar VCC, GND, SDA GPIO21 y SCL GPIO22; VL53L0X en `0x29` y BNO055 en `0x28` (ADD a GND). Con ambos sensores válidos, medir la distancia en la posición inferior y comprobar que disminuye al subir. Identificar si los límites son interruptores conectados o solo topes mecánicos. Entonces se podrá habilitar un controlador de referencia 150 mm debajo de la superficie, con Kp, Ki y Kd editables, filtro de Kalman y corte por lecturas inválidas.
