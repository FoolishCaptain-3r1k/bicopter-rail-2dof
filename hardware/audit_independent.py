"""Independent raster-pixel & firmware-contract auditor for the 1-layer PCB."""

from __future__ import annotations

import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from hardware.pcb_spec import PcbBoard, build_default_board
from hardware.render import BoardPlacement, _draw_bottom_instance

EXPECTED_ESP32_LEFT_PINS: tuple[str, ...] = (
    "EN",
    "VP",
    "VN",
    "D34",
    "D35",
    "D32",
    "D33",
    "D25",
    "D26",
    "D27",
    "D14",
    "D12",
    "D13",
    "GND_L",
    "VIN",
)

EXPECTED_ESP32_RIGHT_PINS: tuple[str, ...] = (
    "D23",
    "D22",
    "TX0",
    "RX0",
    "D21",
    "D19",
    "D18",
    "D5",
    "TX2",
    "RX2",
    "D4",
    "D2",
    "D15",
    "GND_R",
    "3V3",
)

EXPECTED_J_TOF_PINS: tuple[str, ...] = ("3V3", "GND", "SCL", "SDA", "NC", "XSHUT")
EXPECTED_J_IMU_PINS: tuple[str, ...] = ("3V3", "GND", "SCL", "SDA")


@dataclass(frozen=True)
class FirmwareAuditResult:
    """Result of cross-checking firmware/include/config.h against physical PCB pads."""

    passed: bool
    parsed_pins: dict[str, int]
    errors: list[str] = field(default_factory=list)


@dataclass
class PixelNetlistReport:
    """Connected-component netlist extracted purely from rasterized copper pixels."""

    labels_img: np.ndarray
    num_components: int
    pad_to_component: dict[str, int]
    component_to_pads: dict[int, set[str]]
    reconstructed_nets: list[frozenset[str]]
    short_circuits: list[str] = field(default_factory=list)
    open_circuits: list[str] = field(default_factory=list)
    isolated_violations: list[str] = field(default_factory=list)
    banner_violations: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return (
            len(self.short_circuits) == 0
            and len(self.open_circuits) == 0
            and len(self.isolated_violations) == 0
            and len(self.banner_violations) == 0
        )


