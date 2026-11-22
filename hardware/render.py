"""1:1 physical scale (mm) SVG and PDF exporter for B.Cu toner transfer, Top Assembly, and Drill Map."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

from hardware.pcb_spec import PcbBoard, build_default_board

PAGE_W_MM = 116.0
PAGE_H_MM = 114.0
BOARD_OX_MM = 12.0
BOARD_OY_MM = 18.0
RULER_LEN_MM = 50.0

LETTER_W_MM = 215.9
LETTER_H_MM = 279.4
LETTER_W_PT = 612.0
LETTER_H_PT = 792.0
LETTER_WARNING_TEXT = "CARTA 1:1 - IMPRIMIR AL 100% (NO AJUSTAR A PAGINA)"


@dataclass(frozen=True)
class BoardPlacement:
    """Single board instance placement on a US Letter sheet (in mm)."""

    col: int
    row: int
    ox_mm: float
    oy_mm: float
    width_mm: float
    height_mm: float
    rotated_90: bool


@dataclass(frozen=True)
class LetterLayout:
    """Complete multi-copy US Letter panel layout (in mm)."""

    cols: int
    rows: int
    rotated_90: bool
    margin_mm: float
    gap_mm: float
    header_mm: float
    placements: tuple[BoardPlacement, ...]
    h_ruler: tuple[float, float, float, float]  # (x1, y1, x2, y2)
    v_ruler: tuple[float, float, float, float]  # (x1, y1, x2, y2)


@dataclass(frozen=True)
class LabelBox:
    """Bounding box and placement metadata for one Top Assembly label (board coordinates in mm)."""

    x_min_mm: float
    y_min_mm: float
    x_max_mm: float
    y_max_mm: float
    text: str
    anchor_x_mm: float
    anchor_y_mm: float
    ha: str  # "left", "center", "right"
    va: str  # "bottom", "center", "top"
    fontsize_pt: float
    color: str = "#000000"
    category: str = "pin"  # "pin", "header", "callout", "note"
    callout_target: tuple[float, float] | None = None
    draw_bg: bool = False


def _make_label_box(
    text: str,
    anchor_x_mm: float,
    anchor_y_mm: float,
    ha: str,
    va: str,
    fontsize_pt: float,
    color: str = "#000000",
    category: str = "pin",
    callout_target: tuple[float, float] | None = None,
    draw_bg: bool = False,
) -> LabelBox:
    """Estimate conservative monospace bounding box (mm) from font size and alignment."""
    char_h_mm = fontsize_pt * (25.4 / 72.0)
    char_w_mm = char_h_mm * 0.66
    line_h_mm = char_h_mm * 1.18
    lines = text.split("\n")
    max_chars = max(len(line) for line in lines)
    box_w = max_chars * char_w_mm + 0.20
    box_h = len(lines) * line_h_mm + 0.14

    if ha == "left":
        x_min, x_max = anchor_x_mm, anchor_x_mm + box_w
    elif ha == "right":
        x_min, x_max = anchor_x_mm - box_w, anchor_x_mm
    else:
        x_min, x_max = anchor_x_mm - box_w / 2.0, anchor_x_mm + box_w / 2.0

    if va == "bottom":
        y_min, y_max = anchor_y_mm, anchor_y_mm + box_h
    elif va == "top":
        y_min, y_max = anchor_y_mm - box_h, anchor_y_mm
    else:
        y_min, y_max = anchor_y_mm - box_h / 2.0, anchor_y_mm + box_h / 2.0

    return LabelBox(
        x_min_mm=round(x_min, 3),
        y_min_mm=round(y_min, 3),
        x_max_mm=round(x_max, 3),
        y_max_mm=round(y_max, 3),
        text=text,
        anchor_x_mm=round(anchor_x_mm, 3),
        anchor_y_mm=round(anchor_y_mm, 3),
        ha=ha,
        va=va,
        fontsize_pt=fontsize_pt,
        color=color,
        category=category,
        callout_target=callout_target,
        draw_bg=draw_bg,
    )


def get_top_assembly_label_boxes(board: PcbBoard) -> list[LabelBox]:
    """Generate non-overlapping Top Assembly label boxes consumed by both SVG and PDF renderers."""
    boxes: list[LabelBox] = []

    left_power_text = {
        "ESC_L_VBAT": "ESC_L\n+VBAT",
        "ESC_R_VBAT": "ESC_R\n+VBAT",
        "BAT_VBAT_IN": "BAT\n+VBAT",
        "ESC_L_GND_PWR": "ESC_L\nGND P",
        "ESC_R_GND_PWR": "ESC_R\nGND P",
        "BAT_GND_IN": "BAT\nGND",
    }
    left_sig_layout = {
        "ESC_L_GND_SIG": ("ESC_L\nGND S", 26.20, 45.40, -1.05),
        "ESC_L_SIG": ("ESC_L\nPWM", 26.20, 36.90, -1.05),
        "ESC_R_SIG": ("ESC_R\nPWM", 26.20, 23.85, 1.05),
        "ESC_R_GND_SIG": ("ESC_R\nGND S", 26.20, 16.60, 1.05),
    }

    for pad in board.pads:
        if pad.component == "ESP32":
            # Left row inside ESP32 outline (ha="left"), right row inside ESP32 outline (ha="right")
            if pad.x_mm < board.banner_center_x_mm:
                boxes.append(
                    _make_label_box(
                        text=pad.pin_label,
                        anchor_x_mm=pad.x_mm + 1.40,
                        anchor_y_mm=pad.y_mm,
                        ha="left",
                        va="center",
                        fontsize_pt=3.9,
                        color="#000000",
                        category="pin",
                    )
                )
            else:
                boxes.append(
                    _make_label_box(
                        text=pad.pin_label,
                        anchor_x_mm=pad.x_mm - 1.40,
                        anchor_y_mm=pad.y_mm,
                        ha="right",
                        va="center",
                        fontsize_pt=3.9,
                        color="#000000",
                        category="pin",
                    )
                )
        elif pad.name in left_power_text:
            # Centered below each power pad in 2 compact lines (5.0 pt) with callout to pad edge
            boxes.append(
                _make_label_box(
                    text=left_power_text[pad.name],
                    anchor_x_mm=pad.x_mm,
                    anchor_y_mm=pad.y_mm - 6.00,
                    ha="center",
                    va="center",
                    fontsize_pt=4.9,
                    color="#000000",
                    category="callout",
                    callout_target=(pad.x_mm, pad.y_mm - (pad.drill_mm / 2.0 + 0.50)),
                    draw_bg=True,
                )
            )
        elif pad.name in left_sig_layout:
            text, lx, ly, dy_target = left_sig_layout[pad.name]
            boxes.append(
                _make_label_box(
                    text=text,
                    anchor_x_mm=lx,
                    anchor_y_mm=ly,
                    ha="center",
                    va="center",
                    fontsize_pt=4.8,
                    color="#000000",
                    category="callout",
                    callout_target=(pad.x_mm, pad.y_mm - dy_target),
                    draw_bg=True,
                )
            )
        elif pad.component in ("J_TOF", "J_IMU"):
            boxes.append(
                _make_label_box(
                    text=pad.pin_label,
                    anchor_x_mm=pad.x_mm + 1.45,
                    anchor_y_mm=pad.y_mm,
                    ha="left",
                    va="center",
                    fontsize_pt=4.0,
                    color="#000000",
                    category="pin",
                )
            )

    # J_TOF and J_IMU headers cleanly positioned above pin 1
    boxes.append(
        _make_label_box(
            text="J_TOF",
            anchor_x_mm=71.00,
            anchor_y_mm=42.80,
            ha="center",
            va="bottom",
            fontsize_pt=5.2,
            color="#003399",
            category="header",
        )
    )
    boxes.append(
        _make_label_box(
            text="J_IMU",
            anchor_x_mm=82.00,
            anchor_y_mm=42.80,
            ha="center",
            va="bottom",
            fontsize_pt=5.2,
            color="#003399",
            category="header",
        )
    )

    # Reserved top/bottom assembly notes (strictly outside ESP32 outline & banner frame)
    boxes.append(
        _make_label_box(
            text="ESP32 USB (BORDE INFERIOR)",
            anchor_x_mm=46.00,
            anchor_y_mm=1.35,
            ha="center",
            va="center",
            fontsize_pt=5.0,
            color="#003399",
            category="note",
        )
    )
    boxes.append(
        _make_label_box(
            text="GY-BNO055: PUENTE ADD-GND (0x28) | SWITCH 30x20x20 mm +VBAT",
            anchor_x_mm=46.00,
            anchor_y_mm=53.80,
            ha="center",
            va="center",
            fontsize_pt=4.8,
            color="#990000",
            category="note",
        )
    )

    return boxes


def compute_letter_tiling(
    board_w_mm: float,
    board_h_mm: float,
    margin_mm: float = 8.0,
    gap_mm: float = 6.0,
    header_mm: float = 16.0,
) -> tuple[int, int, bool]:
    """Compute maximum (cols, rows, rotated_90) grid fitting inside US Letter printable area."""
    avail_w = LETTER_W_MM - 2.0 * margin_mm
    avail_h = LETTER_H_MM - 2.0 * margin_mm - header_mm

    def _fit(w: float, h: float) -> tuple[int, int]:
        if w <= 0.0 or h <= 0.0 or w > avail_w + 1e-9 or h > avail_h + 1e-9:
            return (0, 0)
        cols = int(math.floor((avail_w + gap_mm + 1e-9) / (w + gap_mm)))
        rows = int(math.floor((avail_h + gap_mm + 1e-9) / (h + gap_mm)))
        return (max(0, cols), max(0, rows))

    c0, r0 = _fit(board_w_mm, board_h_mm)
    c1, r1 = _fit(board_h_mm, board_w_mm)
    if (c1 * r1) > (c0 * r0):
        return (c1, r1, True)
    return (c0, r0, False)


def compute_letter_layout(
    board: PcbBoard,
    margin_mm: float = 8.0,
    gap_mm: float = 6.0,
    header_mm: float = 16.0,
) -> LetterLayout:
    """Compute centered board placements, crop marks, and calibration ruler bounds on US Letter."""
    cols, rows, rotated_90 = compute_letter_tiling(
        board.width_mm,
        board.height_mm,
        margin_mm=margin_mm,
        gap_mm=gap_mm,
        header_mm=header_mm,
    )
    inst_w = board.height_mm if rotated_90 else board.width_mm
    inst_h = board.width_mm if rotated_90 else board.height_mm

    avail_w = LETTER_W_MM - 2.0 * margin_mm
    avail_h = LETTER_H_MM - 2.0 * margin_mm - header_mm

    grid_w = cols * inst_w + max(0, cols - 1) * gap_mm
    grid_h = rows * inst_h + max(0, rows - 1) * gap_mm

    start_x = margin_mm + (avail_w - grid_w) / 2.0
    start_y = margin_mm + (avail_h - grid_h) / 2.0

    placements: list[BoardPlacement] = []
    for row in range(rows):
        for col in range(cols):
            ox = round(start_x + col * (inst_w + gap_mm), 4)
            oy = round(start_y + row * (inst_h + gap_mm), 4)
            placements.append(
                BoardPlacement(
                    col=col,
                    row=row,
                    ox_mm=ox,
                    oy_mm=oy,
                    width_mm=inst_w,
                    height_mm=inst_h,
                    rotated_90=rotated_90,
                )
            )

    # Horizontal 50.0 mm ruler in reserved header zone
    hx2 = round(LETTER_W_MM - margin_mm, 4)
    hx1 = round(hx2 - RULER_LEN_MM, 4)
    hy = round(LETTER_H_MM - margin_mm - header_mm + 4.5, 4)
    h_ruler = (hx1, hy, hx2, hy)

    # Vertical 50.0 mm ruler in clear left corridor (or inter-column gap if corridor is narrow)
    if (start_x - margin_mm) >= 4.0:
        vx = round(margin_mm + (start_x - margin_mm) / 2.0, 4)
    elif cols >= 2:
        vx = round(start_x + inst_w + gap_mm / 2.0, 4)
    else:
        vx = round(margin_mm + 1.5, 4)
    vy1 = round(start_y + max(0.0, (grid_h - RULER_LEN_MM) / 2.0), 4)
    vy2 = round(vy1 + RULER_LEN_MM, 4)
    v_ruler = (vx, vy1, vx, vy2)

    return LetterLayout(
        cols=cols,
        rows=rows,
        rotated_90=rotated_90,
        margin_mm=margin_mm,
        gap_mm=gap_mm,
        header_mm=header_mm,
        placements=tuple(placements),
        h_ruler=h_ruler,
        v_ruler=v_ruler,
    )


def _transform_point(
    x_mm: float,
    y_mm: float,
    board_w_mm: float,
    board_h_mm: float,
    placement: BoardPlacement,
) -> tuple[float, float]:
    """Apply rigid SE(2) transform (det = +1) preserving chirality."""
    if placement.rotated_90:
        return (placement.ox_mm + (board_h_mm - y_mm), placement.oy_mm + x_mm)
    return (placement.ox_mm + x_mm, placement.oy_mm + y_mm)


def _draw_letter_chrome(ax: plt.Axes, board: PcbBoard, layout: LetterLayout, subtitle: str) -> None:
    """Draw readable header warning, 50.0 mm H/V calibration rulers, and fine inter-copy crop marks."""
    pt_per_mm = 72.0 / 25.4
    hx1, hy1, hx2, hy2 = layout.h_ruler
    vx1, vy1, vx2, vy2 = layout.v_ruler

    # Header warning & metadata (always upright, outside board outlines)
    header_y = LETTER_H_MM - layout.margin_mm - 4.0
    ax.text(
        layout.margin_mm,
        header_y,
        LETTER_WARNING_TEXT,
        fontsize=8.5,
        fontweight="bold",
        family="monospace",
        color="black",
        va="center",
    )
    ax.text(
        layout.margin_mm,
        header_y - 5.0,
        f"{subtitle} | Placa: {board.width_mm:.1f}x{board.height_mm:.1f} mm | "
        f"Panel: {layout.cols}x{layout.rows} ({len(layout.placements)} copias)",
        fontsize=6.8,
        family="monospace",
        color="#333333",
        va="center",
    )

    # Horizontal 50.0 mm calibration ruler
    ax.plot([hx1, hx2], [hy1, hy2], color="black", linewidth=0.45 * pt_per_mm, solid_capstyle="butt")
    for tick in range(0, 55, 10):
        tx = hx1 + float(tick)
        ax.plot([tx, tx], [hy1 - 1.4, hy1 + 1.4], color="black", linewidth=0.30 * pt_per_mm)
    ax.text(
        (hx1 + hx2) / 2.0,
        hy1 + 2.4,
        "50.0 mm HORIZ (1:1)",
        fontsize=6.2,
        family="monospace",
        ha="center",
        color="black",
    )

    # Vertical 50.0 mm calibration ruler
    ax.plot([vx1, vx2], [vy1, vy2], color="black", linewidth=0.45 * pt_per_mm, solid_capstyle="butt")
    for tick in range(0, 55, 10):
        ty = vy1 + float(tick)
        ax.plot([vx1 - 1.1, vx1 + 1.1], [ty, ty], color="black", linewidth=0.30 * pt_per_mm)
    ax.text(
        vx1 - 1.5,
        (vy1 + vy2) / 2.0,
        "50.0 mm VERT (1:1)",
        fontsize=5.8,
        family="monospace",
        rotation=90,
        va="center",
        ha="right",
        color="black",
    )

    # Thin crop marks between copies (mid-gap crosshairs and outer corner ticks)
    tick_len = 2.2
    for pl in layout.placements:
        ox, oy, w, h = pl.ox_mm, pl.oy_mm, pl.width_mm, pl.height_mm
        for cx, cy in ((ox, oy), (ox + w, oy), (ox, oy + h), (ox + w, oy + h)):
            sx = -1.0 if cx == ox else 1.0
            sy = -1.0 if cy == oy else 1.0
            ax.plot([cx, cx + sx * tick_len], [cy, cy], color="#888888", linewidth=0.18 * pt_per_mm)
            ax.plot([cx, cx], [cy, cy + sy * tick_len], color="#888888", linewidth=0.18 * pt_per_mm)

    if layout.cols >= 2:
        for col in range(layout.cols - 1):
            mid_x = layout.placements[col].ox_mm + layout.placements[col].width_mm + layout.gap_mm / 2.0
            y_bot = layout.placements[0].oy_mm - 2.0
            y_top = layout.placements[-1].oy_mm + layout.placements[-1].height_mm + 2.0
            ax.plot(
                [mid_x, mid_x],
                [y_bot, y_top],
                color="#999999",
                linestyle="--",
                linewidth=0.18 * pt_per_mm,
            )
    if layout.rows >= 2:
        for row in range(layout.rows - 1):
            base_idx = row * layout.cols
            mid_y = layout.placements[base_idx].oy_mm + layout.placements[base_idx].height_mm + layout.gap_mm / 2.0
            x_left = layout.placements[0].ox_mm - 2.0
            x_right = layout.placements[layout.cols - 1].ox_mm + layout.placements[layout.cols - 1].width_mm + 2.0
            ax.plot(
                [x_left, x_right],
                [mid_y, mid_y],
                color="#999999",
                linestyle="--",
                linewidth=0.18 * pt_per_mm,
            )


def _svg_x(x_mm: float) -> float:
    return round(BOARD_OX_MM + x_mm, 3)


def _svg_y(y_mm: float, board_h_mm: float) -> float:
    return round((PAGE_H_MM - BOARD_OY_MM) - y_mm, 3)


def export_bottom_toner_svg(board: PcbBoard, out_path: Path) -> Path:
    """Export 1:1 monochrome black-on-white B.Cu toner transfer SVG."""
    lines: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{PAGE_W_MM:.2f}mm" height="{PAGE_H_MM:.2f}mm" '
            f'viewBox="0 0 {PAGE_W_MM:.2f} {PAGE_H_MM:.2f}" '
            f'data-layer="B.Cu" data-scale="1:1" '
            f'data-board-width-mm="{board.width_mm:.2f}" '
            f'data-board-height-mm="{board.height_mm:.2f}" '
            f'data-ruler-length-mm="{RULER_LEN_MM:.2f}" '
            f'data-banner-mirrored="true">'
        ),
        f'  <rect x="0" y="0" width="{PAGE_W_MM:.2f}" height="{PAGE_H_MM:.2f}" fill="#FFFFFF"/>',
    ]

    # Board cut outline (thin 0.25 mm border)
    bx = _svg_x(0.0)
    by = _svg_y(board.height_mm, board.height_mm)
    lines.append(
        f'  <rect id="board-outline" x="{bx:.3f}" y="{by:.3f}" '
        f'width="{board.width_mm:.3f}" height="{board.height_mm:.3f}" '
        f'fill="none" stroke="#000000" stroke-width="0.25"/>'
    )

    # 50.0 mm calibration ruler below board
    rx1 = _svg_x(0.0)
    rx2 = _svg_x(RULER_LEN_MM)
    ry = round(PAGE_H_MM - 7.0, 3)
    lines.append('  <g id="calibration-ruler" data-length-mm="50.0">')
    lines.append(
        f'    <line id="calibration-ruler-50mm" x1="{rx1:.3f}" y1="{ry:.3f}" '
        f'x2="{rx2:.3f}" y2="{ry:.3f}" stroke="#000000" stroke-width="0.45"/>'
    )
    for tick_mm in range(0, 55, 10):
        tx = _svg_x(float(tick_mm))
        lines.append(
            f'    <line x1="{tx:.3f}" y1="{ry - 1.8:.3f}" x2="{tx:.3f}" y2="{ry + 1.8:.3f}" '
            f'stroke="#000000" stroke-width="0.35"/>'
        )
    lines.append(
        f'    <text x="{rx1:.3f}" y="{ry - 2.6:.3f}" font-family="monospace" '
        f'font-size="2.5" fill="#000000">50.0 mm CALIBRATION RULER (1:1)</text>'
    )
    lines.append("  </g>")

    # 1. Electrical traces in Top View coordinates
    lines.append('  <g id="copper-traces" data-coords="top-view">')
    for tr in board.traces:
        x1, y1 = _svg_x(tr.x1_mm), _svg_y(tr.y1_mm, board.height_mm)
        x2, y2 = _svg_x(tr.x2_mm), _svg_y(tr.y2_mm, board.height_mm)
        lines.append(
            f'    <line x1="{x1:.3f}" y1="{y1:.3f}" x2="{x2:.3f}" y2="{y2:.3f}" '
            f'stroke="#000000" stroke-width="{tr.width_mm:.3f}" stroke-linecap="round" '
            f'data-net="{tr.net}"/>'
        )
    lines.append("  </g>")

    # 2. Artistic copper banner horizontally mirrored for toner transfer onto B.Cu
    lines.append('  <g id="artistic-banner" data-mirrored="true">')
    for bp in board.banner_primitives:
        x1_m, y1_m, x2_m, y2_m, _ = bp.to_capsule(mirrored=True, center_x_mm=board.banner_center_x_mm)
        sx1, sy1 = _svg_x(x1_m), _svg_y(y1_m, board.height_mm)
        sx2, sy2 = _svg_x(x2_m), _svg_y(y2_m, board.height_mm)
        lines.append(
            f'    <line x1="{sx1:.3f}" y1="{sy1:.3f}" x2="{sx2:.3f}" y2="{sy2:.3f}" '
            f'stroke="#000000" stroke-width="{bp.width_mm:.3f}" stroke-linecap="round" '
            f'data-label="{bp.label}" data-raw-x1="{x1_m:.3f}" data-raw-x2="{x2_m:.3f}"/>'
        )
    lines.append("  </g>")

    # 3. Copper pads (black outer pad + white central drill guide)
    lines.append('  <g id="copper-pads" data-coords="top-view">')
    for pad in board.pads:
        cx, cy = _svg_x(pad.x_mm), _svg_y(pad.y_mm, board.height_mm)
        x1, y1, x2, y2, _ = pad.to_capsule()
        sx1, sy1 = _svg_x(x1), _svg_y(y1, board.height_mm)
        sx2, sy2 = _svg_x(x2), _svg_y(y2, board.height_mm)
        if pad.shape == "oblong":
            lines.append(
                f'    <line id="pad-{pad.name}" x1="{sx1:.3f}" y1="{sy1:.3f}" '
                f'x2="{sx2:.3f}" y2="{sy2:.3f}" stroke="#000000" '
                f'stroke-width="{pad.minor_mm:.3f}" stroke-linecap="round" '
                f'data-pad="{pad.name}" data-net="{pad.net}" '
                f'data-x-mm="{pad.x_mm:.3f}" data-y-mm="{pad.y_mm:.3f}"/>'
            )
        else:
            lines.append(
                f'    <circle id="pad-{pad.name}" cx="{cx:.3f}" cy="{cy:.3f}" '
                f'r="{pad.major_mm / 2.0:.3f}" fill="#000000" '
                f'data-pad="{pad.name}" data-net="{pad.net}" '
                f'data-x-mm="{pad.x_mm:.3f}" data-y-mm="{pad.y_mm:.3f}"/>'
            )
        # White central drill pilot point
        lines.append(
            f'    <circle cx="{cx:.3f}" cy="{cy:.3f}" r="{pad.drill_mm / 2.0:.3f}" '
            f'fill="#FFFFFF" data-drill-guide="{pad.name}"/>'
        )
    lines.append("  </g>")

    # 4. Corner M3 mounting hole drill guides
    lines.append('  <g id="mounting-holes">')
    for mh in board.mounting_holes:
        cx, cy = _svg_x(mh.x_mm), _svg_y(mh.y_mm, board.height_mm)
        lines.append(
            f'    <circle id="{mh.name}" cx="{cx:.3f}" cy="{cy:.3f}" '
            f'r="{mh.drill_mm / 2.0:.3f}" fill="none" stroke="#000000" stroke-width="0.25"/>'
        )
        lines.append(
            f'    <circle cx="{cx:.3f}" cy="{cy:.3f}" r="0.45" fill="#000000"/>'
        )
    lines.append("  </g>")

    lines.append("</svg>")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def _draw_bottom_instance(ax: plt.Axes, board: PcbBoard, pl: BoardPlacement) -> None:
    """Draw one 1:1 B.Cu toner-transfer board copy at placement `pl`."""
    pt_per_mm = 72.0 / 25.4
    bw, bh = board.width_mm, board.height_mm

    # Board cut outline
    ax.add_patch(
        mpatches.Rectangle(
            (pl.ox_mm, pl.oy_mm),
            pl.width_mm,
            pl.height_mm,
            fill=False,
            edgecolor="black",
            linewidth=0.25 * pt_per_mm,
        )
    )

    # Traces (Top View coords, rigidly rotated if rotated_90=True)
    for tr in board.traces:
        tx1, ty1 = _transform_point(tr.x1_mm, tr.y1_mm, bw, bh, pl)
        tx2, ty2 = _transform_point(tr.x2_mm, tr.y2_mm, bw, bh, pl)
        ax.plot(
            [tx1, tx2],
            [ty1, ty2],
            color="black",
            linewidth=tr.width_mm * pt_per_mm,
            solid_capstyle="round",
        )

    # Artistic banner (horizontally mirrored for B.Cu toner transfer, then rigidly placed)
    for bp in board.banner_primitives:
        x1_m, y1_m, x2_m, y2_m, _ = bp.to_capsule(mirrored=True, center_x_mm=board.banner_center_x_mm)
        bx1, by1 = _transform_point(x1_m, y1_m, bw, bh, pl)
        bx2, by2 = _transform_point(x2_m, y2_m, bw, bh, pl)
        ax.plot(
            [bx1, bx2],
            [by1, by2],
            color="black",
            linewidth=bp.width_mm * pt_per_mm,
            solid_capstyle="round",
        )

    # Pads + white central drill guide holes
    for pad in board.pads:
        cx, cy = _transform_point(pad.x_mm, pad.y_mm, bw, bh, pl)
        if pad.shape == "oblong":
            x1, y1, x2, y2, _ = pad.to_capsule()
            px1, py1 = _transform_point(x1, y1, bw, bh, pl)
            px2, py2 = _transform_point(x2, y2, bw, bh, pl)
            ax.plot(
                [px1, px2],
                [py1, py2],
                color="black",
                linewidth=pad.minor_mm * pt_per_mm,
                solid_capstyle="round",
            )
        else:
            ax.add_patch(
                mpatches.Circle(
                    (cx, cy),
                    radius=pad.major_mm / 2.0,
                    facecolor="black",
                    edgecolor="none",
                )
            )
        ax.add_patch(
            mpatches.Circle(
                (cx, cy),
                radius=pad.drill_mm / 2.0,
                facecolor="white",
                edgecolor="none",
                zorder=5,
            )
        )

    # M3 mounting holes
    for mh in board.mounting_holes:
        mx, my = _transform_point(mh.x_mm, mh.y_mm, bw, bh, pl)
        ax.add_patch(
            mpatches.Circle(
                (mx, my),
                radius=mh.drill_mm / 2.0,
                fill=False,
                edgecolor="black",
                linewidth=0.25 * pt_per_mm,
            )
        )


def export_bottom_toner_pdf(board: PcbBoard, out_path: Path) -> Path:
    """Export US Letter 1:1 multi-copy panel PDF for B.Cu toner transfer."""
    layout = compute_letter_layout(board)
    fig = plt.figure(figsize=(LETTER_W_MM / 25.4, LETTER_H_MM / 25.4), facecolor="white")
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0], frameon=False)
    ax.set_xlim(0.0, LETTER_W_MM)
    ax.set_ylim(0.0, LETTER_H_MM)
    ax.set_aspect("equal")
    ax.axis("off")

    _draw_letter_chrome(ax, board, layout, subtitle="B.Cu TONER TRANSFER")
    for pl in layout.placements:
        _draw_bottom_instance(ax, board, pl)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, format="pdf")
    plt.close(fig)
    return out_path


def export_top_assembly_svg(board: PcbBoard, out_path: Path) -> Path:
    """Export 1:1 Top Assembly view (unmirrored) with pin labels, USB side, ADD-GND note, and external switch diagram."""
    lines: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{PAGE_W_MM:.2f}mm" height="{PAGE_H_MM:.2f}mm" '
            f'viewBox="0 0 {PAGE_W_MM:.2f} {PAGE_H_MM:.2f}" '
            f'data-layer="TopAssembly" data-scale="1:1" '
            f'data-board-width-mm="{board.width_mm:.2f}" '
            f'data-board-height-mm="{board.height_mm:.2f}" '
            f'data-banner-mirrored="false">'
        ),
        f'  <rect x="0" y="0" width="{PAGE_W_MM:.2f}" height="{PAGE_H_MM:.2f}" fill="#FFFFFF"/>',
    ]

    bx = _svg_x(0.0)
    by = _svg_y(board.height_mm, board.height_mm)
    lines.append(
        f'  <rect id="board-outline" x="{bx:.3f}" y="{by:.3f}" '
        f'width="{board.width_mm:.3f}" height="{board.height_mm:.3f}" '
        f'fill="none" stroke="#111111" stroke-width="0.35"/>'
    )

    # Faint X-ray copper traces
    lines.append('  <g id="xray-traces" opacity="0.25">')
    for tr in board.traces:
        x1, y1 = _svg_x(tr.x1_mm), _svg_y(tr.y1_mm, board.height_mm)
        x2, y2 = _svg_x(tr.x2_mm), _svg_y(tr.y2_mm, board.height_mm)
        lines.append(
            f'    <line x1="{x1:.3f}" y1="{y1:.3f}" x2="{x2:.3f}" y2="{y2:.3f}" '
            f'stroke="#666666" stroke-width="{tr.width_mm:.3f}" stroke-linecap="round"/>'
        )
    lines.append("  </g>")

    # Artistic banner UNMIRRORED in Top View
    lines.append('  <g id="artistic-banner" data-mirrored="false">')
    for bp in board.banner_primitives:
        x1_u, y1_u, x2_u, y2_u, _ = bp.to_capsule(mirrored=False, center_x_mm=board.banner_center_x_mm)
        sx1, sy1 = _svg_x(x1_u), _svg_y(y1_u, board.height_mm)
        sx2, sy2 = _svg_x(x2_u), _svg_y(y2_u, board.height_mm)
        lines.append(
            f'    <line x1="{sx1:.3f}" y1="{sy1:.3f}" x2="{sx2:.3f}" y2="{sy2:.3f}" '
            f'stroke="#222222" stroke-width="{bp.width_mm:.3f}" stroke-linecap="round" '
            f'data-label="{bp.label}" data-raw-x1="{x1_u:.3f}" data-raw-x2="{x2_u:.3f}"/>'
        )
    lines.append("  </g>")

    # ESP32 DevKit V1 silhouette + USB indicator at bottom edge
    esp_x = _svg_x(31.5)
    esp_y = _svg_y(51.5, board.height_mm)
    lines.append(
        f'  <rect id="esp32-outline" x="{esp_x:.3f}" y="{esp_y:.3f}" width="29.000" height="48.500" '
        f'fill="none" stroke="#003399" stroke-width="0.35" stroke-dasharray="1.2,0.8"/>'
    )
    usb_x = _svg_x(42.0)
    usb_y = _svg_y(5.5, board.height_mm)
    lines.append(
        f'  <rect id="esp32-usb" x="{usb_x:.3f}" y="{usb_y:.3f}" width="8.000" height="5.500" '
        f'fill="#E6EEF8" stroke="#003399" stroke-width="0.35"/>'
    )

    # Pads
    lines.append('  <g id="assembly-pads">')
    for pad in board.pads:
        cx, cy = _svg_x(pad.x_mm), _svg_y(pad.y_mm, board.height_mm)
        lines.append(
            f'    <circle cx="{cx:.3f}" cy="{cy:.3f}" r="{pad.drill_mm / 2.0 + 0.45:.3f}" '
            f'fill="none" stroke="#000000" stroke-width="0.25"/>'
        )
    lines.append("  </g>")

    # Non-overlapping labels driven by get_top_assembly_label_boxes(board)
    ha_to_anchor = {"left": "start", "center": "middle", "right": "end"}
    lines.append('  <g id="assembly-labels">')
    for lb in get_top_assembly_label_boxes(board):
        font_mm = lb.fontsize_pt * (25.4 / 72.0)
        if lb.callout_target is not None:
            tx, ty = lb.callout_target
            box_cx = (lb.x_min_mm + lb.x_max_mm) / 2.0
            box_cy = lb.y_max_mm if ty > lb.y_max_mm else lb.y_min_mm
            lines.append(
                f'    <line x1="{_svg_x(box_cx):.3f}" y1="{_svg_y(box_cy, board.height_mm):.3f}" '
                f'x2="{_svg_x(tx):.3f}" y2="{_svg_y(ty, board.height_mm):.3f}" '
                f'stroke="#555555" stroke-width="0.18"/>'
            )
        if lb.draw_bg:
            bx_bg = _svg_x(lb.x_min_mm)
            by_bg = _svg_y(lb.y_max_mm, board.height_mm)
            lines.append(
                f'    <rect x="{bx_bg:.3f}" y="{by_bg:.3f}" '
                f'width="{lb.x_max_mm - lb.x_min_mm:.3f}" height="{lb.y_max_mm - lb.y_min_mm:.3f}" '
                f'fill="#FFFFFF" fill-opacity="0.92" stroke="none"/>'
            )
        text_lines = lb.text.split("\n")
        ax_svg = _svg_x(lb.anchor_x_mm)
        y_center_mm = (lb.y_min_mm + lb.y_max_mm) / 2.0
        line_step_mm = font_mm * 1.15
        first_y_mm = y_center_mm + ((len(text_lines) - 1) / 2.0) * line_step_mm
        anchor_attr = ha_to_anchor.get(lb.ha, "start")
        for idx, sub in enumerate(text_lines):
            escaped = sub.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            sy = _svg_y(first_y_mm - idx * line_step_mm, board.height_mm)
            lines.append(
                f'    <text x="{ax_svg:.3f}" y="{sy:.3f}" text-anchor="{anchor_attr}" '
                f'dominant-baseline="central" font-family="monospace" '
                f'font-size="{font_mm:.3f}" fill="{lb.color}">{escaped}</text>'
            )
    lines.append("  </g>")

    lines.append("</svg>")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def _draw_top_instance(ax: plt.Axes, board: PcbBoard, pl: BoardPlacement) -> None:
    """Draw one 1:1 Top Assembly (unmirrored) board copy at placement `pl`."""
    pt_per_mm = 72.0 / 25.4
    bw, bh = board.width_mm, board.height_mm
    rot_deg = 90.0 if pl.rotated_90 else 0.0

    ax.add_patch(
        mpatches.Rectangle(
            (pl.ox_mm, pl.oy_mm),
            pl.width_mm,
            pl.height_mm,
            fill=False,
            edgecolor="black",
            linewidth=0.35 * pt_per_mm,
        )
    )

    # Faint X-ray traces
    for tr in board.traces:
        tx1, ty1 = _transform_point(tr.x1_mm, tr.y1_mm, bw, bh, pl)
        tx2, ty2 = _transform_point(tr.x2_mm, tr.y2_mm, bw, bh, pl)
        ax.plot(
            [tx1, tx2],
            [ty1, ty2],
            color="#CCCCCC",
            linewidth=tr.width_mm * pt_per_mm,
            solid_capstyle="round",
        )

    # Unmirrored artistic banner
    for bp in board.banner_primitives:
        x1_u, y1_u, x2_u, y2_u, _ = bp.to_capsule(mirrored=False, center_x_mm=board.banner_center_x_mm)
        bx1, by1 = _transform_point(x1_u, y1_u, bw, bh, pl)
        bx2, by2 = _transform_point(x2_u, y2_u, bw, bh, pl)
        ax.plot(
            [bx1, bx2],
            [by1, by2],
            color="#222222",
            linewidth=bp.width_mm * pt_per_mm,
            solid_capstyle="round",
        )

    # ESP32 outline
    if pl.rotated_90:
        ex, ey = _transform_point(31.5, 51.5, bw, bh, pl)
        ew, eh = 48.5, 29.0
    else:
        ex, ey = _transform_point(31.5, 3.0, bw, bh, pl)
        ew, eh = 29.0, 48.5
    ax.add_patch(
        mpatches.Rectangle(
            (ex, ey),
            ew,
            eh,
            fill=False,
            edgecolor="#003399",
            linestyle="--",
            linewidth=0.35 * pt_per_mm,
        )
    )

    # Pads
    for pad in board.pads:
        cx, cy = _transform_point(pad.x_mm, pad.y_mm, bw, bh, pl)
        ax.add_patch(
            mpatches.Circle(
                (cx, cy),
                radius=pad.drill_mm / 2.0 + 0.45,
                fill=False,
                edgecolor="black",
                linewidth=0.25 * pt_per_mm,
            )
        )

    # Non-overlapping labels driven by get_top_assembly_label_boxes(board)
    for lb in get_top_assembly_label_boxes(board):
        if lb.callout_target is not None:
            tx, ty = lb.callout_target
            box_cx = (lb.x_min_mm + lb.x_max_mm) / 2.0
            box_cy = lb.y_max_mm if ty > lb.y_max_mm else lb.y_min_mm
            cx1, cy1 = _transform_point(box_cx, box_cy, bw, bh, pl)
            cx2, cy2 = _transform_point(tx, ty, bw, bh, pl)
            ax.plot([cx1, cx2], [cy1, cy2], color="#555555", linewidth=0.18 * pt_per_mm, zorder=6)

        lx, ly = _transform_point(lb.anchor_x_mm, lb.anchor_y_mm, bw, bh, pl)
        bbox_kw = {"facecolor": "white", "edgecolor": "none", "alpha": 0.9, "pad": 0.4} if lb.draw_bg else None
        ax.text(
            lx,
            ly,
            lb.text,
            fontsize=lb.fontsize_pt,
            ha=lb.ha,
            va=lb.va,
            family="monospace",
            color=lb.color,
            rotation=rot_deg,
            bbox=bbox_kw,
            zorder=7,
        )


def export_top_assembly_pdf(board: PcbBoard, out_path: Path) -> Path:
    """Export US Letter 1:1 multi-copy Top Assembly view PDF (unmirrored)."""
    layout = compute_letter_layout(board)
    fig = plt.figure(figsize=(LETTER_W_MM / 25.4, LETTER_H_MM / 25.4), facecolor="white")
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0], frameon=False)
    ax.set_xlim(0.0, LETTER_W_MM)
    ax.set_ylim(0.0, LETTER_H_MM)
    ax.set_aspect("equal")
    ax.axis("off")

    _draw_letter_chrome(ax, board, layout, subtitle="TOP ASSEMBLY (VISTA SUPERIOR)")
    for pl in layout.placements:
        _draw_top_instance(ax, board, pl)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, format="pdf")
    plt.close(fig)
    return out_path


def export_drill_map_svg(board: PcbBoard, out_path: Path) -> Path:
    """Export 1:1 drill map SVG cataloging all hole coordinates and diameters."""
    lines: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{PAGE_W_MM:.2f}mm" height="{PAGE_H_MM:.2f}mm" '
            f'viewBox="0 0 {PAGE_W_MM:.2f} {PAGE_H_MM:.2f}" '
            f'data-layer="DrillMap" data-scale="1:1">'
        ),
        f'  <rect x="0" y="0" width="{PAGE_W_MM:.2f}" height="{PAGE_H_MM:.2f}" fill="#FFFFFF"/>',
    ]

    bx = _svg_x(0.0)
    by = _svg_y(board.height_mm, board.height_mm)
    lines.append(
        f'  <rect id="board-outline" x="{bx:.3f}" y="{by:.3f}" '
        f'width="{board.width_mm:.3f}" height="{board.height_mm:.3f}" '
        f'fill="none" stroke="#000000" stroke-width="0.30"/>'
    )

    lines.append('  <g id="drill-holes">')
    for pad in board.pads:
        cx, cy = _svg_x(pad.x_mm), _svg_y(pad.y_mm, board.height_mm)
        r = pad.drill_mm / 2.0
        lines.append(
            f'    <circle cx="{cx:.3f}" cy="{cy:.3f}" r="{r:.3f}" '
            f'fill="none" stroke="#000000" stroke-width="0.22" '
            f'data-hole="{pad.name}" data-drill-mm="{pad.drill_mm:.2f}"/>'
        )
        lines.append(
            f'    <line x1="{cx - r:.3f}" y1="{cy:.3f}" x2="{cx + r:.3f}" y2="{cy:.3f}" '
            f'stroke="#000000" stroke-width="0.15"/>'
        )
        lines.append(
            f'    <line x1="{cx:.3f}" y1="{cy - r:.3f}" x2="{cx:.3f}" y2="{cy + r:.3f}" '
            f'stroke="#000000" stroke-width="0.15"/>'
        )

    for mh in board.mounting_holes:
        cx, cy = _svg_x(mh.x_mm), _svg_y(mh.y_mm, board.height_mm)
        r = mh.drill_mm / 2.0
        lines.append(
            f'    <circle cx="{cx:.3f}" cy="{cy:.3f}" r="{r:.3f}" '
            f'fill="none" stroke="#000000" stroke-width="0.30" '
            f'data-hole="{mh.name}" data-drill-mm="{mh.drill_mm:.2f}"/>'
        )
    lines.append("  </g>")

    lines.append(
        f'  <text x="{_svg_x(0.0):.3f}" y="{round(PAGE_H_MM - 6.0, 3):.3f}" '
        f'font-family="monospace" font-size="2.4" fill="#000000">'
        f'DRILL LEGEND: Headers=0.9mm (39x) | ESC Sig=1.0mm (4x) | Power=1.6mm (6x) | M3=3.2mm (4x)</text>'
    )
    lines.append("</svg>")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def render_all(board: PcbBoard | None = None, output_dir: Path | None = None) -> dict[str, Path]:
    """Generate all 1:1 manufacturing files into hardware/output/."""
    if board is None:
        board = build_default_board()
    if output_dir is None:
        output_dir = Path(__file__).resolve().parent / "output"

    output_dir.mkdir(parents=True, exist_ok=True)
    return {
        "bottom_toner_svg": export_bottom_toner_svg(board, output_dir / "pcb_bottom_toner_1to1.svg"),
        "bottom_toner_pdf": export_bottom_toner_pdf(board, output_dir / "pcb_bottom_toner_1to1.pdf"),
        "top_assembly_svg": export_top_assembly_svg(board, output_dir / "pcb_top_assembly_1to1.svg"),
        "top_assembly_pdf": export_top_assembly_pdf(board, output_dir / "pcb_top_assembly_1to1.pdf"),
        "drill_map_svg": export_drill_map_svg(board, output_dir / "pcb_drill_map.svg"),
    }


if __name__ == "__main__":
    render_all()
