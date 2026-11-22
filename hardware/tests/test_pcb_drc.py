"""Focused verification suite for the 1-layer PCB specification, DRC engine, and 1:1 exports."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from hardware.drc import run_drc
from hardware.pcb_spec import (
    ESP32_LEFT_PINS,
    ESP32_RIGHT_PINS,
    J_IMU_PINS,
    J_TOF_PINS,
    build_default_board,
)
from hardware.render import PAGE_H_MM, PAGE_W_MM, render_all


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

    # 2. Verify PDF MediaBox physical dimensions (±0.1 mm)
    for pdf_key in ("bottom_toner_pdf", "top_assembly_pdf"):
        raw_bytes = outputs[pdf_key].read_bytes()
        match = re.search(rb"/MediaBox\s*\[\s*0(?:\.0+)?\s+0(?:\.0+)?\s+([0-9.]+)\s+([0-9.]+)\s*\]", raw_bytes)
        assert match is not None, f"MediaBox not found in {pdf_key}"
        w_pt = float(match.group(1))
        h_pt = float(match.group(2))
        w_mm = w_pt * 25.4 / 72.0
        h_mm = h_pt * 25.4 / 72.0
        assert abs(w_mm - PAGE_W_MM) <= 0.1
        assert abs(h_mm - PAGE_H_MM) <= 0.1

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
