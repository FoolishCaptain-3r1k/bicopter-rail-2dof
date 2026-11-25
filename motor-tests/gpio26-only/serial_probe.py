"""Comprueba por USB las ordenes del firmware GPIO26, sin helices."""

import sys
import time

import serial


def expect(port, expected):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        line = port.readline().decode(errors="replace").strip()
        if line == expected:
            return
    raise RuntimeError(f"No se recibio {expected!r}")


def command(port, code, expected):
    port.write(code.encode())
    expect(port, expected)


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python serial_probe.py COM6 (solo sin helices)")

    with serial.Serial(sys.argv[1], 115200, timeout=0.1) as port:
        try:
            time.sleep(2)  # Abrir COM reinicia algunas placas ESP32.
            port.reset_input_buffer()
            command(port, "A", "PWM,1000,ARMED")
            command(port, "U", "PWM,1100,ARMED")
            print("GPIO26: 1100 us confirmado por firmware")

            for pulse in range(1110, 1360, 10):
                command(port, "U", f"PWM,{pulse},ARMED")
                if pulse in (1200, 1300, 1350):
                    print(f"GPIO26: {pulse} us confirmado por firmware")

            command(port, "X", "PWM,1000,STOPPED")
            command(port, "A", "PWM,1000,ARMED")
            command(port, "U", "PWM,1100,ARMED")
            expect(port, "PWM,1000,STOPPED")  # Watchdog de 250 ms.
            print("GPIO26: corte automatico confirmado")
        finally:
            port.write(b"X")


if __name__ == "__main__":
    main()