def verify_firmware_pin_contract(config_h_path: Path, board: PcbBoard) -> FirmwareAuditResult:
    """Parse firmware/include/config.h and verify exact physical pin mapping on the PCB."""
    text = config_h_path.read_text(encoding="utf-8")
    errors: list[str] = []
    required_symbols = (
        "I2C_SDA_PIN",
        "I2C_SCL_PIN",
        "TOF_XSHUT_PIN",
        "ESC_LEFT_PIN",
        "ESC_RIGHT_PIN",
    )
    parsed: dict[str, int] = {}
    for sym in required_symbols:
        m = re.search(rf"constexpr\s+\w+\s+{sym}\s*=\s*(\d+)\s*;", text)
        if not m:
            errors.append(f"Missing or unparseable {sym} in {config_h_path}")
        else:
            parsed[sym] = int(m.group(1))

    # Verify physical ESP32 30-pin layout (top-down left 1..15, right 1..15, 25.40 mm spacing)
    esp_pads = [p for p in board.pads if p.component == "ESP32"]
    left_pads = sorted([p for p in esp_pads if p.x_mm < board.banner_center_x_mm], key=lambda p: -p.y_mm)
    right_pads = sorted([p for p in esp_pads if p.x_mm > board.banner_center_x_mm], key=lambda p: -p.y_mm)

    if tuple(p.pin_label for p in left_pads) != EXPECTED_ESP32_LEFT_PINS:
        errors.append(f"ESP32 left pinout mismatch: {[p.pin_label for p in left_pads]}")
    if tuple(p.pin_label for p in right_pads) != EXPECTED_ESP32_RIGHT_PINS:
        errors.append(f"ESP32 right pinout mismatch: {[p.pin_label for p in right_pads]}")

    if left_pads and right_pads:
        row_spacing = abs(right_pads[0].x_mm - left_pads[0].x_mm)
        if abs(row_spacing - 25.40) > 1e-3:
            errors.append(f"ESP32 row spacing {row_spacing:.3f} mm != 25.40 mm")

    # Verify J_TOF & J_IMU exact top-down pin order
    tof_pads = sorted([p for p in board.pads if p.component == "J_TOF"], key=lambda p: -p.y_mm)
    imu_pads = sorted([p for p in board.pads if p.component == "J_IMU"], key=lambda p: -p.y_mm)
    if tuple(p.pin_label for p in tof_pads) != EXPECTED_J_TOF_PINS:
        errors.append(f"J_TOF pinout mismatch: {[p.pin_label for p in tof_pads]}")
    if tuple(p.pin_label for p in imu_pads) != EXPECTED_J_IMU_PINS:
        errors.append(f"J_IMU pinout mismatch: {[p.pin_label for p in imu_pads]}")

    # Cross-check firmware GPIO pins against expected PCB pin labels and nets
    if len(parsed) == len(required_symbols):
        expected_gpio_nets = {
            f"D{parsed['I2C_SDA_PIN']}": ("I2C_SDA", {"J_TOF_SDA", "J_IMU_SDA"}),
            f"D{parsed['I2C_SCL_PIN']}": ("I2C_SCL", {"J_TOF_SCL", "J_IMU_SCL"}),
            f"D{parsed['TOF_XSHUT_PIN']}": ("TOF_XSHUT", {"J_TOF_XSHUT"}),
            f"D{parsed['ESC_LEFT_PIN']}": ("ESC_L_SIG", {"ESC_L_SIG"}),
            f"D{parsed['ESC_RIGHT_PIN']}": ("ESC_R_SIG", {"ESC_R_SIG"}),
        }
        for gpio_label, (expected_net, target_pad_names) in expected_gpio_nets.items():
            esp_pad = next((p for p in esp_pads if p.pin_label == gpio_label), None)
            if esp_pad is None:
                errors.append(f"Firmware pin {gpio_label} not found on ESP32 footprint")
                continue
            if esp_pad.net != expected_net:
                errors.append(f"ESP32 {gpio_label} net {esp_pad.net} != {expected_net}")
            for target_name in target_pad_names:
                t_pad = board.get_pad(target_name)
                if t_pad.net != expected_net:
                    errors.append(f"Target pad {target_name} net {t_pad.net} != {expected_net}")

    return FirmwareAuditResult(passed=len(errors) == 0, parsed_pins=parsed, errors=errors)


def rasterize_bottom_copper(
    board: PcbBoard,
    dpi: int = 300,
) -> tuple[np.ndarray, dict[str, tuple[int, int]]]:
    """Rasterize pcb_bottom_toner_1to1 copper layer via Agg at >= 300 DPI.

    Returns:
        toner_binary_img: Boolean ndarray (H, W) where True = black copper/toner pixel.
        pad_coords_px: Mapping pad_name -> (px_x, px_y) in image pixel coordinates.
    """
    if dpi < 300:
        raise ValueError(f"Audit DPI must be >= 300, got {dpi}")

    fig = Figure(figsize=(board.width_mm / 25.4, board.height_mm / 25.4), dpi=dpi, facecolor="white")
    canvas = FigureCanvasAgg(fig)
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0], frameon=False)
    ax.set_xlim(0.0, board.width_mm)
    ax.set_ylim(0.0, board.height_mm)
    ax.set_aspect("equal")
    ax.axis("off")

    placement = BoardPlacement(
        col=0,
        row=0,
        ox_mm=0.0,
        oy_mm=0.0,
        width_mm=board.width_mm,
        height_mm=board.height_mm,
        rotated_90=False,
    )
    _draw_bottom_instance(ax, board, placement)

    # Clear the thin outer board cut border (3 px edge) so outline ink is never mistaken for copper
    canvas.draw()
    rgba = np.asarray(canvas.buffer_rgba())
    gray = rgba[:, :, :3].mean(axis=2)
    toner_binary = gray < 128.0
    toner_binary[:4, :] = False
    toner_binary[-4:, :] = False
    toner_binary[:, :4] = False
    toner_binary[:, -4:] = False

    h, w = toner_binary.shape
    pad_coords_px: dict[str, tuple[int, int]] = {}
    for pad in board.pads:
        px = int(round((pad.x_mm / board.width_mm) * w))
        py = int(round(((board.height_mm - pad.y_mm) / board.height_mm) * h))
        px = max(0, min(w - 1, px))
        py = max(0, min(h - 1, py))
        pad_coords_px[pad.name] = (px, py)

    return toner_binary, pad_coords_px


