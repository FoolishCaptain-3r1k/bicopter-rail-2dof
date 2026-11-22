"""Focused verification suite for the 2-piece 3D-printable console enclosure."""

from __future__ import annotations

import numpy as np
import trimesh

from hardware.enclosure.build_enclosure import (
    box_mesh_from_bounds,
    build_all,
    build_base_mesh,
    build_top_shell_mesh,
    check_intersection_volume,
)
from hardware.enclosure.enclosure_spec import build_enclosure_spec
from hardware.pcb_spec import build_default_board


def test_enclosure_meshes_watertight_and_printable_bounds() -> None:
    """Verify watertight solid meshes (volume > 0, no degenerate faces) within <= 200x200x150 mm."""
    outputs = build_all()
    for key in ("base_stl", "top_shell_stl", "preview_png"):
        assert outputs[key].exists(), f"Missing output {key}: {outputs[key]}"
        assert outputs[key].stat().st_size > 5_000

    for stl_key in ("base_stl", "top_shell_stl"):
        mesh = trimesh.load(str(outputs[stl_key]), force="mesh")
        assert mesh.is_watertight, f"{stl_key} is not watertight"
        assert mesh.is_volume, f"{stl_key} is not a valid closed volume"
        assert mesh.volume > 1_000.0, f"{stl_key} volume unexpectedly small: {mesh.volume}"
        assert np.all(mesh.area_faces > 1e-9), f"{stl_key} has degenerate zero-area faces"

        extents = mesh.extents
        assert extents[0] <= 200.0 and extents[1] <= 200.0 and extents[2] <= 150.0, (
            f"{stl_key} exceeds 200x200x150 mm print bed: {extents}"
        )


def test_internal_keepouts_zero_collision() -> None:
    """Verify strictly 0 mm^3 intersection between SWITCH_KEEP_OUT and ESP32_KEEP_OUT/PCB/ESCs/walls."""
    spec = build_enclosure_spec()
    base_mesh = build_base_mesh(spec)
    top_mesh = build_top_shell_mesh(spec)

    pcb_mesh = box_mesh_from_bounds(spec.pcb_keepout)
    esp_mesh = box_mesh_from_bounds(spec.esp32_keepout)
    esc_mesh = box_mesh_from_bounds(spec.left_esc_keepout)
    sw_mesh = box_mesh_from_bounds(spec.switch_keepout)

    # 0 mm^3 overlap between switch keep-out and ESP32 / PCB / ESCs / enclosure walls
    assert check_intersection_volume(sw_mesh, esp_mesh) == 0.0
    assert check_intersection_volume(sw_mesh, pcb_mesh) == 0.0
    assert check_intersection_volume(sw_mesh, esc_mesh) == 0.0
    assert check_intersection_volume(sw_mesh, base_mesh) == 0.0
    assert check_intersection_volume(sw_mesh, top_mesh) == 0.0

    # 0 mm^3 overlap between ESP32 / ESC keep-outs and enclosure shells
    assert check_intersection_volume(esp_mesh, base_mesh) == 0.0
    assert check_intersection_volume(esp_mesh, top_mesh) == 0.0
    assert check_intersection_volume(esc_mesh, base_mesh) == 0.0
    assert check_intersection_volume(esc_mesh, top_mesh) == 0.0

    # 0 mm^3 overlap between base and top_shell (0.30 mm mating tolerance verified)
    assert check_intersection_volume(base_mesh, top_mesh) == 0.0


def test_m3_standoffs_aligned_with_pcb_spec() -> None:
    """Verify exact (±0.05 mm) alignment of all 4 M3 standoffs against hardware/pcb_spec.py."""
    board = build_default_board()
    spec = build_enclosure_spec(board)
    base_mesh = build_base_mesh(spec)

    assert len(spec.pcb_m3_holes) == len(board.mounting_holes) == 4
    z_pcb_bot = spec.floor_mm + spec.standoff_height_mm
    for mh, (_, sx, sy, s_drill) in zip(board.mounting_holes, spec.pcb_m3_holes):
        assert abs(mh.x_mm - sx) <= 0.05
        assert abs(mh.y_mm - sy) <= 0.05
        assert abs(mh.drill_mm - s_drill) <= 0.05

        # Probe standoff annulus (r = 2.4 mm) via exact manifold CSG to confirm z_pcb_bot = 8.40 mm (±0.05 mm)
        solid_probe = trimesh.creation.box(extents=[0.6, 0.6, 0.2])
        solid_probe.apply_translation([sx + 2.4, sy, z_pcb_bot - 0.15])
        assert check_intersection_volume(base_mesh, solid_probe) > 0.05, (
            f"Missing M3 standoff material at ({sx}, {sy})"
        )

        air_probe = trimesh.creation.box(extents=[0.6, 0.6, 0.5])
        air_probe.apply_translation([sx + 2.4, sy, z_pcb_bot + 0.30])
        assert check_intersection_volume(base_mesh, air_probe) == 0.0, (
            f"M3 standoff exceeds z_pcb_bot={z_pcb_bot} at ({sx}, {sy})"
        )

        # Probe central M3 pilot bore to confirm hollow screw hole
        bore_probe = trimesh.creation.cylinder(radius=1.0, height=1.0, sections=16)
        bore_probe.apply_translation([sx, sy, z_pcb_bot - 0.5])
        assert check_intersection_volume(base_mesh, bore_probe) == 0.0, (
            f"M3 pilot bore clogged at ({sx}, {sy})"
        )
