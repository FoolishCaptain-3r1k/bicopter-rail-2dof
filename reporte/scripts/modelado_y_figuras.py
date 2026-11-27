"""Reproducible Control/DSP modeling and IEEE-quality figure generator for Bicopter Rail 2-DOF."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch
import numpy as np
from scipy import optimize, signal

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "datos_pruebas"
FIG_DIR = ROOT / "reporte" / "figuras"
OUT_JSON = Path(__file__).with_name("resultados_modelado.json")
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Clean IEEE-style light editorial palette
NAVY = "#1B365D"
TEAL = "#007A78"
CORAL = "#C83E4D"
AMBER = "#D97706"
EMERALD = "#15803D"
SLATE = "#475569"
VIOLET = "#6D28D9"
GRID = "#E2E8F0"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9.5,
    "axes.titlesize": 10.5,
    "axes.titleweight": "bold",
    "axes.labelsize": 9.5,
    "axes.edgecolor": "#334155",
    "axes.linewidth": 0.9,
    "grid.color": GRID,
    "grid.linewidth": 0.7,
    "legend.frameon": True,
    "legend.facecolor": "#FFFFFF",
    "legend.edgecolor": "#CBD5E1",
    "legend.fontsize": 8.5,
    "figure.facecolor": "#FFFFFF",
    "axes.facecolor": "#FFFFFF",
    "savefig.facecolor": "#FFFFFF",
})


def load_pid_csv(path: Path) -> dict[str, np.ndarray]:
    with path.open("r", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["power"] == "PID"]
    return {
        "t": np.array([float(r["pid_t"]) for r in rows], dtype=float),
        "raw_tof_mm": np.array([float(r["raw_tof_mm"]) for r in rows], dtype=float),
        "raw_h": np.array([float(r["raw_h"]) for r in rows], dtype=float),
        "filt_h": np.array([float(r["filt_h"]) for r in rows], dtype=float),
        "ref_h": np.array([float(r["ref_h"]) for r in rows], dtype=float),
        "raw_a": np.array([float(r["raw_a"]) for r in rows], dtype=float),
        "filt_a": np.array([float(r["filt_a"]) for r in rows], dtype=float),
        "pwm_l": np.array([float(r["pwm_l"]) for r in rows], dtype=float),
        "pwm_r": np.array([float(r["pwm_r"]) for r in rows], dtype=float),
    }


def save_fig(fig: plt.Figure, stem: str) -> None:
    fig.savefig(FIG_DIR / f"{stem}.pdf", bbox_inches="tight")
    fig.savefig(FIG_DIR / f"{stem}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def identify_plant_and_statespace(flight: dict[str, np.ndarray]) -> dict:
    """Fit 2nd-order continuous G(s) & discrete G(z) (Ts=0.05s, ZOH) and 2-DOF state space."""
    t = flight["t"] - flight["t"][0]
    # Collective PWM (%) and height in physical mm (rail = 200 mm -> 1000 sensor units => * 0.2)
    u_col = 0.5 * (flight["pwm_l"] + flight["pwm_r"])
    y_u = flight["filt_h"]  # sensor units [0..1000]
    y_mm = y_u * 0.2        # physical mm [0..200]

    # Resample onto uniform Ts = 0.05 s grid for exact discrete simulation
    ts = 0.05
    t_uni = np.arange(0.0, t[-1], ts)
    u_uni = np.interp(t_uni, t, u_col)
    y_uni = np.interp(t_uni, t, y_mm)

    # Second-order plant: G(s) = K * wn^2 / (s^2 + 2*zeta*wn*s + wn^2)
    # Input: du = u_col - u_eq (%), Output: z_phys (mm)
    def simulate(params: np.ndarray) -> np.ndarray:
        k_dc, wn, zeta, u_eq = params
        num = [k_dc * wn * wn]
        den = [1.0, 2.0 * zeta * wn, wn * wn]
        sys_c = signal.TransferFunction(num, den)
        _, y_sim, _ = signal.lsim(sys_c, U=u_uni - u_eq, T=t_uni)
        return y_sim

    def residuals(params: np.ndarray) -> np.ndarray:
        return simulate(params) - y_uni

    p0 = np.array([6.0, 2.2, 0.55, 62.0])
    bounds = ([0.5, 0.4, 0.08, 45.0], [40.0, 12.0, 3.0, 82.0])
    opt = optimize.least_squares(residuals, p0, bounds=bounds, max_nfev=2000)
    k_dc, wn, zeta, u_eq = [float(v) for v in opt.x]
    y_hat = simulate(opt.x)

    ss_res = float(np.sum((y_uni - y_hat) ** 2))
    ss_tot = float(np.sum((y_uni - np.mean(y_uni)) ** 2))
    r2 = 1.0 - ss_res / max(ss_tot, 1e-12)
    rmse_mm = float(np.sqrt(np.mean((y_uni - y_hat) ** 2)))

    num_c = [k_dc * wn * wn]
    den_c = [1.0, 2.0 * zeta * wn, wn * wn]
    bz, az, _ = signal.cont2discrete((num_c, den_c), ts, method="zoh")
    bz = bz.ravel()
    az = az.ravel()

    # 2-DOF Linearized State-Space around hover: x = [z(mm), z_dot(mm/s), theta(deg), theta_dot(deg/s)]^T
    # u = [du_col (%), u_diff (%)]^T, y = [z(mm), theta(deg)]^T
    # Vertical dynamics directly from identified G(s); angular dynamics from physical rig parameters
    # (m = 0.40 kg, arm L = 0.075 m, I_eff ~ 0.0022 kg*m^2, aerodynamic/cable damping c_theta)
    m_kg = 0.40
    arm_m = 0.075
    inertia = 0.0022
    # Approximate angular gain from thrust sensitivity: b_z = K * wn^2 [mm/(s^2 * %)]
    b_z = k_dc * wn * wn
    # Force per 1% collective PWM: F_per_pct = m * (b_z / 1000) [N/%]
    f_per_pct = m_kg * (b_z / 1000.0)
    # Torque per 1% differential PWM (one motor +1%, other -1% -> 2 * F_per_pct * L)
    # Convert rad/s^2 to deg/s^2 (* 180/pi)
    b_theta = (2.0 * f_per_pct * arm_m / inertia) * (180.0 / math.pi)
    c_theta = 1.2  # light pivot/cable angular damping [1/s]

    A = np.array([
        [0.0, 1.0, 0.0, 0.0],
        [-wn * wn, -2.0 * zeta * wn, 0.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
        [0.0, 0.0, 0.0, -c_theta],
    ])
    B = np.array([
        [0.0, 0.0],
        [b_z, 0.0],
        [0.0, 0.0],
        [0.0, b_theta],
    ])
    C = np.array([
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
    ])
    D = np.zeros((2, 2))

    Phi, Gamma, Cd, Dd, _ = signal.cont2discrete((A, B, C, D), ts, method="zoh")

    # Controllability & Observability
    ctrb = np.hstack([np.linalg.matrix_power(A, k) @ B for k in range(4)])
    obsv = np.vstack([C @ np.linalg.matrix_power(A, k) for k in range(4)])
    rank_ctrb = int(np.linalg.matrix_rank(ctrb))
    rank_obsv = int(np.linalg.matrix_rank(obsv))

    eigs_c = np.linalg.eigvals(A)
    eigs_d = np.linalg.eigvals(Phi)

    return {
        "ts": ts,
        "t_uni": t_uni,
        "u_uni": u_uni,
        "y_uni": y_uni,
        "y_hat": y_hat,
        "k_dc": k_dc,
        "wn": wn,
        "zeta": zeta,
        "u_eq": u_eq,
        "r2": r2,
        "rmse_mm": rmse_mm,
        "num_c": num_c,
        "den_c": den_c,
        "bz": bz,
        "az": az,
        "A": A,
        "B": B,
        "C": C,
        "Phi": Phi,
        "Gamma": Gamma,
        "rank_ctrb": rank_ctrb,
        "rank_obsv": rank_obsv,
        "eigs_c": eigs_c,
        "eigs_d": eigs_d,
        "b_z": b_z,
        "b_theta": b_theta,
    }


def make_fig1_block_diagram() -> None:
    fig, ax = plt.subplots(figsize=(13.8, 5.4))
    ax.set_xlim(0, 14.4)
    ax.set_ylim(0, 5.4)
    ax.axis("off")

    def box(x, y, w, h, title, sub, fc="#F8FAFC", ec=NAVY, tc=NAVY):
        p = FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.05,rounding_size=0.14",
            facecolor=fc, edgecolor=ec, linewidth=1.6
        )
        ax.add_patch(p)
        ax.text(x + w / 2, y + h * 0.66, title, ha="center", va="center",
                fontsize=9.2, fontweight="bold", color=tc)
        ax.text(x + w / 2, y + h * 0.28, sub, ha="center", va="center",
                fontsize=7.8, color=SLATE)

    def arrow(x1, y1, x2, y2, text="", tx=0, ty=0, color="#1E293B"):
        a = FancyArrowPatch(
            (x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=13,
            linewidth=1.45, color=color
        )
        ax.add_patch(a)
        if text:
            ax.text((x1 + x2) / 2 + tx, (y1 + y2) / 2 + ty, text,
                    ha="center", va="center", fontsize=8.0, color=color, fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.12", facecolor="#FFFFFF", edgecolor="none", alpha=0.85))

    ax.text(7.2, 5.05, "Arquitectura del Lazo Cerrado Digital 2-DOF con Filtrado DSP (20 Hz)",
            ha="center", va="center", fontsize=12.8, fontweight="bold", color=NAVY)

    # Top forward path with generous gaps
    box(0.2, 2.85, 1.75, 1.08, "Referencia", "r[k]: Senoidal 0.35 Hz\nθ_ref = 0°", fc="#FEF3C7", ec=AMBER, tc="#92400E")
    s_x, s_y = 2.85, 3.39
    ax.add_patch(Circle((s_x, s_y), 0.25, facecolor="#FFFFFF", edgecolor=NAVY, linewidth=1.6))
    ax.text(s_x, s_y, "Σ", ha="center", va="center", fontsize=11, fontweight="bold", color=NAVY)
    ax.text(s_x - 0.36, s_y + 0.22, "+", fontsize=10, fontweight="bold", color=EMERALD)
    ax.text(s_x + 0.20, s_y - 0.38, "−", fontsize=11, fontweight="bold", color=CORAL)

    box(3.75, 2.85, 1.85, 1.08, "Banda Muerta", "Continua ±2.0 mm\n(±20 u., sin escalón)", fc="#F1F5F9", ec=SLATE, tc="#1E293B")
    box(6.30, 2.85, 2.25, 1.08, "PID Discreto + Mixer", "20 Hz · D en medida\nAnti-windup · 58% ± u_a", fc="#E0F2FE", ec=NAVY, tc=NAVY)
    box(9.25, 2.85, 1.75, 1.08, "Actuadores ESC", "LEDC 50 Hz (16-bit)\nGPIO25/26 · 200 µs/s", fc="#EDE9FE", ec=VIOLET, tc=VIOLET)
    box(11.70, 2.85, 1.85, 1.08, "Planta 2-DOF", "Bicóptero en Riel\n20 cm · m = 0.40 kg", fc="#DCFCE7", ec=EMERALD, tc=EMERALD)

    arrow(2.00, 3.39, s_x - 0.25, 3.39, "r[k]", ty=0.28)
    arrow(s_x + 0.25, 3.39, 3.70, 3.39, "e[k]", ty=0.28)
    arrow(5.65, 3.39, 6.25, 3.39, "e_db", ty=0.28)
    arrow(8.60, 3.39, 9.20, 3.39, "u_L, u_R", ty=0.28)
    arrow(11.05, 3.39, 11.65, 3.39, "PWM", ty=0.28)

    # Output tap cleanly outside the last box
    arrow(13.60, 3.39, 14.25, 3.39, "", color=EMERALD)
    ax.text(14.00, 3.72, "z(t), θ(t)", ha="center", va="bottom", fontsize=8.5, fontweight="bold", color=EMERALD)

    # Feedback path
    box(9.25, 0.65, 2.75, 1.08, "Sensores I2C (100 kHz)", "VL53L0X (0x29, ~10.6 Hz)\nBNO055 IMUPLUS (0x28, 20 Hz)", fc="#FFF1F2", ec=CORAL, tc=CORAL)
    box(4.65, 0.65, 3.35, 1.08, "Bloque DSP Ganador", "ToF: Median3 + Butter2 (fc = 1.5 Hz)\nIMU: EMA ligero (α = 0.70)", fc="#CCFBF1", ec=TEAL, tc=TEAL)

    ax.plot([13.95, 13.95, 12.05], [3.39, 1.19, 1.19], color=CORAL, lw=1.45)
    arrow(12.25, 1.19, 12.05, 1.19, color=CORAL)
    arrow(9.20, 1.19, 8.05, 1.19, "z_raw, θ_raw", ty=0.28, color=CORAL)
    ax.plot([4.60, s_x], [1.19, 1.19], color=TEAL, lw=1.5)
    arrow(s_x, 1.19, s_x, s_y - 0.25, "y_filt[k]", tx=-0.52, color=TEAL)

    ax.text(
        7.2, 0.16,
        "Supervisión de seguridad activa en ESP32: Watchdog HB > 350 ms · Frescura sensores < 200 ms · Paro inmediato STOP / Esc / Espacio",
        ha="center", va="center", fontsize=8.2, color=SLATE, style="italic"
    )
    save_fig(fig, "fig1_diagrama_retroalimentado")


def make_fig2_fft_noise(baseline: dict[str, np.ndarray]) -> dict:
    t = baseline["t"] - baseline["t"][0]
    fs = 20.0
    raw_mm = baseline["raw_h"] / 10.0
    raw_tof = baseline["raw_tof_mm"]

    # Zero-phase ideal trajectory for noise isolation
    win_med = signal.medfilt(raw_mm, kernel_size=3)
    b_id, a_id = signal.butter(3, 1.2 / (fs / 2.0), btype="low")
    ideal_mm = signal.filtfilt(b_id, a_id, win_med)
    noise = raw_mm - ideal_mm

    d_tof = np.abs(np.diff(raw_tof))
    idx_5 = np.where((d_tof >= 5.0) & (d_tof < 10.0))[0] + 1
    idx_10 = np.where(d_tof >= 10.0)[0] + 1

    # Hann FFT / PSD
    n = len(noise)
    w = np.hanning(n)
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    psd = (np.abs(np.fft.rfft(noise * w)) ** 2) / (fs * np.sum(w ** 2))
    tot = float(np.sum(psd)) + 1e-12
    bands = [
        ("0–1 Hz\n(Señal útil)", 0.0, 1.0, "#DCFCE7"),
        ("1–2 Hz\n(Transición)", 1.0, 2.0, "#FEF3C7"),
        ("2–5 Hz\n(Ruido medio)", 2.0, 5.0, "#FFEDD5"),
        ("5–10 Hz\n(Alta frec.)", 5.0, 10.01, "#FEE2E2"),
    ]
    band_pcts = {}
    for label, flo, fhi, _ in bands:
        m = (freqs >= flo) & (freqs < fhi)
        band_pcts[label.splitlines()[0]] = round(float(np.sum(psd[m]) / tot * 100.0), 2)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10.5, 6.4))
    ax1.plot(t, raw_mm, color=SLATE, lw=1.1, alpha=0.85, label="ToF crudo (escala mm)")
    ax1.plot(t, ideal_mm, color=NAVY, lw=1.8, ls="--", label="Trayectoria suavizada (fase cero)")
    if len(idx_5):
        ax1.scatter(t[idx_5], raw_mm[idx_5], color=AMBER, s=26, zorder=4, label=f"Saltos 5–10 mm ({len(idx_5)})")
    if len(idx_10):
        ax1.scatter(t[idx_10], raw_mm[idx_10], color=CORAL, s=46, marker="x", lw=1.8, zorder=5, label=f"Saltos ≥ 10 mm ({len(idx_10)})")
    ax1.set_title("A) Señal Cruda del Sensor VL53L0X en Vuelo Dinámico y Detección de Saltos Impulsivos")
    ax1.set_xlabel("Tiempo en modo PID (s)")
    ax1.set_ylabel("Desplazamiento ToF (mm)")
    ax1.grid(True)
    ax1.legend(loc="upper right", ncol=2)

    for label, flo, fhi, col in bands:
        ax2.axvspan(flo, min(fhi, 10.0), color=col, alpha=0.65)
        pct = band_pcts[label.splitlines()[0]]
        ax2.text((flo + min(fhi, 10.0)) / 2, np.max(psd) * 0.87, f"{label}\n{pct:.1f}%",
                 ha="center", va="top", fontsize=8.0, fontweight="bold", color="#1E293B")
    ax2.plot(freqs, psd, color=NAVY, lw=1.7, label="PSD del ruido dinámico (ventana Hann)")
    ax2.axvline(1.5, color=TEAL, ls="--", lw=1.8, label="Corte Butter2 ganador (fc = 1.5 Hz)")
    ax2.set_xlim(0, 10.0)
    ax2.set_ylim(0, np.max(psd) * 1.08)
    ax2.set_title("B) Densidad Espectral de Potencia (FFT/PSD) del Ruido sobre Trayectoria Real")
    ax2.set_xlabel("Frecuencia (Hz)")
    ax2.set_ylabel("PSD (mm²/Hz)")
    ax2.grid(True)
    ax2.legend(loc="center right")

    fig.tight_layout()
    save_fig(fig, "fig2_espectro_fft_ruido")
    return {"bands_pct": band_pcts, "spikes_5_10": int(len(idx_5)), "spikes_ge_10": int(len(idx_10))}


def make_fig3_filter_comparison(suite_results: list[dict]) -> None:
    fs = 20.0
    w_grid = np.linspace(0.01, fs / 2.0, 500)
    filters_tf = [
        ("EMA (α=0.30)", [0.30], [1.0, -0.70], SLATE, "--"),
        ("SMA (N=5)", [0.2] * 5, [1.0], AMBER, "-."),
        ("Butter2 (1.5 Hz) ★", [0.04125354, 0.08250707, 0.04125354], [1.0, -1.34896775, 0.51398189], EMERALD, "-"),
        ("Bessel2 (2.0 Hz)", [0.06327976, 0.12655953, 0.06327976], [1.0, -1.07222953, 0.32534858], VIOLET, ":"),
        ("Cheby1-2 (1.8 Hz)", [0.08298522, 0.16597045, 0.08298522], [1.0, -1.13091303, 0.46285393], CORAL, "-"),
    ]

    fig = plt.figure(figsize=(12.2, 6.8))
    gs = fig.add_gridspec(2, 2, width_ratios=[1.15, 1.0], hspace=0.36, wspace=0.28)
    ax_mag = fig.add_subplot(gs[0, 0])
    ax_phs = fig.add_subplot(gs[1, 0], sharex=ax_mag)
    ax_std = fig.add_subplot(gs[0, 1])
    ax_scr = fig.add_subplot(gs[1, 1])

    for name, b, a, col, ls in filters_tf:
        f_hz, h = signal.freqz(b, a, worN=w_grid, fs=fs)
        mag_db = 20.0 * np.log10(np.maximum(np.abs(h), 1e-6))
        phs_deg = np.unwrap(np.angle(h)) * 180.0 / np.pi
        lw = 2.4 if "★" in name else 1.5
        ax_mag.plot(f_hz, mag_db, color=col, ls=ls, lw=lw, label=name)
        ax_phs.plot(f_hz, phs_deg, color=col, ls=ls, lw=lw)

    ax_mag.axvline(0.35, color=NAVY, ls=":", lw=1.1, label="Senoidal (0.35 Hz)")
    ax_mag.axhline(-3.0, color="#94A3B8", ls="--", lw=0.9)
    ax_mag.set_ylim(-35, 3)
    ax_mag.set_xlim(0, 10)
    ax_mag.set_ylabel("Magnitud (dB)")
    ax_mag.set_title("A) Diagrama de Bode Digital (fs = 20 Hz)")
    ax_mag.grid(True)
    ax_mag.legend(loc="lower left", ncol=2, fontsize=7.8)

    ax_phs.axvline(0.35, color=NAVY, ls=":", lw=1.1)
    ax_phs.set_xlabel("Frecuencia (Hz)")
    ax_phs.set_ylabel("Fase (°)")
    ax_phs.grid(True)

    # Bar charts from real flight suite
    names = [r["filter_name"].replace("LIVE · Median3+", "") for r in suite_results]
    stds = [r["std_mm"] for r in suite_results]
    p2ps = [r["p2p_mm"] for r in suite_results]
    scores = [r["smoothness_score"] for r in suite_results]
    bar_cols = [EMERALD if r["filter_mode"] == 2 else "#64748B" for r in suite_results]

    x = np.arange(len(names))
    w = 0.36
    b1 = ax_std.bar(x - w / 2, stds, w, color=NAVY, label="STD ruido (mm)")
    b2 = ax_std.bar(x + w / 2, p2ps, w, color=CORAL, alpha=0.82, label="P2P ruido (mm)")
    ax_std.set_xticks(x)
    ax_std.set_xticklabels(names, rotation=16, ha="right", fontsize=8.2)
    ax_std.set_ylabel("Ruido residual (mm)")
    ax_std.set_title("B) Ruido Medido en Vuelo Real (COM4, 12 s c/u)")
    ax_std.grid(True, axis="y")
    ax_std.legend(loc="upper left")
    for bar, v in zip(b1, stds):
        ax_std.text(bar.get_x() + bar.get_width() / 2, v + 0.4, f"{v:.2f}", ha="center", fontsize=7.5)

    bs = ax_scr.bar(x, scores, 0.56, color=bar_cols)
    ax_scr.set_xticks(x)
    ax_scr.set_xticklabels(names, rotation=16, ha="right", fontsize=8.2)
    ax_scr.set_ylabel("Smoothness Score (0–100)")
    ax_scr.set_ylim(0, 68)
    ax_scr.set_title("C) Puntaje Global en Vuelo Real (Verde = Ganador)")
    ax_scr.grid(True, axis="y")
    for bar, v in zip(bs, scores):
        ax_scr.text(bar.get_x() + bar.get_width() / 2, v + 1.4, f"{v:.1f}", ha="center", fontsize=8.5, fontweight="bold")

    fig.suptitle("Evaluación Frecuencial y Experimental de los 5 Filtros Pasabajas Implementados",
                 fontsize=12, fontweight="bold", color=NAVY, y=0.98)
    save_fig(fig, "fig3_comparativa_filtros")


def make_fig4_winning_flight(winner_flight: dict[str, np.ndarray]) -> None:
    t = winner_flight["t"] - winner_flight["t"][0]
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10.8, 7.8), sharex=True)

    ax1.plot(t, winner_flight["raw_h"], color=CORAL, alpha=0.45, lw=1.2, label="ToF crudo (u.)")
    ax1.plot(t, winner_flight["ref_h"], color=AMBER, ls="--", lw=1.7, label="Referencia senoidal (0.35 Hz)")
    ax1.plot(t, winner_flight["filt_h"], color=TEAL, lw=2.2, label="Altura filtrada (Median3 + Butter2 1.5 Hz)")
    ax1.axhline(1000, color=CORAL, ls=":", lw=1.0, alpha=0.6, label="Tope superior (20 cm = 1000 u.)")
    ax1.set_ylabel("Altura (u. ToF)")
    ax1.set_title("A) Seguimiento de Altura — Vuelo Ganador Median3 + Butterworth 2° (1.5 Hz)")
    ax1.grid(True)
    ax1.legend(loc="upper right", ncol=2)

    ax2.plot(t, winner_flight["filt_a"], color=EMERALD, lw=1.8, label="Ángulo relativo controlado θ (°)")
    ax2.axhline(0.0, color=NAVY, ls="--", lw=1.1, label="Consigna angular (0°)")
    ax2.set_ylabel("Ángulo (°)")
    ax2.set_title("B) Estabilidad del Eje Angular (BNO055 IMUPLUS + EMA α = 0.70)")
    ax2.grid(True)
    ax2.legend(loc="upper right")

    ax3.plot(t, winner_flight["pwm_l"], color=NAVY, lw=1.6, label="ESC Izquierdo (GPIO25)")
    ax3.plot(t, winner_flight["pwm_r"], color=VIOLET, lw=1.4, ls="--", label="ESC Derecho (GPIO26)")
    ax3.axhline(58.0, color=SLATE, ls=":", lw=1.1, label="Base hover (58% = 1580 µs)")
    ax3.set_xlabel("Tiempo en modo PID (s)")
    ax3.set_ylabel("PWM (%)")
    ax3.set_ylim(40, 102)
    ax3.set_title("C) Esfuerzo de Actuadores PWM (Rampa máxima 20%/s = 200 µs/s)")
    ax3.grid(True)
    ax3.legend(loc="lower right", ncol=3)

    fig.tight_layout()
    save_fig(fig, "fig4_vuelo_ganador_senoidal")


def make_fig5_ident_and_poles(model: dict) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.8, 4.8), gridspec_kw={"width_ratios": [1.35, 1.0]})

    ax1.plot(model["t_uni"], model["y_uni"], color=NAVY, lw=2.0, label="Altura real medida (mm físicos)")
    ax1.plot(model["t_uni"], model["y_hat"], color=CORAL, ls="--", lw=2.0,
             label=f"Modelo G(s)/G(z) (R²={model['r2']:.3f}, RMSE={model['rmse_mm']:.1f} mm)")
    ax1.set_xlabel("Tiempo (s)")
    ax1.set_ylabel("Altura física z (mm)")
    ax1.set_title("A) Validación del Modelo Identificado vs Vuelo Real")
    ax1.grid(True)
    ax1.legend(loc="upper right")

    # Unit circle & z-plane poles/zeros
    theta = np.linspace(0, 2 * np.pi, 300)
    ax2.plot(np.cos(theta), np.sin(theta), color="#64748B", ls="--", lw=1.2, label="Círculo unitario |z|=1")
    ax2.axhline(0, color="#CBD5E1", lw=0.8)
    ax2.axvline(0, color="#CBD5E1", lw=0.8)

    # Butter2 (1.5 Hz) poles and zeros
    b_but = [0.04125354, 0.08250707, 0.04125354]
    a_but = [1.0, -1.34896775, 0.51398189]
    z_but, p_but, _ = signal.tf2zpk(b_but, a_but)
    p_plant = np.roots(model["az"])

    ax2.scatter(np.real(p_but), np.imag(p_but), marker="x", s=85, lw=2.2, color=EMERALD, label="Polos Butter2 (1.5 Hz)")
    ax2.scatter(np.real(z_but), np.imag(z_but), marker="o", s=65, facecolors="none", edgecolors=EMERALD, lw=1.8, label="Ceros Butter2 (z = −1)")
    ax2.scatter(np.real(p_plant), np.imag(p_plant), marker="x", s=85, lw=2.2, color=CORAL, label="Polos Planta G(z)")

    ax2.set_xlim(-1.25, 1.25)
    ax2.set_ylim(-1.15, 1.15)
    ax2.set_aspect("equal")
    ax2.set_xlabel("Re(z)")
    ax2.set_ylabel("Im(z)")
    ax2.set_title("B) Mapa de Polos y Ceros en el Plano Z (Ts = 0.05 s)")
    ax2.grid(True)
    ax2.legend(loc="lower left", fontsize=7.8)

    fig.tight_layout()
    save_fig(fig, "fig5_identificacion_y_polos")


def make_fig6_timeline() -> None:
    milestones = [
        ("v0.1 · Base", "Stub seguro,\nPCB 1-capa y\nconsola 3D"),
        ("v0.1 · Sensores", "I2C 100 kHz,\nBNO055 + VL53,\nGimbal→Cuaternión"),
        ("V8 / V9", "Manual, Auto,\nGestos MediaPipe\ny logger CSV"),
        ("DSP v2.0", "Reversión Kalman;\nMedian3 + EMA +\n4 rutinas 1-clic"),
        ("Suite 5 Filtros", "Fix failsafe ESC\n(FILTER,0..4 sin\nreset) + SSE live"),
        ("Ganador Final", "Butter2 (1.5 Hz)\nen flash ESP32 +\nModelado 2-DOF"),
    ]
    fig, ax = plt.subplots(figsize=(12.0, 3.0))
    ax.set_xlim(-0.5, len(milestones) - 0.5)
    ax.set_ylim(-1.1, 1.25)
    ax.axis("off")

    ax.plot([0, len(milestones) - 1], [0, 0], color=NAVY, lw=2.4, zorder=1)
    colors = [SLATE, NAVY, VIOLET, AMBER, TEAL, EMERALD]
    for i, ((title, desc), col) in enumerate(zip(milestones, colors)):
        ax.scatter([i], [0], s=140, color=col, edgecolor="#FFFFFF", lw=2.0, zorder=3)
        ax.text(i, 0.24, title, ha="center", va="bottom", fontsize=9.2, fontweight="bold", color=col)
        ax.text(i, -0.22, desc, ha="center", va="top", fontsize=8.0, color="#334155")
    ax.text((len(milestones) - 1) / 2, 1.02, "Evolución Técnica e Iteraciones de Laboratorio del Bicóptero 2-DOF",
            ha="center", va="center", fontsize=11.5, fontweight="bold", color=NAVY)
    save_fig(fig, "fig6_evolucion_proyecto")


def main() -> None:
    baseline = load_pid_csv(DATA_DIR / "dsp_flight_baseline.csv")
    winner = load_pid_csv(DATA_DIR / "dsp_suite_2_butter2.csv")
    suite_results = json.loads((DATA_DIR / "dsp_suite_results.json").read_text(encoding="utf-8"))

    model = identify_plant_and_statespace(winner)
    make_fig1_block_diagram()
    fft_info = make_fig2_fft_noise(baseline)
    make_fig3_filter_comparison(suite_results)
    make_fig4_winning_flight(winner)
    make_fig5_ident_and_poles(model)
    make_fig6_timeline()

    export = {
        "plant_identification": {
            "ts_s": model["ts"],
            "K_dc_mm_per_pct": round(model["k_dc"], 4),
            "wn_rad_s": round(model["wn"], 4),
            "zeta": round(model["zeta"], 4),
            "u_eq_pct": round(model["u_eq"], 3),
            "r2": round(model["r2"], 4),
            "rmse_mm": round(model["rmse_mm"], 3),
            "G_s_num": [round(float(x), 5) for x in model["num_c"]],
            "G_s_den": [round(float(x), 5) for x in model["den_c"]],
            "G_z_num": [round(float(x), 6) for x in model["bz"]],
            "G_z_den": [round(float(x), 6) for x in model["az"]],
            "G_z_poles": [[round(float(p.real), 5), round(float(p.imag), 5)] for p in np.roots(model["az"])],
        },
        "state_space": {
            "A": np.round(model["A"], 5).tolist(),
            "B": np.round(model["B"], 5).tolist(),
            "C": model["C"].tolist(),
            "Phi": np.round(model["Phi"], 5).tolist(),
            "Gamma": np.round(model["Gamma"], 5).tolist(),
            "rank_controllability": model["rank_ctrb"],
            "rank_observability": model["rank_obsv"],
            "eigs_continuous": [[round(float(e.real), 4), round(float(e.imag), 4)] for e in model["eigs_c"]],
            "eigs_discrete": [[round(float(e.real), 5), round(float(e.imag), 5)] for e in model["eigs_d"]],
            "eigs_discrete_abs": [round(float(abs(e)), 5) for e in model["eigs_d"]],
        },
        "butter2_z_poles": [
            [round(float(p.real), 5), round(float(p.imag), 5), round(float(abs(p)), 5)]
            for p in np.roots([1.0, -1.34896775, 0.51398189])
        ],
        "fft_baseline": fft_info,
    }
    OUT_JSON.write_text(json.dumps(export, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(export, indent=2, ensure_ascii=False))
    print("ALL_6_FIGURES_GENERATED_OK")


if __name__ == "__main__":
    main()
