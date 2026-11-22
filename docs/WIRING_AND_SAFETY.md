# Cableado, Seguridad y Flujo Git

## 1. Tabla de Pinout (ESP32 `esp32dev`)

| Señal / Módulo | Pin ESP32 (GPIO) | Notas Eléctricas / I2C |
| :--- | :---: | :--- |
| **I2C SDA** | `GPIO 21` | Bus compartido a `400 kHz` (pull-ups 3.3 V) |
| **I2C SCL** | `GPIO 22` | Bus compartido a `400 kHz` (pull-ups 3.3 V) |
| **ToF XSHUT** | `GPIO 19` | Control de encendido / reset del sensor ToF (`0x29`) |
| **BNO055 (IMU)** | `GPIO 21 / 22` | Dirección I2C **`0x28`** (pin **`ADD` conectado a `GND`**) |
| **ToF (VL53L0X/1X)** | `GPIO 21 / 22` | Dirección I2C **`0x29`** |
| **ESC Izquierdo (Señal)** | `GPIO 25` | PWM `50 Hz` (`1000–1500 us`) hacia ESC OPTO |
| **ESC Derecho (Señal)** | `GPIO 26` | PWM `50 Hz` (`1000–1500 us`) hacia ESC OPTO |

---

## 2. Reglas Críticas de Alimentación y GND Común

> [!CAUTION]
> **GND Común Obligatorio:** El pin `GND` del ESP32 **DEBE** estar conectado sólidamente al `GND` de señal de ambos ESCs OPTO y de los sensores I2C. Sin referencia de tierra común, la señal PWM puede flotar o provocar comportamiento errático en los motores.

> [!IMPORTANT]
> **Alimentación del ESP32:** Alimentar el ESP32 exclusivamente por el puerto **USB** (5 V regulados en placa). **NUNCA** conectar la batería **LiPo 2S** (`7.4–8.4 V`) directamente al ESP32 (`VIN`/`5V`/`3V3`); la LiPo 2S alimenta únicamente la etapa de potencia de los ESCs.

---

## 3. Protocolo Obligatorio de Pruebas Iniciales (Sin Hélices)

1. **Verificación física:** Confirmar continuidad de `GND` común y ausencia de cortocircuitos entre `3V3`, `5V` y `GND` antes de energizar.
2. **Sin hélices:** Todas las pruebas iniciales de arranque, calibración de ESC, verificación de sentido de giro y respuesta de sensores/watchdog **DEBEN realizarse sin hélices instaladas** en los motores.
3. **Estado de arranque seguro:** Al reiniciar el ESP32, el firmware garantiza `ControlCommand.armed = false` y señales PWM en `PWM_MIN_US` (`1000 us`).
4. **Límites de seguridad activos en firmware:**
   - `PWM_MIN_US = 1000`, `PWM_SAFE_MAX_US = 1350`, `PWM_ABS_LIMIT_US = 1500`.
   - Corte automático por ángulo: `ANGLE_CUTOFF_DEG = 55.0°`.
   - Límites del riel: `0.0 mm` a `230.0 mm`.
   - Watchdog de comunicación/control: `250 ms`.

---

## 4. Convención de Ramas GitHub

- `main`: Rama estable y compilable. Ningún cambio experimental entra directamente aquí sin verificación.
- `feature/<modulo>`: Ramas de trabajo por módulo o hito (ej. `feature/imu-driver`, `feature/pid-controller`, `feature/host-telemetry`).
- Formato de commits: Conventional Commits (`chore:`, `feat:`, `fix:`, `docs:`, `test:`).
