"""Autonomous DSP flight capture, FFT/PSD analysis, and filter benchmark for MotorLab V9."""

from __future__ import annotations

import argparse
from collections import deque
import csv
import json
import math
from pathlib import Path
import time
import urllib.error
import urllib.request

import numpy as np
from scipy import signal
import serial

SSE_BASE = "http://127.0.0.1:8090"

# Flight contract (top = 1000 -> scale = 200 / 1000 = 0.20)
FLIGHT_TOP = 1000.0
H_MID = 500.0
H_AMP = 300.0
H_MIN = 150.0
H_MAX = 850.0
SINE_FREQ = 0.35
GAINS = (0.048, 0.002, 0.0, 0.35, 0.02, 0.08)


def post_sse(endpoint: str, payload: dict) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{SSE_BASE}{endpoint}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=0.4):
            pass
    except (urllib.error.URLError, TimeoutError, OSError):
        pass


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def median3_stream(arr: np.ndarray) -> np.ndarray:
    out = np.empty_like(arr, dtype=float)
    win: deque[float] = deque(maxlen=3)
    for i, x in enumerate(arr):
        win.append(float(x))
        if len(win) < 3:
            out[i] = float(x)
        else:
            out[i] = sorted(win)[1]
    return out


def compute_lag_ms(ref: np.ndarray, sig: np.ndarray, fs: float) -> float:
    if len(ref) < 10 or len(sig) < 10:
        return 0.0
    r = ref - np.mean(ref)
    s = sig - np.mean(sig)
    if np.std(r) < 1e-6 or np.std(s) < 1e-6:
        return 0.0
    corr = np.correlate(s, r, mode="full")
    lags = np.arange(-len(r) + 1, len(r))
    # Restrict search to physically meaningful lag [-1.0 s, +1.0 s]
    max_samples = int(round(1.0 * fs))
    mask = (lags >= -max_samples) & (lags <= max_samples)
    best_idx = int(np.argmax(corr[mask]))
    best_lag_samples = int(lags[mask][best_idx])
    return float(best_lag_samples * (1000.0 / fs))


def open_serial_no_reset(port: str) -> serial.Serial:
    ser = serial.Serial()
    ser.port = port
    ser.baudrate = 115200
    ser.timeout = 0.02
    ser.write_timeout = 0.2
    ser.dtr = False
    ser.rts = False
    ser.open()
    return ser


