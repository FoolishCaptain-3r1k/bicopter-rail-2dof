"""Parametric 3D CAD solid builder (trimesh + manifold3d) and multi-view renderer."""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import manifold3d as m3d
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from hardware.enclosure.enclosure_spec import BoundingBox3D, EnclosureSpec, build_enclosure_spec


def _box_mesh(
    x_min: float,
    y_min: float,
    z_min: float,
    x_max: float,
    y_max: float,
    z_max: float,
) -> trimesh.Trimesh:
    """Create an axis-aligned watertight box mesh from min/max bounds."""
    extents = [x_max - x_min, y_max - y_min, z_max - z_min]
    center = [(x_min + x_max) / 2.0, (y_min + y_max) / 2.0, (z_min + z_max) / 2.0]
    mesh = trimesh.creation.box(extents=extents)
    mesh.apply_translation(center)
    return mesh


def _extrude_yz_profile(
    yz_points: list[tuple[float, float]],
    x_min: float,
    x_max: float,
) -> trimesh.Trimesh:
    """Extrude a 2D polygon in the (Y, Z) plane along the X axis [x_min, x_max] via manifold3d."""
    cs = m3d.CrossSection([yz_points])
    man = cs.extrude(x_max - x_min)
    raw = man.to_mesh()
    mesh = trimesh.Trimesh(vertices=np.asarray(raw.vert_properties[:, :3]), faces=np.asarray(raw.tri_verts))
    # extrude extrudes (u, v) along +w; map (u->Y, v->Z, w->X)
    rot_to_yzx = np.array(
        [
            [0.0, 0.0, 1.0, x_min],
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    mesh.apply_transform(rot_to_yzx)
    return mesh


def _cylinder_z(cx: float, cy: float, z_min: float, z_max: float, radius: float, sections: int = 32) -> trimesh.Trimesh:
    """Create a Z-aligned watertight cylinder from z_min to z_max."""
    h = z_max - z_min
    cyl = trimesh.creation.cylinder(radius=radius, height=h, sections=sections)
    cyl.apply_translation([cx, cy, (z_min + z_max) / 2.0])
    return cyl


def _cylinder_y(cx: float, y_min: float, y_max: float, cz: float, radius: float, sections: int = 32) -> trimesh.Trimesh:
    """Create a Y-aligned watertight cylinder from y_min to y_max."""
    h = y_max - y_min
    cyl = trimesh.creation.cylinder(radius=radius, height=h, sections=sections)
    rot_x = trimesh.transformations.rotation_matrix(math.pi / 2.0, [1.0, 0.0, 0.0])
    cyl.apply_transform(rot_x)
    cyl.apply_translation([cx, (y_min + y_max) / 2.0, cz])
    return cyl


def _boolean_union(meshes: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    if len(meshes) == 1:
        return meshes[0]
    return trimesh.boolean.union(meshes, engine="manifold")


def _boolean_diff(base: trimesh.Trimesh, cutters: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    if not cutters:
        return base
    return trimesh.boolean.difference([base, _boolean_union(cutters)], engine="manifold")


def build_base_mesh(spec: EnclosureSpec) -> trimesh.Trimesh:
    """Build watertight enclosure_base mesh with M3 PCB standoffs, mating lip, bottom closure bosses & USB slot."""
    w = spec.wall_mm
    x0, x1 = spec.x_outer_min, spec.x_outer_max
    y0, y1 = spec.y_outer_min, spec.y_outer_max
    x_in0, x_in1 = x0 + w, x1 - w
    y_in0, y_in1 = y0 + w, y1 - w

    # Outer lower shell up to split_z
    outer_body = _box_mesh(x0, y0, 0.0, x1, y1, spec.split_z_mm)

    # Stepped mating lip rising lip_height_mm above split_z (1.0 mm wall recessed inside outer shell)
    lip_outer_inset = 1.40
    lip_ring = _box_mesh(
        x0 + lip_outer_inset,
        y0 + lip_outer_inset,
        spec.split_z_mm - 0.5,
        x1 - lip_outer_inset,
        y1 - lip_outer_inset,
        spec.split_z_mm + spec.lip_height_mm,
    )
    solid = _boolean_union([outer_body, lip_ring])

    # Hollow inner cavity above floor
    cavity = _box_mesh(x_in0, y_in0, spec.floor_mm, x_in1, y_in1, spec.split_z_mm + spec.lip_height_mm + 1.0)
    shell = _boolean_diff(solid, [cavity])

    # Add 4 internal M3 PCB standoffs + 4 corner closure bosses
    add_parts: list[trimesh.Trimesh] = [shell]
    cut_parts: list[trimesh.Trimesh] = []

    z_pcb_bot = spec.floor_mm + spec.standoff_height_mm
    for _, hx, hy, _ in spec.pcb_m3_holes:
        add_parts.append(_cylinder_z(hx, hy, spec.floor_mm - 0.2, z_pcb_bot, spec.standoff_od_mm / 2.0))
        cut_parts.append(_cylinder_z(hx, hy, spec.floor_mm + 0.8, z_pcb_bot + 0.5, spec.standoff_drill_mm / 2.0))

    for bx, by in spec.closure_bosses_xy:
        add_parts.append(_cylinder_z(bx, by, 0.0, spec.split_z_mm, 3.20))
        # M3 clearance bore + bottom countersink pocket
        cut_parts.append(_cylinder_z(bx, by, -0.5, spec.split_z_mm + 0.5, 1.70))
        cut_parts.append(_cylinder_z(bx, by, -0.5, 2.20, 3.00))

    # Front Micro-USB cutout through front wall & lip
    ux0, ux1 = spec.usb_slot_x_range
    uz0, uz1 = spec.usb_slot_z_range
    cut_parts.append(_box_mesh(ux0, y0 - 1.0, uz0, ux1, y_in0 + 1.0, uz1))

    result = _boolean_diff(_boolean_union(add_parts), cut_parts)
    return result


def build_top_shell_mesh(spec: EnclosureSpec) -> trimesh.Trimesh:
    """Build watertight sloped soldering-station top_shell mesh with switch deck, vents & 3 rear grommets."""
    w = spec.wall_mm
    x0, x1 = spec.x_outer_min, spec.x_outer_max
    y0, y1 = spec.y_outer_min, spec.y_outer_max
    x_in0, x_in1 = x0 + w, x1 - w
    y_in0, y_in1 = y0 + w, y1 - w

    # Outer sloped console profile (Y, Z) in CCW order
    outer_yz = [
        (y0, spec.split_z_mm),
        (y1, spec.split_z_mm),
        (y1, spec.top_deck_z_outer),
        (spec.slope_y_end, spec.top_deck_z_outer),
        (spec.front_step_y_end, spec.front_step_z_outer),
        (y0, spec.front_step_z_outer),
    ]
    outer_solid = _extrude_yz_profile(outer_yz, x0, x1)

    # Inner hollow cavity (offset downward/inward by wall thickness) in CCW order
    slope_angle = math.atan2(
        spec.top_deck_z_outer - spec.front_step_z_outer,
        spec.slope_y_end - spec.front_step_y_end,
    )
    y_shift = w * math.tan(slope_angle / 2.0)
    inner_yz = [
        (y_in0, spec.split_z_mm - 1.0),
        (y_in1, spec.split_z_mm - 1.0),
        (y_in1, spec.top_deck_z_outer - w),
        (spec.slope_y_end - y_shift, spec.top_deck_z_outer - w),
        (spec.front_step_y_end - y_shift, spec.front_step_z_outer - w),
        (y_in0, spec.front_step_z_outer - w),
    ]
    inner_cavity = _extrude_yz_profile(inner_yz, x_in0, x_in1)

    # Mating lip receiver pocket at bottom of top_shell with fit_tolerance_mm clearance
    lip_outer_inset = 1.40
    lip_pocket = _box_mesh(
        x0 + lip_outer_inset - spec.fit_tolerance_mm,
        y0 + lip_outer_inset - spec.fit_tolerance_mm,
        spec.split_z_mm - 0.5,
        x1 - lip_outer_inset + spec.fit_tolerance_mm,
        y1 - lip_outer_inset + spec.fit_tolerance_mm,
        spec.split_z_mm + spec.lip_height_mm + spec.fit_tolerance_mm,
    )

    add_parts: list[trimesh.Trimesh] = [outer_solid]
    cut_parts: list[trimesh.Trimesh] = [inner_cavity, lip_pocket]

    # Add flat raised seat (+0.8 mm bezel) for ON/OFF toggle switch plate (32 x 22 mm) on top deck
    sw_cx, sw_cy = spec.switch_center_xy
    add_parts.append(
        _box_mesh(
            sw_cx - 16.0,
            sw_cy - 11.0,
            spec.top_deck_z_outer - 1.0,
            sw_cx + 16.0,
            sw_cy + 11.0,
            spec.top_deck_z_outer + 0.8,
        )
    )
    # Toggle switch Ø12.2 mm bore
    cut_parts.append(
        _cylinder_z(
            sw_cx,
            sw_cy,
            spec.top_deck_z_outer - w - 1.0,
            spec.top_deck_z_outer + 1.5,
            spec.switch_hole_diam_mm / 2.0,
        )
    )

    # 3 Rear aesthetic cable grommets / strain-relief collars on rear wall
    for _, gx, gz, gdiam in spec.rear_grommets:
        add_parts.append(_cylinder_y(gx, y1 - 1.5, y1 + 4.0, gz, gdiam / 2.0 + 2.2))
        cut_parts.append(_cylinder_y(gx, y_in1 - 1.0, y1 + 4.5, gz, gdiam / 2.0))

    shell = _boolean_diff(_boolean_union(add_parts), cut_parts)

    # Add 4 internal M3 corner screw bosses (rising inside corners, clear of mating lip pocket)
    boss_adds: list[trimesh.Trimesh] = [shell]
    boss_cuts: list[trimesh.Trimesh] = []
    lip_clear_z = spec.split_z_mm + spec.lip_height_mm + spec.fit_tolerance_mm
    for bx, by in spec.closure_bosses_xy:
        boss_adds.append(_cylinder_z(bx, by, spec.split_z_mm, 34.0, 3.20))
        boss_cuts.append(_cylinder_z(bx, by, spec.split_z_mm - 0.5, 28.0, 1.40))
    # Clear lip pocket inside bosses if any overlap
    boss_cuts.append(
        _box_mesh(
            x0 + lip_outer_inset - spec.fit_tolerance_mm,
            y0 + lip_outer_inset - spec.fit_tolerance_mm,
            spec.split_z_mm - 0.5,
            x1 - lip_outer_inset + spec.fit_tolerance_mm,
            y1 - lip_outer_inset + spec.fit_tolerance_mm,
            lip_clear_z,
        )
    )

    # Front Micro-USB upper arch cutout
    ux0, ux1 = spec.usb_slot_x_range
    uz0, uz1 = spec.usb_slot_z_range
    boss_cuts.append(_box_mesh(ux0, y0 - 1.0, uz0 - 1.0, ux1, y_in0 + 1.0, uz1))

    # Left-side ESC ventilation slots (5 slots along left wall above split_z)
    for idx in range(5):
        vy0 = 16.0 + idx * 6.8
        boss_cuts.append(_box_mesh(x0 - 1.0, vy0, 21.0, x_in0 + 1.0, vy0 + 2.4, 32.0))

    result = _boolean_diff(_boolean_union(boss_adds), boss_cuts)
    return result


def box_mesh_from_bounds(box: BoundingBox3D) -> trimesh.Trimesh:
    """Convert a BoundingBox3D keep-out envelope to a watertight trimesh Box."""
    return _box_mesh(box.x_min, box.y_min, box.z_min, box.x_max, box.y_max, box.z_max)


def check_intersection_volume(mesh_a: trimesh.Trimesh, mesh_b: trimesh.Trimesh) -> float:
    """Compute exact 3D boolean intersection volume (mm^3) between two watertight meshes."""
    ba, bb = mesh_a.bounds, mesh_b.bounds
    if np.any(ba[1] <= bb[0]) or np.any(bb[1] <= ba[0]):
        return 0.0
    inter = trimesh.boolean.intersection([mesh_a, mesh_b], engine="manifold")
    if inter.is_empty:
        return 0.0
    return float(inter.volume)


def _draw_box_faces(ax: plt.Axes, box: BoundingBox3D, color: str, alpha: float = 0.45) -> None:
    x0, y0, z0, x1, y1, z1 = box.x_min, box.y_min, box.z_min, box.x_max, box.y_max, box.z_max
    verts = [
        [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)],
        [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
        [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],
        [(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)],
        [(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)],
        [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)],
    ]
    poly = Poly3DCollection(verts, facecolors=color, linewidths=0.4, edgecolors="black", alpha=alpha)
    ax.add_collection3d(poly)


def render_enclosure_preview(
    spec: EnclosureSpec,
    base_mesh: trimesh.Trimesh,
    top_mesh: trimesh.Trimesh,
    out_path: Path,
) -> Path:
    """Render 4-view verification figure (Isometric, Side Cutaway, Top View, Rear View)."""
    fig = plt.figure(figsize=(14.0, 10.5), dpi=180, facecolor="white")

    # 1. Isometric 3D view
    ax_iso = fig.add_subplot(2, 2, 1, projection="3d")
    base_tris = base_mesh.vertices[base_mesh.faces]
    top_tris = top_mesh.vertices[top_mesh.faces]
    ax_iso.add_collection3d(Poly3DCollection(base_tris, facecolors="#3B6EA5", alpha=0.75, linewidths=0.05, edgecolors="#1E3A5F"))
    ax_iso.add_collection3d(Poly3DCollection(top_tris, facecolors="#D0D5DD", alpha=0.30, linewidths=0.05, edgecolors="#667085"))
    _draw_box_faces(ax_iso, spec.pcb_keepout, "#2CA02C", alpha=0.65)
    _draw_box_faces(ax_iso, spec.esp32_keepout, "#1D4ED8", alpha=0.55)
    _draw_box_faces(ax_iso, spec.switch_keepout, "#DC2626", alpha=0.55)
    ax_iso.set_xlim(spec.x_outer_min - 5, spec.x_outer_max + 5)
    ax_iso.set_ylim(spec.y_outer_min - 5, spec.y_outer_max + 8)
    ax_iso.set_zlim(0, spec.top_deck_z_outer + 10)
    ax_iso.set_box_aspect((118, 117, 72))
    ax_iso.view_init(elev=24, azim=-48)
    ax_iso.set_title("1. Vista Isometrica (Base + Top Shell + Internos)", fontsize=10, fontweight="bold")
    ax_iso.set_xlabel("X (mm)")
    ax_iso.set_ylabel("Y (mm)")
    ax_iso.set_zlabel("Z (mm)")

    # 2. Side Cross-Section (Y-Z plane at X=46 mm) showing PCB + ESP32 + Switch clearances
    ax_side = fig.add_subplot(2, 2, 2)
    y_prof = [
        spec.y_outer_min,
        spec.y_outer_min,
        spec.front_step_y_end,
        spec.slope_y_end,
        spec.y_outer_max,
        spec.y_outer_max,
        spec.y_outer_min,
    ]
    z_prof = [0.0, spec.front_step_z_outer, spec.front_step_z_outer, spec.top_deck_z_outer, spec.top_deck_z_outer, 0.0, 0.0]
    ax_side.plot(y_prof, z_prof, color="black", linewidth=2.0, label="Perfil Exterior")
    ax_side.axhline(spec.split_z_mm, color="#666666", linestyle="--", linewidth=1.0, label="Union Base/Tapa")

    for box, col, lbl in (
        (spec.pcb_keepout, "#2CA02C", "PCB (92x88x1.6 mm)"),
        (spec.esp32_keepout, "#1D4ED8", "ESP32_KEEP_OUT (+24 mm)"),
        (spec.switch_keepout, "#DC2626", "SWITCH_KEEP_OUT (30x20x24 mm)"),
    ):
        ax_side.add_patch(
            mpatches.Rectangle(
                (box.y_min, box.z_min),
                box.y_max - box.y_min,
                box.z_max - box.z_min,
                facecolor=col,
                alpha=0.45,
                edgecolor=col,
                linewidth=1.5,
                label=lbl,
            )
        )
    ax_side.set_xlim(spec.y_outer_min - 5, spec.y_outer_max + 8)
    ax_side.set_ylim(-2, spec.top_deck_z_outer + 8)
    ax_side.set_aspect("equal")
    ax_side.grid(True, linestyle=":", alpha=0.5)
    ax_side.legend(loc="upper left", fontsize=7.5)
    ax_side.set_title("2. Corte Lateral Y-Z (X=46 mm) — Validacion Holguras", fontsize=10, fontweight="bold")
    ax_side.set_xlabel("Y (mm) [Frontal USB -> Trasero]")
    ax_side.set_ylabel("Z (mm)")

    # 3. Top View (X-Y plane)
    ax_top = fig.add_subplot(2, 2, 3)
    ax_top.add_patch(
        mpatches.Rectangle(
            (spec.x_outer_min, spec.y_outer_min),
            spec.x_outer_max - spec.x_outer_min,
            spec.y_outer_max - spec.y_outer_min,
            fill=False,
            edgecolor="black",
            linewidth=1.8,
            label="Caja Exterior",
        )
    )
    for box, col, lbl in (
        (spec.pcb_keepout, "#2CA02C", "PCB"),
        (spec.left_esc_keepout, "#F59E0B", "ESCs Izq"),
        (spec.esp32_keepout, "#1D4ED8", "ESP32"),
        (spec.switch_keepout, "#DC2626", "Switch"),
    ):
        ax_top.add_patch(
            mpatches.Rectangle(
                (box.x_min, box.y_min),
                box.x_max - box.x_min,
                box.y_max - box.y_min,
                facecolor=col,
                alpha=0.35,
                edgecolor=col,
                linewidth=1.2,
                label=lbl,
            )
        )
    for _, hx, hy, _ in spec.pcb_m3_holes:
        ax_top.add_patch(mpatches.Circle((hx, hy), radius=spec.standoff_od_mm / 2.0, fill=False, edgecolor="#111111", linewidth=1.2))
    sw_cx, sw_cy = spec.switch_center_xy
    ax_top.add_patch(mpatches.Circle((sw_cx, sw_cy), radius=spec.switch_hole_diam_mm / 2.0, fill=False, edgecolor="#990000", linewidth=1.5))
    ax_top.set_xlim(spec.x_outer_min - 6, spec.x_outer_max + 6)
    ax_top.set_ylim(spec.y_outer_min - 6, spec.y_outer_max + 10)
    ax_top.set_aspect("equal")
    ax_top.grid(True, linestyle=":", alpha=0.5)
    ax_top.legend(loc="upper right", fontsize=7.5)
    ax_top.set_title("3. Vista Superior X-Y (Standoffs M3 + Keep-Outs)", fontsize=10, fontweight="bold")
    ax_top.set_xlabel("X (mm)")
    ax_top.set_ylabel("Y (mm)")

    # 4. Rear View (X-Z plane) showing 3 rear cable grommets & left vents
    ax_rear = fig.add_subplot(2, 2, 4)
    ax_rear.add_patch(
        mpatches.Rectangle(
            (spec.x_outer_min, 0.0),
            spec.x_outer_max - spec.x_outer_min,
            spec.top_deck_z_outer,
            facecolor="#F3F4F6",
            edgecolor="black",
            linewidth=1.6,
        )
    )
    ax_rear.axhline(spec.split_z_mm, color="#666666", linestyle="--", linewidth=1.0)
    for g_name, gx, gz, gdiam in spec.rear_grommets:
        ax_rear.add_patch(mpatches.Circle((gx, gz), radius=gdiam / 2.0 + 2.2, facecolor="#D1D5DB", edgecolor="black", linewidth=1.0))
        ax_rear.add_patch(mpatches.Circle((gx, gz), radius=gdiam / 2.0, facecolor="white", edgecolor="#DC2626", linewidth=1.2))
        ax_rear.text(gx, gz + gdiam / 2.0 + 4.0, g_name, fontsize=7.0, ha="center", family="monospace")
    ax_rear.set_xlim(spec.x_outer_min - 6, spec.x_outer_max + 6)
    ax_rear.set_ylim(-2, spec.top_deck_z_outer + 8)
    ax_rear.set_aspect("equal")
    ax_rear.grid(True, linestyle=":", alpha=0.5)
    ax_rear.set_title("4. Vista Trasera X-Z (3 Pasacables: LiPo, Motores, I2C)", fontsize=10, fontweight="bold")
    ax_rear.set_xlabel("X (mm)")
    ax_rear.set_ylabel("Z (mm)")

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, format="png", dpi=180)
    plt.close(fig)
    return out_path


def build_all(output_dir: Path | None = None) -> dict[str, Path]:
    """Generate enclosure_base.stl, enclosure_top_shell.stl, and enclosure_preview.png."""
    if output_dir is None:
        output_dir = Path(__file__).resolve().parent.parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    spec = build_enclosure_spec()
    base_mesh = build_base_mesh(spec)
    top_mesh = build_top_shell_mesh(spec)

    base_stl = output_dir / "enclosure_base.stl"
    top_stl = output_dir / "enclosure_top_shell.stl"
    preview_png = output_dir / "enclosure_preview.png"

    base_mesh.export(str(base_stl))
    top_mesh.export(str(top_stl))
    render_enclosure_preview(spec, base_mesh, top_mesh, preview_png)

    return {
        "base_stl": base_stl,
        "top_shell_stl": top_stl,
        "preview_png": preview_png,
    }


if __name__ == "__main__":
    build_all()