def _connected_components_8(binary_img: np.ndarray) -> tuple[np.ndarray, int]:
    """Fast 8-connected component labeling via scanline-segment flood fill."""
    h, w = binary_img.shape
    labels = np.zeros((h, w), dtype=np.int32)
    img_rows = binary_img.tolist()
    lbl_rows = [[0] * w for _ in range(h)]
    comp_id = 0

    for y in range(h):
        row_data = img_rows[y]
        row_lbl = lbl_rows[y]
        for x in range(w):
            if row_data[x] and row_lbl[x] == 0:
                comp_id += 1
                row_lbl[x] = comp_id
                queue: deque[tuple[int, int]] = deque([(y, x)])
                while queue:
                    cy, cx = queue.popleft()
                    y0 = cy - 1 if cy > 0 else 0
                    y1 = cy + 1 if cy + 1 < h else h - 1
                    x0 = cx - 1 if cx > 0 else 0
                    x1 = cx + 1 if cx + 1 < w else w - 1
                    for ny in range(y0, y1 + 1):
                        n_data = img_rows[ny]
                        n_lbl = lbl_rows[ny]
                        for nx in range(x0, x1 + 1):
                            if n_data[nx] and n_lbl[nx] == 0:
                                n_lbl[nx] = comp_id
                                queue.append((ny, nx))

    labels[:] = np.asarray(lbl_rows, dtype=np.int32)
    return labels, comp_id


def _find_pad_copper_component(
    labels: np.ndarray,
    px: int,
    py: int,
    max_radius_px: int = 16,
) -> int:
    """Locate the copper component surrounding a pad's central white drill pilot hole."""
    h, w = labels.shape
    if labels[py, px] > 0:
        return int(labels[py, px])

    for radius in range(1, max_radius_px + 1):
        hits: list[int] = []
        y0 = max(0, py - radius)
        y1 = min(h - 1, py + radius)
        x0 = max(0, px - radius)
        x1 = min(w - 1, px + radius)
        for ny in range(y0, y1 + 1):
            for nx in range(x0, x1 + 1):
                if (nx - px) * (nx - px) + (ny - py) * (ny - py) <= radius * radius:
                    lbl = int(labels[ny, nx])
                    if lbl > 0:
                        hits.append(lbl)
        if hits:
            # Return the dominant component on the pad's annular ring
            return max(set(hits), key=hits.count)
    return 0


def _expected_net_groups(board: PcbBoard) -> tuple[dict[str, set[str]], set[str]]:
    """Build expected connected pad groups and isolated single-pad sets from board contract."""
    by_net: dict[str, set[str]] = defaultdict(set)
    for pad in board.pads:
        by_net[pad.net].add(pad.name)

    multi_nets: dict[str, set[str]] = {}
    isolated: set[str] = set()
    for net, names in by_net.items():
        if len(names) >= 2:
            multi_nets[net] = names
        else:
            isolated.update(names)
    return multi_nets, isolated


