"""USB/UART controller: python keyboard_control.py COM6 (requires pyserial)."""
import sys
import time
import tkinter as tk
from tkinter import ttk, messagebox
import serial


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Uso: python keyboard_control.py COM6')
    port = serial.Serial(sys.argv[1], 115200, timeout=0, write_timeout=0.1)
    root = tk.Tk()
    root.title('Bicóptero — PID USB / flechas')
    status = tk.StringVar(value='Esperando sensores y referencia automática…')
    last_rx = time.monotonic()
    buffer = bytearray()
    controls = []
    fields = {}

    def send(command):
        try:
            port.write((command + '\n').encode('ascii'))
            return True
        except (serial.SerialException, serial.SerialTimeoutException) as exc:
            status.set(f'Enlace perdido: {exc}')
            return False

    def arm():
        send('ARM')
        root.focus_set()

    def configure():
        try:
            import math
            for axis in ('H', 'A'):
                values = [float(v.get()) for v in fields[axis]]
                if not all(math.isfinite(v) and 0 <= v <= 100 for v in values):
                    raise ValueError('Ganancias entre 0 y 100')
                send('PID,' + axis + ',' + ','.join(map(str, values)))
        except ValueError as exc:
            messagebox.showerror('Ganancias inválidas', str(exc))

    ttk.Label(root, text='↑/↓ altura ±10 mm · ←/→ ángulo ±1° · Espacio: PARAR').pack(padx=15, pady=10)
    ttk.Label(root, text='Ganancias: salida en %, altura en mm, inclinación en grados.').pack()
    for axis, label in [('H', 'Altura'), ('A', 'Inclinación')]:
        frame = ttk.Frame(root)
        frame.pack(pady=5)
        ttk.Label(frame, text=label).pack(side='left')
        fields[axis] = []
        for name in ('Kp', 'Ki', 'Kd'):
            ttk.Label(frame, text=name).pack(side='left')
            value = tk.StringVar(value='0')
            fields[axis].append(value)
            ttk.Entry(frame, textvariable=value, width=8).pack(side='left')
    ttk.Button(root, text='Aplicar PID (desarmado)', command=configure).pack()
    ttk.Button(root, text='Armar y enfocar flechas', command=arm).pack(pady=6)
    ttk.Button(root, text='PARAR motores', command=lambda: send('STOP')).pack()
    ttk.Label(root, textvariable=status, wraplength=650).pack(padx=15, pady=15)

    def key(event):
        if event.keysym in ('space', 'Escape'):
            send('STOP')
            return 'break'
        if isinstance(root.focus_get(), ttk.Entry):
            return
        mapping = {'Up': 'U', 'Down': 'D', 'Left': 'L', 'Right': 'R'}
        if event.keysym in mapping:
            send(mapping[event.keysym])
            return 'break'

    root.bind_all('<KeyPress>', key)

    def poll():
        nonlocal last_rx
        try:
            buffer.extend(port.read(min(port.in_waiting, 8192)))
            while b'\n' in buffer:
                raw, _, rest = buffer.partition(b'\n')
                buffer[:] = rest
                text = raw.decode('ascii', errors='replace').strip()
                if text.startswith('CTRL,'):
                    parts = text.split(',')
                    if len(parts) in (11, 12, 14):
                        last_rx = time.monotonic()
                        status.set(f'Armado: {parts[2]} | Referencia: {parts[3]} | Sensores: {parts[10]}\n'
                                   f'Altura {parts[4]} → {parts[5]} mm | Ángulo {parts[6]} → {parts[7]}°\n'
                                   f'Motor izquierdo: {parts[8]} % | Derecho: {parts[9]} %')
                elif text.startswith(('ERR,', 'STATE,', 'ACK,')):
                    print(text, flush=True)
                    if text.startswith('ERR,'):
                        status.set(text)
                elif text.startswith('IMU,'):
                    print(text, flush=True)  # acceleration and gyro telemetry
            if len(buffer) > 16384:
                buffer.clear()
            if time.monotonic() - last_rx > 1:
                send('STOP')
                status.set('Esperando telemetría actual; motores detenidos.')
            elif root.focus_displayof() is not None:
                send('HB')
            else:
                send('STOP')
        except serial.SerialException as exc:
            status.set(f'Desconectado: {exc}')
        root.after(100, poll)

    def close():
        send('STOP')
        port.close()
        root.destroy()

    root.protocol('WM_DELETE_WINDOW', close)
    root.after(100, poll)
    root.mainloop()


if __name__ == '__main__':
    main()
