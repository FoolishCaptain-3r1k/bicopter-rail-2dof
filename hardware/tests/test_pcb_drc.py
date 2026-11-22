"""Focused verification suite for the 1-layer PCB specification, DRC engine, and 1:1 exports."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

from hardware.drc import run_drc
from hardware.pcb_spec import (
    ESP32_LEFT_PINS,
    ESP32_RIGHT_PINS,
    J_IMU_PINS,
    J_TOF_PINS,
    build_default_board,
)
from hardware.render import (
    LETTER_H_MM,
    LETTER_H_PT,
    LETTER_W_MM,
    LETTER_W_PT,
    PAGE_H_MM,
    PAGE_W_MM,
    _transform_point,
    compute_letter_layout,
    compute_letter_tiling,
    render_all,
)


def test_drc_zero_errors_and_clearances() -> None:
    """Verify 0 DRC violations and all minimum copper clearances and widths."""
    board = build_default_board()
    report = run_drc(board)

    assert report.passed, f"DRC failed with errors: {report.errors}"
    assert len(report.errors) == 0
    assert report.min_net_clearance_mm >= 0.70
    assert report.min_banner_clearance_mm >= 1.50
    assert report.min_signal_width_mm >= 1.00
    assert report.min_power_width_mm >= 4.00
    assert report.min_banner_stroke_mm >= 0.50


def test_net_connectivity_and_vin_isolation() -> None:
    """Verify 100% single-component connectivity per net and strict ESP32_VIN isolation."""
    board = build_default_board()
    report = run_drc(board)

    expected_nets = {
        "+VBAT_SW",
        "GND",
        "3V3",
        "I2C_SCL",
        "I2C_SDA",
        "TOF_XSHUT",
        "ESC_L_SIG",
        "ESC_R_SIG",
    }
    assert set(report.connected_nets.keys()) == expected_nets
    for net_name, is_connected in report.connected_nets.items():
        assert is_connected, f"Net {net_name} is not 100% connected"

    assert report.vin_isolated is True
    vin_pad = board.get_pad("ESP32_VIN")
    assert vin_pad.net == "ESP32_VIN"
    assert all(tr.net != "ESP32_VIN" for tr in board.traces)


def test_esp32_and_headers_geometry() -> None:
    """Verify exact 25.40 mm ESP32 row spacing, pinout ordering, and board size <= 94x90 mm."""
    board = build_default_board()
    report = run_drc(board)

    assert board.width_mm <= 94.0
    assert board.height_mm <= 90.0
    assert board.jumpers_count == 0
    assert board.passive_components_count == 0
    assert abs(report.esp32_row_pitch_mm - 25.40) < 1e-4

    left_pads = [p for p in board.pads if p.component == "ESP32" and p.x_mm < 46.0]
    right_pads = [p for p in board.pads if p.component == "ESP32" and p.x_mm > 46.0]
    assert [p.pin_label for p in left_pads] == list(ESP32_LEFT_PINS)
    assert [p.pin_label for p in right_pads] == list(ESP32_RIGHT_PINS)

    tof_pads = [p for p in board.pads if p.component == "J_TOF"]
    imu_pads = [p for p in board.pads if p.component == "J_IMU"]
    assert [p.pin_label for p in tof_pads] == list(J_TOF_PINS)
    assert [p.pin_label for p in imu_pads] == list(J_IMU_PINS)


def test_1to1_exports_and_mirroring_invariant() -> None:
    """Verify 1:1 physical scale (±0.1 mm) in PDF/SVG and B.Cu mirroring invariant."""
    board = build_default_board()
    outputs = render_all(board)

    for key, path in outputs.items():
        assert path.exists(), f"Missing output file for {key}: {path}"
        assert path.stat().st_size > 500, f"Output file {path} is unexpectedly empty"

    readme_path = Path(__file__).resolve().parent.parent / "README.md"
    assert readme_path.exists()

    # 1. Verify SVG physical dimensions and 50.0 mm calibration ruler (±0.1 mm)
    toner_tree = ET.parse(outputs["bottom_toner_svg"])
    toner_root = toner_tree.getroot()
    assert toner_root.attrib["width"] == f"{PAGE_W_MM:.2f}mm"
    assert toner_root.attrib["height"] == f"{PAGE_H_MM:.2f}mm"

    ns = {"svg": "http://www.w3.org/2000/svg"}
    outline = toner_root.find(".//svg:rect[@id='board-outline']", ns)
    assert outline is not None
    assert abs(float(outline.attrib["width"]) - board.width_mm) <= 0.1
    assert abs(float(outline.attrib["height"]) - board.height_mm) <= 0.1

    ruler = toner_root.find(".//svg:line[@id='calibration-ruler-50mm']", ns)
    assert ruler is not None
    ruler_len = abs(float(ruler.attrib["x2"]) - float(ruler.attrib["x1"]))
    assert abs(ruler_len - 50.0) <= 0.1

    # 2. Verify PDF MediaBox exact US Letter dimensions (612 x 792 pt ± 0.5 pt)
    for pdf_key in ("bottom_toner_pdf", "top_assembly_pdf"):
        raw_bytes = outputs[pdf_key].read_bytes()
        match = re.search(rb"/MediaBox\s*\[\s*0(?:\.0+)?\s+0(?:\.0+)?\s+([0-9.]+)\s+([0-9.]+)\s*\]", raw_bytes)
        assert match is not None, f"MediaBox not found in {pdf_key}"
        w_pt = float(match.group(1))
        h_pt = float(match.group(2))
        assert abs(w_pt - LETTER_W_PT) <= 0.5
        assert abs(h_pt - LETTER_H_PT) <= 0.5
        w_mm = w_pt * 25.4 / 72.0
        h_mm = h_pt * 25.4 / 72.0
        assert abs(w_mm - LETTER_W_MM) <= 0.1
        assert abs(h_mm - LETTER_H_MM) <= 0.1

    # 3. Verify B.Cu toner transfer mirroring invariant:
    #    - Electrical pads remain in Top View coordinates.
    #    - Artistic banner (Anáhuac México + 4 names) is horizontally mirrored in toner SVG vs top assembly SVG.
    top_tree = ET.parse(outputs["top_assembly_svg"])
    top_root = top_tree.getroot()

    toner_banner = toner_root.find(".//svg:g[@id='artistic-banner']", ns)
    top_banner = top_root.find(".//svg:g[@id='artistic-banner']", ns)
    assert toner_banner is not None and toner_banner.attrib.get("data-mirrored") == "true"
    assert top_banner is not None and top_banner.attrib.get("data-mirrored") == "false"

    toner_lines = toner_banner.findall("svg:line", ns)
    top_lines = top_banner.findall("svg:line", ns)
    assert len(toner_lines) == len(top_lines) and len(toner_lines) > 20

    labels_seen: set[str] = set()
    for t_line, u_line in zip(toner_lines, top_lines):
        labels_seen.add(t_line.attrib["data-label"])
        x1_toner = float(t_line.attrib["data-raw-x1"])
        x1_top = float(u_line.attrib["data-raw-x1"])
        assert abs((x1_toner + x1_top) - 2.0 * board.banner_center_x_mm) <= 1e-2

    assert labels_seen == {
        "Anáhuac México",
        "Leonardo Monter",
        "Renata Bello",
        "Adrian Ruiz",
        "Alonso Madrigal",
    }


def _extract_pdf_segments_mm(pdf_path: Path) -> list[tuple[float, float, float, float]]:
    """Decompress FlateDecode PDF streams and extract drawn 2-point line segments in mm."""
    raw = pdf_path.read_bytes()
    pt_to_mm = 25.4 / 72.0
    segments: list[tuple[float, float, float, float]] = []
    seg_re = re.compile(r"([0-9.\-]+)\s+([0-9.\-]+)\s+m\s+([0-9.\-]+)\s+([0-9.\-]+)\s+l")

    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", raw, flags=re.DOTALL):
        payload = match.group(1)
        try:
            text = zlib.decompress(payload).decode("latin1", errors="ignore")
        except zlib.error:
            text = payload.decode("latin1", errors="ignore")
        for m in seg_re.finditer(text):
            x1, y1, x2, y2 = (float(m.group(i)) * pt_to_mm for i in range(1, 5))
            segments.append((x1, y1, x2, y2))
    return segments


def test_letter_tiling_non_overlap_and_pdf_1to1_copies() -> None:
    """Verify US Letter multi-copy panelization, zero overlaps, 1:1 H/V rulers, and chirality."""
    board = build_default_board()
    cols, rows, rotated_90 = compute_letter_tiling(board.width_mm, board.height_mm)
    copies = cols * rows
    assert copies >= 2
    assert (cols, rows, rotated_90) == (2, 2, False)

    layout = compute_letter_layout(board)
    assert len(layout.placements) == copies

    # 1. Verify every board placement stays inside printable US Letter bounds
    max_y_allowed = LETTER_H_MM - layout.margin_mm - layout.header_mm
    for pl in layout.placements:
        assert pl.ox_mm >= layout.margin_mm - 1e-6
        assert pl.oy_mm >= layout.margin_mm - 1e-6
        assert pl.ox_mm + pl.width_mm <= LETTER_W_MM - layout.margin_mm + 1e-6
        assert pl.oy_mm + pl.height_mm <= max_y_allowed + 1e-6

    # 2. Verify pairwise zero overlap between copies and >= gap_mm clearance
    for i, a in enumerate(layout.placements):
        for j, b in enumerate(layout.placements):
            if i >= j:
                continue
            x_overlap = min(a.ox_mm + a.width_mm, b.ox_mm + b.width_mm) - max(a.ox_mm, b.ox_mm)
            y_overlap = min(a.oy_mm + a.height_mm, b.oy_mm + b.height_mm) - max(a.oy_mm, b.oy_mm)
            assert not (x_overlap > -1e-6 and y_overlap > -1e-6), f"Copies {i} and {j} overlap"

    # 3. Verify 50.0 mm H/V rulers stay inside margins and never overlap any copy
    hx1, hy1, hx2, hy2 = layout.h_ruler
    vx1, vy1, vx2, vy2 = layout.v_ruler
    assert abs((hx2 - hx1) - 50.0) <= 1e-6 and abs(hy2 - hy1) <= 1e-6
    assert abs((vy2 - vy1) - 50.0) <= 1e-6 and abs(vx2 - vx1) <= 1e-6
    assert hy1 > max_y_allowed  # Strictly inside reserved header band
    assert vx1 >= layout.margin_mm and vx1 <= LETTER_W_MM - layout.margin_mm
    for pl in layout.placements:
        in_x = pl.ox_mm <= vx1 <= pl.ox_mm + pl.width_mm
        in_y = not (vy2 < pl.oy_mm or vy1 > pl.oy_mm + pl.height_mm)
        assert not (in_x and in_y), "Vertical ruler overlaps board copy"

    # 4. Verify 1:1 physical scale (±0.1 mm) and mirrored banner presence in EVERY copy of bottom toner PDF
    outputs = render_all(board)
    segments = _extract_pdf_segments_mm(outputs["bottom_toner_pdf"])
    assert len(segments) > 100

    # Check both 50.0 mm rulers are present at exact physical length (±0.1 mm)
    has_h_ruler = any(
        abs(x1 - hx1) <= 0.1 and abs(y1 - hy1) <= 0.1 and abs(x2 - hx2) <= 0.1 and abs(y2 - hy2) <= 0.1
        for x1, y1, x2, y2 in segments
    )
    has_v_ruler = any(
        abs(x1 - vx1) <= 0.1 and abs(y1 - vy1) <= 0.1 and abs(x2 - vx2) <= 0.1 and abs(y2 - vy2) <= 0.1
        for x1, y1, x2, y2 in segments
    )
    assert has_h_ruler, "50.0 mm horizontal calibration ruler missing or off-scale in PDF"
    assert has_v_ruler, "50.0 mm vertical calibration ruler missing or off-scale in PDF"

    # Check each of the 4 copies contains the mirrored Anáhuac banner segments at exact 1:1 coordinates
    sample_bp = board.banner_primitives[5]  # Inner emblem stroke
    mx1, my1, mx2, my2, _ = sample_bp.to_capsule(mirrored=True, center_x_mm=board.banner_center_x_mm)
    ux1, _, ux2, _, _ = sample_bp.to_capsule(mirrored=False, center_x_mm=board.banner_center_x_mm)
    assert abs(mx1 - ux1) > 1.0  # Asymmetric stroke confirms mirroring is non-trivial

    for pl in layout.placements:
        ex1, ey1 = _transform_point(mx1, my1, board.width_mm, board.height_mm, pl)
        ex2, ey2 = _transform_point(mx2, my2, board.width_mm, board.height_mm, pl)
        found_mirrored = any(
            abs(x1 - ex1) <= 0.1 and abs(y1 - ey1) <= 0.1 and abs(x2 - ex2) <= 0.1 and abs(y2 - ey2) <= 0.1
            for x1, y1, x2, y2 in segments
        )
        assert found_mirrored, f"Mirrored banner stroke missing at 1:1 coords in copy ({pl.col},{pl.row})"

    # 5. Verify rotated_90 = True rigid SE(2) transform (det = +1) when rotation maximizes copies
    c_rot, r_rot, is_rot = compute_letter_tiling(210.0, 90.0)
    assert (c_rot, r_rot, is_rot) == (2, 1, True)