def extract_pixel_netlist(
    toner_binary_img: np.ndarray,
    pad_coords_px: dict[str, tuple[int, int]],
    board: PcbBoard | None = None,
) -> PixelNetlistReport:
    """Extract electrical connectivity strictly from rasterized copper pixels."""
    if board is None:
        board = build_default_board()

    labels, num_components = _connected_components_8(toner_binary_img)

    pad_to_comp: dict[str, int] = {}
    comp_to_pads: dict[int, set[str]] = defaultdict(set)
    for pad_name, (px, py) in pad_coords_px.items():
        cid = _find_pad_copper_component(labels, px, py)
        pad_to_comp[pad_name] = cid
        if cid > 0:
            comp_to_pads[cid].add(pad_name)

    reconstructed_nets = [frozenset(pads) for pads in comp_to_pads.values()]
    expected_multi, expected_isolated = _expected_net_groups(board)

    short_circuits: list[str] = []
    open_circuits: list[str] = []
    isolated_violations: list[str] = []
    banner_violations: list[str] = []

    # Check every expected multi-pad net forms a single pixel component with no extra pads
    for net_name, expected_pads in expected_multi.items():
        comps = {pad_to_comp.get(p, 0) for p in expected_pads}
        if 0 in comps:
            open_circuits.append(f"Net {net_name}: missing copper around pad(s)")
            continue
        if len(comps) > 1:
            open_circuits.append(f"Net {net_name}: split across {len(comps)} pixel components")
            continue
        cid = next(iter(comps))
        actual_pads = comp_to_pads[cid]
        extra = actual_pads - expected_pads
        if extra:
            short_circuits.append(f"Net {net_name} shorted to {sorted(extra)}")

    # Check isolated pads (ESP32_VIN, J_TOF_NC, and unused ESP32 pins)
    for iso_pad in sorted(expected_isolated):
        cid = pad_to_comp.get(iso_pad, 0)
        if cid == 0:
            open_circuits.append(f"Isolated pad {iso_pad} missing copper ring")
            continue
        actual_pads = comp_to_pads[cid]
        if actual_pads != {iso_pad}:
            isolated_violations.append(
                f"Isolated pad {iso_pad} bridged to {sorted(actual_pads - {iso_pad})}"
            )

    # Check artistic banner pixels (top band y > 56.0 mm) never connect to any pad component
    h, w = toner_binary_img.shape
    banner_y_end = int(round(((board.height_mm - 56.5) / board.height_mm) * h))
    banner_region_labels = set(np.unique(labels[:banner_y_end, :]).tolist()) - {0}
    pad_comp_ids = set(comp_to_pads.keys())
    shorted_banner = banner_region_labels & pad_comp_ids
    if shorted_banner:
        banner_violations.append(f"Artistic banner shorted to pad component(s): {sorted(shorted_banner)}")

    return PixelNetlistReport(
        labels_img=labels,
        num_components=num_components,
        pad_to_component=pad_to_comp,
        component_to_pads=dict(comp_to_pads),
        reconstructed_nets=reconstructed_nets,
        short_circuits=short_circuits,
        open_circuits=open_circuits,
        isolated_violations=isolated_violations,
        banner_violations=banner_violations,
    )


