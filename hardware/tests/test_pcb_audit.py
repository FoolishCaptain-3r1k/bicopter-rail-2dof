"""Independent PCB audit tests: firmware contract, 300+ DPI pixel flood-fill netlist, and transfer overlay."""

from __future__ import annotations

from pathlib import Path

from hardware.audit_independent import (
    extract_pixel_netlist,
    rasterize_bottom_copper,
    render_iron_transfer_audit,
    verify_firmware_pin_contract,
)
from hardware.pcb_spec import build_default_board


def test_firmware_pin_contract_against_pcb() -> None:
    """Verify firmware/include/config.h GPIOs match ESP32 30-pin and sensor headers 1:1."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    config_h = repo_root / "firmware" / "include" / "config.h"
    board = build_default_board()

    result = verify_firmware_pin_contract(config_h, board)
    assert result.passed, f"Firmware-to-PCB pin contract mismatch: {result.errors}"
    assert result.parsed_pins == {
        "I2C_SDA_PIN": 21,
        "I2C_SCL_PIN": 22,
        "TOF_XSHUT_PIN": 19,
        "ESC_LEFT_PIN": 25,
        "ESC_RIGHT_PIN": 26,
    }


def test_raster_pixel_netlist_zero_shorts_and_opens() -> None:
    """Verify electrical connectivity purely via 300 DPI pixel flood-fill on rendered toner copper."""
    board = build_default_board()
    toner_binary, pad_coords_px = rasterize_bottom_copper(board, dpi=300)
    report = extract_pixel_netlist(toner_binary, pad_coords_px, board=board)

    assert report.passed, (
        f"Pixel netlist audit failed: shorts={report.short_circuits}, "
        f"opens={report.open_circuits}, isolated={report.isolated_violations}, "
        f"banner={report.banner_violations}"
    )
    assert frozenset({"ESP32_VIN"}) in report.reconstructed_nets
    assert frozenset({"J_TOF_NC"}) in report.reconstructed_nets
    assert frozenset({"ESP32_D25", "ESC_L_SIG"}) in report.reconstructed_nets
    assert frozenset({"ESP32_D26", "ESC_R_SIG"}) in report.reconstructed_nets
    assert frozenset({"ESP32_D22", "J_TOF_SCL", "J_IMU_SCL"}) in report.reconstructed_nets
    assert frozenset({"ESP32_D21", "J_TOF_SDA", "J_IMU_SDA"}) in report.reconstructed_nets
    assert frozenset({"ESP32_D19", "J_TOF_XSHUT"}) in report.reconstructed_nets
    assert frozenset({"ESP32_3V3", "J_TOF_3V3", "J_IMU_3V3"}) in report.reconstructed_nets
    assert frozenset({"BAT_VBAT_IN", "ESC_L_VBAT", "ESC_R_VBAT"}) in report.reconstructed_nets


def test_render_iron_transfer_audit_png() -> None:
    """Verify generation of high-res audit_overlay_verify.png."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    out_png = repo_root / "hardware" / "output" / "audit_overlay_verify.png"
    board = build_default_board()

    rendered = render_iron_transfer_audit(out_png, board=board, dpi=300)
    assert rendered.exists()
    assert rendered.stat().st_size > 20_000
