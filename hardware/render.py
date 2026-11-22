"""1:1 physical scale (mm) SVG and PDF exporter for B.Cu toner transfer, Top Assembly, and Drill Map."""

from __future__ import annotations

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


def export_bottom_toner_pdf(board: PcbBoard, out_path: Path) -> Path:
    """Export 1:1 physical scale PDF for B.Cu toner transfer."""
    fig = plt.figure(figsize=(PAGE_W_MM / 25.4, PAGE_H_MM / 25.4), facecolor="white")
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0], frameon=False)
    ax.set_xlim(0.0, PAGE_W_MM)
    ax.set_ylim(0.0, PAGE_H_MM)
    ax.set_aspect("equal")
    ax.axis("off")

    ox, oy = BOARD_OX_MM, BOARD_OY_MM

    # Board outline
    ax.add_patch(
        mpatches.Rectangle(
            (ox, oy),
            board.width_mm,
            board.height_mm,
            fill=False,
            edgecolor="black",
            linewidth=0.25 * 72.0 / 25.4,
        )
    )

    # 50.0 mm calibration ruler
    ry = 7.0
    ax.plot(
        [ox, ox + RULER_LEN_MM],
        [ry, ry],
        color="black",
        linewidth=0.45 * 72.0 / 25.4,
        solid_capstyle="butt",
    )
    for tick_mm in range(0, 55, 10):
        tx = ox + float(tick_mm)
        ax.plot([tx, tx], [ry - 1.5, ry + 1.5], color="black", linewidth=0.35 * 72.0 / 25.4)
    ax.text(ox, ry + 2.2, "50.0 mm CALIBRATION RULER (1:1)", fontsize=6.5, family="monospace", color="black")

    # Traces (exact width in points: mm * 72 / 25.4)
    for tr in board.traces:
        ax.plot(
            [ox + tr.x1_mm, ox + tr.x2_mm],
            [oy + tr.y1_mm, oy + tr.y2_mm],
            color="black",
            linewidth=tr.width_mm * 72.0 / 25.4,
            solid_capstyle="round",
        )

    # Artistic banner (horizontally mirrored for B.Cu toner transfer)
    for bp in board.banner_primitives:
        x1_m, y1_m, x2_m, y2_m, _ = bp.to_capsule(mirrored=True, center_x_mm=board.banner_center_x_mm)
        ax.plot(
            [ox + x1_m, ox + x2_m],
            [oy + y1_m, oy + y2_m],
            color="black",
            linewidth=bp.width_mm * 72.0 / 25.4,
            solid_capstyle="round",
        )

    # Pads + white drill guide holes
    for pad in board.pads:
        x1, y1, x2, y2, _ = pad.to_capsule()
        if pad.shape == "oblong":
            ax.plot(
                [ox + x1, ox + x2],
                [oy + y1, oy + y2],
                color="black",
                linewidth=pad.minor_mm * 72.0 / 25.4,
                solid_capstyle="round",
            )
        else:
            ax.add_patch(
                mpatches.Circle(
                    (ox + pad.x_mm, oy + pad.y_mm),
                    radius=pad.major_mm / 2.0,
                    facecolor="black",
                    edgecolor="none",
                )
            )
        ax.add_patch(
            mpatches.Circle(
                (ox + pad.x_mm, oy + pad.y_mm),
                radius=pad.drill_mm / 2.0,
                facecolor="white",
                edgecolor="none",
                zorder=5,
            )
        )

    # M3 mounting holes
    for mh in board.mounting_holes:
        ax.add_patch(
            mpatches.Circle(
                (ox + mh.x_mm, oy + mh.y_mm),
                radius=mh.drill_mm / 2.0,
                fill=False,
                edgecolor="black",
                linewidth=0.25 * 72.0 / 25.4,
            )
        )

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
    lines.append(
        f'  <text x="{_svg_x(46.0):.3f}" y="{_svg_y(2.5, board.height_mm):.3f}" '
        f'text-anchor="middle" font-family="monospace" font-size="2.1" fill="#003399">'
        f'ESP32 USB (BORDE INFERIOR)</text>'
    )

    # Pads and explicit pin labels
    lines.append('  <g id="assembly-pads-and-labels">')
    for pad in board.pads:
        cx, cy = _svg_x(pad.x_mm), _svg_y(pad.y_mm, board.height_mm)
        lines.append(
            f'    <circle cx="{cx:.3f}" cy="{cy:.3f}" r="{pad.drill_mm / 2.0 + 0.45:.3f}" '
            f'fill="none" stroke="#000000" stroke-width="0.25"/>'
        )
        lines.append(
            f'    <text x="{cx + 1.6:.3f}" y="{cy + 0.6:.3f}" font-family="monospace" '
            f'font-size="1.65" fill="#000000">{pad.name} ({pad.pin_label})</text>'
        )
    lines.append("  </g>")

    # Mandatory hardware notes: GY-BNO055 ADD->GND bridge and External Switch (30x20x20 mm)
    lines.append('  <g id="assembly-notes">')
    lines.append(
        f'    <text x="{_svg_x(58.0):.3f}" y="{_svg_y(53.0, board.height_mm):.3f}" '
        f'font-family="monospace" font-size="2.0" fill="#B00000">'
        f'NOTA GY-BNO055: PUENTE ADD-GND OBLIGATORIO (ADDR 0x28)</text>'
    )
    lines.append(
        f'    <text x="{_svg_x(2.0):.3f}" y="{_svg_y(53.0, board.height_mm):.3f}" '
        f'font-family="monospace" font-size="2.0" fill="#005500">'
        f'SWITCH EXTERNO (30x20x20 mm) EN SERIE CON +VBAT -&gt; BAT_VBAT_IN | VIN AISLADO</text>'
    )
    lines.append("  </g>")

    lines.append("</svg>")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def export_top_assembly_pdf(board: PcbBoard, out_path: Path) -> Path:
    """Export 1:1 Top Assembly view PDF (unmirrored)."""
    fig = plt.figure(figsize=(PAGE_W_MM / 25.4, PAGE_H_MM / 25.4), facecolor="white")
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0], frameon=False)
    ax.set_xlim(0.0, PAGE_W_MM)
    ax.set_ylim(0.0, PAGE_H_MM)
    ax.set_aspect("equal")
    ax.axis("off")

    ox, oy = BOARD_OX_MM, BOARD_OY_MM

    ax.add_patch(
        mpatches.Rectangle(
            (ox, oy),
            board.width_mm,
            board.height_mm,
            fill=False,
            edgecolor="black",
            linewidth=0.35 * 72.0 / 25.4,
        )
    )

    # Faint traces
    for tr in board.traces:
        ax.plot(
            [ox + tr.x1_mm, ox + tr.x2_mm],
            [oy + tr.y1_mm, oy + tr.y2_mm],
            color="#CCCCCC",
            linewidth=tr.width_mm * 72.0 / 25.4,
            solid_capstyle="round",
        )

    # Unmirrored artistic banner
    for bp in board.banner_primitives:
        x1_u, y1_u, x2_u, y2_u, _ = bp.to_capsule(mirrored=False, center_x_mm=board.banner_center_x_mm)
        ax.plot(
            [ox + x1_u, ox + x2_u],
            [oy + y1_u, oy + y2_m if False else oy + y2_u],
            color="#222222",
            linewidth=bp.width_mm * 72.0 / 25.4,
            solid_capstyle="round",
        )

    # ESP32 outline and USB side indicator
    ax.add_patch(
        mpatches.Rectangle(
            (ox + 31.5, oy + 3.0),
            29.0,
            48.5,
            fill=False,
            edgecolor="#003399",
            linestyle="--",
            linewidth=0.35 * 72.0 / 25.4,
        )
    )
    ax.text(ox + 46.0, oy + 1.0, "ESP32 USB (BORDE INFERIOR)", fontsize=5.5, ha="center", color="#003399")
    ax.text(
        ox + 46.0,
        oy + 53.0,
        "GY-BNO055: PUENTE ADD-GND (0x28) | SWITCH EXTERNO 30x20x20 mm EN SERIE +VBAT",
        fontsize=5.2,
        ha="center",
        color="#990000",
    )

    for pad in board.pads:
        ax.add_patch(
            mpatches.Circle(
                (ox + pad.x_mm, oy + pad.y_mm),
                radius=pad.drill_mm / 2.0 + 0.4,
                fill=False,
                edgecolor="black",
                linewidth=0.25 * 72.0 / 25.4,
            )
        )
        ax.text(ox + pad.x_mm + 1.2, oy + pad.y_mm - 0.3, pad.pin_label, fontsize=4.2, family="monospace")

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