def render_iron_transfer_audit(
    out_path: Path,
    board: PcbBoard | None = None,
    dpi: int = 300,
) -> Path:
    """Generate 2-panel verification overlay PNG:
    (Left) Horizontally flipped toner image simulating iron-on transfer viewed from bottom,
           overlaid with expected bottom-view pin markers and upright Anáhuac banner check.
    (Right) Connected-component color map extracted directly from 300+ DPI copper pixels.
    """
    if board is None:
        board = build_default_board()

    toner_binary, pad_coords_px = rasterize_bottom_copper(board, dpi=dpi)
    report = extract_pixel_netlist(toner_binary, pad_coords_px, board=board)

    fig, (ax_left, ax_right) = plt.subplots(1, 2, figsize=(16.0, 8.2), dpi=200, facecolor="white")

    # Left Panel: Horizontally flipped toner (iron-on B.Cu viewed from underside)
    flipped_toner = np.fliplr(toner_binary)
    ax_left.imshow(
        np.where(flipped_toner, 0.12, 1.0),
        cmap="gray",
        vmin=0.0,
        vmax=1.0,
        extent=[0.0, board.width_mm, 0.0, board.height_mm],
        origin="upper",
    )
    net_colors = {
        "+VBAT_SW": "#D62728",
        "GND": "#1F77B4",
        "3V3": "#FF7F0E",
        "I2C_SCL": "#2CA02C",
        "I2C_SDA": "#9467BD",
        "TOF_XSHUT": "#17BECF",
        "ESC_L_SIG": "#E377C2",
        "ESC_R_SIG": "#BCBD22",
        "ESP32_VIN": "#000000",
        "NC_J_TOF_NC": "#7F7F7F",
    }
    for pad in board.pads:
        # Bottom-view X coordinate after horizontal flip is (width - x)
        bx = board.width_mm - pad.x_mm
        by = pad.y_mm
        color = net_colors.get(pad.net, "#AAAAAA")
        ax_left.scatter([bx], [by], s=26, color=color, alpha=0.65, edgecolors="white", linewidths=0.4, zorder=4)
        if pad.component in ("J_TOF", "J_IMU", "PWR_ESC") or pad.pin_label in (
            "D25",
            "D26",
            "D22",
            "D21",
            "D19",
            "GND_L",
            "GND_R",
            "3V3",
            "VIN",
        ):
            ax_left.text(
                bx,
                by + 1.15,
                pad.pin_label,
                fontsize=4.6,
                ha="center",
                va="bottom",
                color=color,
                fontweight="bold",
                zorder=5,
            )

    ax_left.set_title(
        "1. Simulacion Planchado B.Cu (Volteado Horizontal)\n"
        "Emblema/Nombres al derecho + Coincidencia pines vistos desde abajo",
        fontsize=9.5,
        fontweight="bold",
    )
    ax_left.set_xlabel("X vista inferior (mm)")
    ax_left.set_ylabel("Y (mm)")

    # Right Panel: Pixel-extracted connected components color map
    h, w = report.labels_img.shape
    rgb = np.ones((h, w, 3), dtype=np.float32)

    # Color non-pad components (artistic banner + M3 outline) in slate gray
    rgb[report.labels_img > 0] = (0.55, 0.58, 0.62)

    palette_rgb = [
        (0.12, 0.47, 0.71),  # blue
        (0.84, 0.15, 0.16),  # red
        (0.17, 0.63, 0.17),  # green
        (1.00, 0.50, 0.05),  # orange
        (0.58, 0.40, 0.74),  # purple
        (0.09, 0.75, 0.81),  # cyan
        (0.89, 0.47, 0.76),  # pink
        (0.74, 0.74, 0.13),  # olive
    ]
    comp_color_map: dict[int, tuple[float, float, float]] = {}
    multi_idx = 0
    for cid, pads in sorted(report.component_to_pads.items(), key=lambda kv: -len(kv[1])):
        if len(pads) >= 2:
            col_rgb = palette_rgb[multi_idx % len(palette_rgb)]
            multi_idx += 1
        else:
            col_rgb = (0.20, 0.20, 0.20)
        comp_color_map[cid] = col_rgb
        rgb[report.labels_img == cid] = col_rgb

    ax_right.imshow(rgb, extent=[0.0, board.width_mm, 0.0, board.height_mm], origin="upper")
    status_str = "PASS: 0 cortos | 0 abiertas" if report.passed else "FAIL: Revisar conectividad"
    ax_right.set_title(
        f"2. Mapa Componentes Conectados (Pixeles {dpi} DPI)\n{status_str} | {len(report.component_to_pads)} redes/islas",
        fontsize=9.5,
        fontweight="bold",
        color="#006600" if report.passed else "#AA0000",
    )
    ax_right.set_xlabel("X vista superior toner (mm)")
    ax_right.set_ylabel("Y (mm)")

    legend_handles = [
        mpatches.Patch(color=col_rgb, label=f"Comp #{cid} ({len(report.component_to_pads[cid])} pads)")
        for cid, col_rgb in list(comp_color_map.items())[:8]
    ]
    ax_right.legend(handles=legend_handles, loc="upper right", fontsize=6.5, framealpha=0.92)

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, format="png", dpi=200)
    plt.close(fig)
    return out_path