def run_sine_flight_on_port(
    ser: serial.Serial,
    port_label: str,
    filter_name: str,
    csv_path: Path,
    duration_s: float = 12.0,
    order: int = 1,
    fc_hz: float = 1.36,
    filter_mode: int | None = None,
    winner: bool = False,
) -> dict:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    post_sse("/api/reset", {"clear_results": False})
    post_sse(
        "/api/stage",
        {
            "filter_name": filter_name,
            "phase": "CAPTURANDO",
            "note": f"Vuelo senoidal real {duration_s:.0f} s en {port_label} (H_mid=500, A=300, f=0.35 Hz, 0°).",
        },
    )

    rows: list[dict] = []
    tof_pre: deque[float] = deque(maxlen=30)
    tof_times: list[float] = []
    imu_times: list[float] = []
    last_tof_mm: float | None = None
    origin_mm: float | None = None
    origin_ready = False
    sensors_valid = False
    armed = False
    power = "OFF"
    started_cmd = False
    pid_t0: float | None = None
    flight_t0 = time.monotonic()
    last_hb = 0.0
    last_target_sent = H_MID
    stop_reason: str | None = None
    high_pwm_since: float | None = None
    max_filt_h = -1e9
    liftoff_aborted = False

    try:
        # 1) Wait for originReady=1 & sensors_valid=1 (no reset required)
        wait_deadline = time.monotonic() + 10.0
        while time.monotonic() < wait_deadline and not (origin_ready and sensors_valid):
            raw = ser.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").strip()
            if line.startswith("TOF,"):
                p = line.split(",")
                if len(p) >= 5 and p[3] == "OK":
                    mm = float(p[2])
                    last_tof_mm = mm
                    tof_pre.append(mm)
                    tof_times.append(time.monotonic())
            elif line.startswith("IMU,"):
                p = line.split(",")
                if len(p) >= 16 and p[15] == "OK":
                    imu_times.append(time.monotonic())
            elif line == "STATE,READY":
                origin_ready = True
                if tof_pre:
                    origin_mm = float(np.mean(list(tof_pre)))
            elif line.startswith("CTRL,"):
                p = line.split(",")
                if len(p) == 14:
                    origin_ready = int(p[3]) == 1
                    sensors_valid = int(p[10]) == 1
                    if origin_ready and origin_mm is None and last_tof_mm is not None:
                        origin_mm = last_tof_mm + float(p[4]) / 10.0

        if not (origin_ready and sensors_valid):
            raise RuntimeError("Timeout esperando STATE,READY y sensores válidos en ESP32.")
        if origin_mm is None:
            origin_mm = last_tof_mm if last_tof_mm is not None else 140.0

        # 1b) Switch runtime filter mode if requested
        if filter_mode is not None:
            ser.write(f"FILTER,{filter_mode}\n".encode("ascii"))
            ser.flush()
            ack_deadline = time.monotonic() + 1.5
            got_ack = False
            while time.monotonic() < ack_deadline:
                raw = ser.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="replace").strip()
                if line == f"ACK,FILTER,{filter_mode}":
                    got_ack = True
                    break
            if not got_ack:
                raise RuntimeError(f"Sin ACK,FILTER,{filter_mode} desde ESP32.")

        # 2) Send START,AUTO command
        hkp, hki, hkd, akp, aki, akd = GAINS
        start_cmd = f"START,AUTO,{H_MID:.2f},0,{hkp},{hki},{hkd},{akp},{aki},{akd}\n"
        ser.write(start_cmd.encode("ascii"))
        started_cmd = True
        last_hb = time.monotonic()
        flight_t0 = time.monotonic()

        # 3) Main 12s PID sine flight loop with no-liftoff safety guard
        max_wall_deadline = time.monotonic() + duration_s + 10.0
        while time.monotonic() < max_wall_deadline:
            now = time.monotonic()
            if now - last_hb >= 0.10:
                ser.write(b"HB\n")
                last_hb = now
                if power == "PID" and pid_t0 is not None:
                    t_pid = now - pid_t0
                    if t_pid >= duration_s:
                        break
                    ref_h = clamp(
                        H_MID + H_AMP * math.sin(2.0 * math.pi * SINE_FREQ * t_pid),
                        H_MIN,
                        H_MAX,
                    )
                    ref_h = round(ref_h, 2)
                    if ref_h != last_target_sent:
                        ser.write(f"TARGET,{ref_h:.2f},0\n".encode("ascii"))
                        last_target_sent = ref_h

            raw = ser.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            now = time.monotonic()
            if line.startswith("TOF,"):
                p = line.split(",")
                if len(p) >= 5 and p[3] == "OK":
                    last_tof_mm = float(p[2])
                    tof_times.append(now)
            elif line.startswith("IMU,"):
                p = line.split(",")
                if len(p) >= 16 and p[15] == "OK":
                    imu_times.append(now)
            elif line.startswith("STATE,STOP,"):
                stop_reason = line.split(",", 2)[2]
                if started_cmd:
                    break
            elif line.startswith("CTRL,"):
                p = line.split(",")
                if len(p) != 14:
                    continue
                device_ms = int(p[1])
                armed = int(p[2]) == 1
                origin_ready = int(p[3]) == 1
                filt_h = float(p[4])
                target_h = float(p[5])
                filt_a = float(p[6])
                pwm_l = float(p[8])
                pwm_r = float(p[9])
                power = p[12]
                raw_a = float(p[13])
                if power == "PID" and pid_t0 is None:
                    pid_t0 = now
                if power == "PID":
                    if filt_h > max_filt_h:
                        max_filt_h = filt_h
                    if pwm_l > 75.0 and pwm_r > 75.0 and max_filt_h < 40.0:
                        if high_pwm_since is None:
                            high_pwm_since = now
                        elif now - high_pwm_since >= 2.5:
                            liftoff_aborted = True
                            stop_reason = "NO_LIFTOFF_DETECTED"
                            break
                    else:
                        high_pwm_since = None
                raw_h = (
                    -10.0 * (last_tof_mm - origin_mm)
                    if last_tof_mm is not None
                    else filt_h
                )
                t_rel = round(now - flight_t0, 4)
                row = {
                    "host_t": t_rel,
                    "pid_t": round(now - pid_t0, 4) if pid_t0 is not None else -1.0,
                    "device_ms": device_ms,
                    "armed": int(armed),
                    "power": power,
                    "raw_tof_mm": round(last_tof_mm, 3) if last_tof_mm is not None else 0.0,
                    "origin_mm": round(origin_mm, 3),
                    "raw_h": round(raw_h, 3),
                    "filt_h": round(filt_h, 3),
                    "ref_h": round(target_h, 3),
                    "raw_a": round(raw_a, 3),
                    "filt_a": round(filt_a, 3),
                    "pwm_l": round(pwm_l, 3),
                    "pwm_r": round(pwm_r, 3),
                }
                rows.append(row)
                post_sse(
                    "/api/sample",
                    {
                        "t": t_rel,
                        "raw_h": row["raw_h"],
                        "filt_h": row["filt_h"],
                        "ref_h": row["ref_h"],
                        "raw_a": row["raw_a"],
                        "filt_a": row["filt_a"],
                        "pwm_l": row["pwm_l"],
                        "pwm_r": row["pwm_r"],
                    },
                )
    finally:
        # Guaranteed safe STOP + wait for power == OFF (keep port open for suite)
        stop_deadline = time.monotonic() + 2.0
        try:
            ser.write(b"STOP\n")
            ser.flush()
            while time.monotonic() < stop_deadline:
                raw = ser.readline()
                if not raw:
                    ser.write(b"STOP\n")
                    continue
                line = raw.decode("utf-8", errors="replace").strip()
                if line.startswith("CTRL,"):
                    p = line.split(",")
                    if len(p) == 14 and int(p[2]) == 0 and p[12] == "OFF":
                        power = "OFF"
                        armed = False
                        break
        except Exception:
            pass

    # Save CSV
    fieldnames = [
        "host_t",
        "pid_t",
        "device_ms",
        "armed",
        "power",
        "raw_tof_mm",
        "origin_mm",
        "raw_h",
        "filt_h",
        "ref_h",
        "raw_a",
        "filt_a",
        "pwm_l",
        "pwm_r",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Compute live metrics on PID rows
    pid_rows = [r for r in rows if r["power"] == "PID"]
    if len(pid_rows) < 10:
        pid_rows = rows
    t_arr = np.array([r["host_t"] for r in pid_rows], dtype=float)
    fs_ctrl = float(1.0 / np.median(np.diff(t_arr))) if len(t_arr) > 2 else 20.0
    filt_h_mm = np.array([r["filt_h"] for r in pid_rows], dtype=float) / 10.0
    ref_h_mm = np.array([r["ref_h"] for r in pid_rows], dtype=float) / 10.0
    pwm_l = np.array([r["pwm_l"] for r in pid_rows], dtype=float)
    pwm_r = np.array([r["pwm_r"] for r in pid_rows], dtype=float)

    b_ref, a_ref = signal.butter(3, min(0.95, 1.2 / (fs_ctrl / 2.0)), btype="low")
    if len(filt_h_mm) > 15:
        smooth_traj = signal.filtfilt(b_ref, a_ref, filt_h_mm)
    else:
        smooth_traj = filt_h_mm
    noise_res = filt_h_mm - smooth_traj
    std_mm = float(np.std(noise_res))
    p2p_mm = float(np.max(noise_res) - np.min(noise_res))
    rmse_mm = float(np.sqrt(np.mean((filt_h_mm - ref_h_mm) ** 2)))
    lag_ms = compute_lag_ms(ref_h_mm, filt_h_mm, fs_ctrl)
    pwm_jitter = float(
        0.5 * (np.std(np.diff(pwm_l)) + np.std(np.diff(pwm_r)))
    ) if len(pwm_l) > 2 else 0.0
    tv_vel = float(np.mean(np.abs(np.diff(filt_h_mm, n=2)))) if len(filt_h_mm) > 3 else 0.0
    liftoff_ok = (not liftoff_aborted) and (max_filt_h >= 40.0)
    smoothness_score = max(
        0.0,
        min(100.0, 100.0 - std_mm * 30.0 - pwm_jitter * 15.0 - tv_vel * 10.0),
    ) if liftoff_ok else 0.0

    fs_tof = float(1.0 / np.median(np.diff(tof_times))) if len(tof_times) > 2 else 0.0
    fs_imu = float(1.0 / np.median(np.diff(imu_times))) if len(imu_times) > 2 else 0.0

    summary = {
        "filter_name": filter_name,
        "filter_mode": filter_mode,
        "order": order,
        "fc_hz": fc_hz,
        "std_mm": round(std_mm, 3),
        "p2p_mm": round(p2p_mm, 3),
        "lag_ms": round(lag_ms, 1),
        "rmse_mm": round(rmse_mm, 3),
        "pwm_jitter": round(pwm_jitter, 4),
        "tv_vel": round(tv_vel, 4),
        "max_h": round(max_filt_h, 2) if max_filt_h > -1e8 else 0.0,
        "liftoff_ok": liftoff_ok,
        "smoothness_score": round(smoothness_score, 1),
        "winner": winner,
        "n_rows": len(rows),
        "n_pid_rows": len(pid_rows),
        "fs_ctrl": round(fs_ctrl, 2),
        "fs_tof": round(fs_tof, 2),
        "fs_imu": round(fs_imu, 2),
        "stop_reason": stop_reason,
        "final_power": power,
        "csv": str(csv_path),
    }
    post_sse("/api/result", summary)
    return summary


def run_sine_flight(
    port: str,
    filter_name: str,
    csv_path: Path,
    duration_s: float = 12.0,
    order: int = 1,
    fc_hz: float = 1.36,
    filter_mode: int | None = None,
    winner: bool = False,
) -> dict:
    ser = open_serial_no_reset(port)
    try:
        return run_sine_flight_on_port(
            ser, port, filter_name, csv_path, duration_s, order, fc_hz, filter_mode, winner
        )
    finally:
        ser.close()


SUITE_FILTERS = [
    (0, "LIVE · Median3+EMA(0.30)",      1, 1.36, "datos_pruebas/dsp_suite_0_ema.csv"),
    (1, "LIVE · Median3+SMA(N=5)",       4, 1.77, "datos_pruebas/dsp_suite_1_sma5.csv"),
    (2, "LIVE · Median3+Butter2(1.5Hz)", 2, 1.50, "datos_pruebas/dsp_suite_2_butter2.csv"),
    (3, "LIVE · Median3+Bessel2(2.0Hz)", 2, 2.00, "datos_pruebas/dsp_suite_3_bessel2.csv"),
    (4, "LIVE · Median3+Cheby1-2(1.8Hz)",2, 1.80, "datos_pruebas/dsp_suite_4_cheby2.csv"),
]


def run_full_suite(port: str, duration_s: float = 12.0, cooldown_s: float = 3.0) -> list[dict]:
    post_sse("/api/reset", {"clear_results": True})
    ser = open_serial_no_reset(port)
    results: list[dict] = []
    try:
        for idx, (mode, name, order, fc_hz, csv_rel) in enumerate(SUITE_FILTERS):
            res = run_sine_flight_on_port(
                ser, port, name, Path(csv_rel), duration_s, order, fc_hz, filter_mode=mode
            )
            results.append(res)
            if not res["liftoff_ok"]:
                post_sse(
                    "/api/stage",
                    {
                        "filter_name": name,
                        "phase": "COMPLETADO",
                        "note": "Abortado por NO_LIFTOFF_DETECTED (cicla la batería LiPo para armar ESCs).",
                    },
                )
                break
            if idx < len(SUITE_FILTERS) - 1:
                post_sse(
                    "/api/stage",
                    {
                        "filter_name": f"Enfriamiento ({cooldown_s:.0f} s) antes del siguiente filtro",
                        "phase": "ANALIZANDO",
                        "note": f"Completado {name}. Motores en OFF sin reiniciar ESP32.",
                    },
                )
                time.sleep(cooldown_s)

        valid_runs = [r for r in results if r["liftoff_ok"]]
        if valid_runs:
            best = max(valid_runs, key=lambda r: r["smoothness_score"])
            best["winner"] = True
            ser.write(f"FILTER,{best['filter_mode']}\n".encode("ascii"))
            ser.flush()
            post_sse("/api/result", best)
            post_sse(
                "/api/stage",
                {
                    "filter_name": f"GANADOR · {best['filter_name']}",
                    "phase": "COMPLETADO",
                    "note": f"std={best['std_mm']} mm · p2p={best['p2p_mm']} mm · PWM_jitter={best['pwm_jitter']} · score={best['smoothness_score']}",
                },
            )
    finally:
        ser.close()
    Path("datos_pruebas/dsp_suite_results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return results


def run_offline_benchmark(csv_path: Path, out_json: Path) -> dict:
    post_sse(
        "/api/stage",
        {
            "filter_name": "Análisis FFT/PSD + Benchmark Offline",
            "phase": "ANALIZANDO",
            "note": f"Procesando {csv_path.name} con 8 filtros pasabajas a fs=20 Hz.",
        },
    )

    with csv_path.open("r", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    pid_rows = [r for r in rows if r["power"] == "PID"]
    if len(pid_rows) < 20:
        pid_rows = rows

    t = np.array([float(r["host_t"]) for r in pid_rows], dtype=float)
    fs = 20.0
    raw_mm = np.array([float(r["raw_h"]) for r in pid_rows], dtype=float) / 10.0
    raw_tof_mm = np.array([float(r["raw_tof_mm"]) for r in pid_rows], dtype=float)
    d_tof = np.abs(np.diff(raw_tof_mm))
    spikes_5 = int(np.sum(d_tof >= 5.0))
    spikes_10 = int(np.sum(d_tof >= 10.0))

    # Ideal zero-phase reference trajectory of the real carriage motion
    b_id, a_id = signal.butter(3, 1.2 / (fs / 2.0), btype="low")
    ideal_mm = signal.filtfilt(b_id, a_id, median3_stream(raw_mm))
    noise_raw = raw_mm - ideal_mm

    # FFT / PSD with Hann window
    n = len(noise_raw)
    win = np.hanning(n)
    spec = np.fft.rfft(noise_raw * win)
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    psd = (np.abs(spec) ** 2) / (fs * np.sum(win ** 2))
    total_power = float(np.sum(psd)) + 1e-12

    def band_pct(f_lo: float, f_hi: float) -> float:
        m = (freqs >= f_lo) & (freqs < f_hi)
        return round(float(np.sum(psd[m]) / total_power * 100.0), 2)

    fft_report = {
        "n_samples": n,
        "fs_hz": fs,
        "raw_noise_std_mm": round(float(np.std(noise_raw)), 3),
        "raw_noise_p2p_mm": round(float(np.max(noise_raw) - np.min(noise_raw)), 3),
        "spikes_ge_5mm": spikes_5,
        "spikes_ge_10mm": spikes_10,
        "energy_0_1_hz_pct": band_pct(0.0, 1.0),
        "energy_1_2_hz_pct": band_pct(1.0, 2.0),
        "energy_2_5_hz_pct": band_pct(2.0, 5.0),
        "energy_5_nyq_hz_pct": band_pct(5.0, fs / 2.0 + 0.01),
    }

    med_mm = median3_stream(raw_mm)

    def apply_ema(x: np.ndarray, alpha: float) -> np.ndarray:
        y = np.empty_like(x)
        y[0] = x[0]
        for i in range(1, len(x)):
            y[i] = alpha * x[i] + (1.0 - alpha) * y[i - 1]
        return y

    def apply_sma(x: np.ndarray, n_tap: int) -> np.ndarray:
        y = np.empty_like(x)
        buf: deque[float] = deque(maxlen=n_tap)
        for i, v in enumerate(x):
            buf.append(float(v))
            y[i] = sum(buf) / len(buf)
        return y

    def apply_iir(x: np.ndarray, b: np.ndarray, a: np.ndarray) -> np.ndarray:
        zi = signal.lfilter_zi(b, a) * x[0]
        y, _ = signal.lfilter(b, a, x, zi=zi)
        return y

    candidates: list[dict] = []

    def add_cand(name: str, key: str, order: int, fc_hz: float, y: np.ndarray, b=None, a=None):
        res = y - ideal_mm
        # Skip initial 0.5 s transient (10 samples) for steady metrics
        sl = slice(10, None) if len(y) > 25 else slice(None)
        std_mm = float(np.std(res[sl]))
        p2p_mm = float(np.max(res[sl]) - np.min(res[sl]))
        rmse_mm = float(np.sqrt(np.mean(res[sl] ** 2)))
        lag_ms = compute_lag_ms(ideal_mm[sl], y[sl], fs)
        tv_vel = float(np.mean(np.abs(np.diff(y[sl], n=2))))
        candidates.append(
            {
                "filter_name": name,
                "key": key,
                "order": order,
                "fc_hz": fc_hz,
                "std_mm": round(std_mm, 4),
                "p2p_mm": round(p2p_mm, 4),
                "rmse_mm": round(rmse_mm, 4),
                "lag_ms": round(lag_ms, 1),
                "tv_vel": round(tv_vel, 4),
                "b": [round(float(v), 8) for v in b] if b is not None else None,
                "a": [round(float(v), 8) for v in a] if a is not None else None,
            }
        )

    # 1) EMA baseline
    add_cand("OFF · Median3+EMA(0.30)", "ema030", 1, 1.36, apply_ema(med_mm, 0.30))
    # 2) SMA N=5
    add_cand("OFF · Median3+SMA(N=5)", "sma5", 4, 1.77, apply_sma(med_mm, 5))
    # 3) Butterworth 2nd order (1.5 Hz, 2.0 Hz)
    for fc in (1.5, 2.0):
        b, a = signal.butter(2, fc / (fs / 2.0), btype="low")
        add_cand(f"OFF · Median3+Butter2({fc}Hz)", f"butter2_{str(fc).replace('.','p')}", 2, fc, apply_iir(med_mm, b, a), b, a)
    # 4) Bessel 2nd order (1.5 Hz, 2.0 Hz)
    for fc in (1.5, 2.0):
        b, a = signal.bessel(2, fc / (fs / 2.0), btype="low", norm="phase")
        add_cand(f"OFF · Median3+Bessel2({fc}Hz)", f"bessel2_{str(fc).replace('.','p')}", 2, fc, apply_iir(med_mm, b, a), b, a)
    # 5) Chebyshev Type I 2nd order (1.8 Hz, 0.5 dB ripple)
    b, a = signal.cheby1(2, 0.5, 1.8 / (fs / 2.0), btype="low")
    add_cand("OFF · Median3+Cheby1-2(1.8Hz)", "cheby2_1p8", 2, 1.8, apply_iir(med_mm, b, a), b, a)
    # 6) Butterworth 4th order (2.0 Hz)
    b, a = signal.butter(4, 2.0 / (fs / 2.0), btype="low")
    add_cand("OFF · Median3+Butter4(2.0Hz)", "butter4_2p0", 4, 2.0, apply_iir(med_mm, b, a), b, a)

    # Normalize & compute smoothness_score (60% smoothness/noise attenuation + 40% low lag, penalize lag > 180 ms)
    max_std = max(c["std_mm"] for c in candidates) + 1e-9
    max_tv = max(c["tv_vel"] for c in candidates) + 1e-9
    for c in candidates:
        smooth_part = 0.5 * (1.0 - c["std_mm"] / max_std) + 0.5 * (1.0 - c["tv_vel"] / max_tv)
        lag_abs = abs(c["lag_ms"])
        lag_part = max(0.0, 1.0 - lag_abs / 250.0)
        penalty = max(0.0, (lag_abs - 180.0) / 100.0) * 0.35
        score = max(0.0, min(100.0, (0.60 * smooth_part + 0.40 * lag_part - penalty) * 100.0))
        c["smoothness_score"] = round(score, 1)
        c["winner"] = False

    candidates.sort(key=lambda x: x["smoothness_score"], reverse=True)
    for c in candidates:
        post_sse("/api/result", c)

    report = {"fft": fft_report, "candidates": candidates}
    out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Autonomous DSP flight & benchmark runner")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_f = sub.add_parser("flight", help="Run 12s live sine flight on COM port")
    p_f.add_argument("--port", default="COM4")
    p_f.add_argument("--name", required=True)
    p_f.add_argument("--csv", required=True)
    p_f.add_argument("--duration", type=float, default=12.0)
    p_f.add_argument("--order", type=int, default=1)
    p_f.add_argument("--fc", type=float, default=1.36)
    p_f.add_argument("--filter-mode", type=int, default=None)
    p_f.add_argument("--winner", action="store_true")

    p_su = sub.add_parser("suite", help="Run all 5 filters live without resetting ESP32")
    p_su.add_argument("--port", default="COM4")
    p_su.add_argument("--duration", type=float, default=12.0)
    p_su.add_argument("--cooldown", type=float, default=3.0)

    p_a = sub.add_parser("analyze", help="Run FFT/PSD + offline benchmark on flight CSV")
    p_a.add_argument("--csv", required=True)
    p_a.add_argument("--out", required=True)

    p_s = sub.add_parser("stage", help="Publish stage update to SSE dashboard")
    p_s.add_argument("--name", required=True)
    p_s.add_argument("--phase", required=True)
    p_s.add_argument("--note", default="")

    args = parser.parse_args()
    if args.cmd == "flight":
        res = run_sine_flight(
            port=args.port,
            filter_name=args.name,
            csv_path=Path(args.csv),
            duration_s=args.duration,
            order=args.order,
            fc_hz=args.fc,
            filter_mode=args.filter_mode,
            winner=args.winner,
        )
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif args.cmd == "suite":
        res = run_full_suite(port=args.port, duration_s=args.duration, cooldown_s=args.cooldown)
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif args.cmd == "analyze":
        rep = run_offline_benchmark(Path(args.csv), Path(args.out))
        print(json.dumps(rep, indent=2, ensure_ascii=False))
    elif args.cmd == "stage":
        post_sse("/api/stage", {"filter_name": args.name, "phase": args.phase, "note": args.note})
        print("STAGE_OK")


if __name__ == "__main__":
    main()
