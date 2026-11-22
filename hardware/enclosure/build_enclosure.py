"""Parametric 3D CAD solid builder (manifold3d + trimesh) with ergonomic fillets & engraved team names."""

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
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath
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


def _rounded_rect_points(
    x_min: float,
    y_min: float,
    x_max: float,
    y_max: float,
    radius: float,
    segments_per_corner: int = 20,
) -> list[tuple[float, float]]:
    """Generate CCW 2D rounded-rectangle perimeter points (>= 16 segments per corner)."""
    if radius <= 1e-6:
        return [(x_min, y_min), (x_max, y_min), (x_max, y_max), (x_min, y_max)]

    r = min(radius, (x_max - x_min) / 2.0 - 1e-3, (y_max - y_min) / 2.0 - 1e-3)
    corners = [
        (x_max - r, y_max - r, 0.0, math.pi / 2.0),
        (x_min + r, y_max - r, math.pi / 2.0, math.pi),
        (x_min + r, y_min + r, math.pi, 1.5 * math.pi),
        (x_max - r, y_min + r, 1.5 * math.pi, 2.0 * math.pi),
    ]
    pts: list[tuple[float, float]] = []
    for cx, cy, a0, a1 in corners:
        for step in range(segments_per_corner + 1):
            ang = a0 + (a1 - a0) * (step / segments_per_corner)
            pts.append((round(cx + r * math.cos(ang), 5), round(cy + r * math.sin(ang), 5)))
    return pts


def _extrude_xy_rounded_rect(
    x_min: float,
    y_min: float,
    x_max: float,
    y_max: float,
    z_min: float,
    z_max: float,
    radius: float,
    segments_per_corner: int = 20,
) -> trimesh.Trimesh:
    """Extrude a rounded XY rectangle from z_min to z_max."""
    pts = _rounded_rect_points(x_min, y_min, x_max, y_max, radius, segments_per_corner=segments_per_corner)
    man = m3d.CrossSection([pts]).extrude(z_max - z_min)
    raw = man.to_mesh()
    mesh = trimesh.Trimesh(vertices=np.asarray(raw.vert_properties[:, :3]), faces=np.asarray(raw.tri_verts))
    mesh.apply_translation([0.0, 0.0, z_min])
    return mesh


def _loft_chamfered_rounded_rect(
    x_min: float,
    y_min: float,
    x_max: float,
    y_max: float,
    z_bot: float,
    z_top: float,
    radius: float,
    chamfer_mm: float,
    segments_per_corner: int = 20,
) -> trimesh.Trimesh:
    """Build a watertight 45-deg bottom-chamfered rounded-rectangle frustum [z_bot, z_top]."""
    ring_bot = _rounded_rect_points(
        x_min + chamfer_mm,
        y_min + chamfer_mm,
        x_max - chamfer_mm,
        y_max - chamfer_mm,
        max(0.2, radius - chamfer_mm),
        segments_per_corner=segments_per_corner,
    )
    ring_top = _rounded_rect_points(
        x_min,
        y_min,
        x_max,
        y_max,
        radius,
        segments_per_corner=segments_per_corner,
    )
    n = len(ring_bot)
    cx = (x_min + x_max) / 2.0
    cy = (y_min + y_max) / 2.0

    verts: list[tuple[float, float, float]] = [(cx, cy, z_bot), (cx, cy, z_top)]
    for x, y in ring_bot:
        verts.append((x, y, z_bot))
    for x, y in ring_top:
        verts.append((x, y, z_top))

    faces: list[tuple[int, int, int]] = []
    bot_start = 2
    top_start = 2 + n
    for i in range(n):
        nxt = (i + 1) % n
        b0, b1 = bot_start + i, bot_start + nxt
        t0, t1 = top_start + i, top_start + nxt
        # Bottom cap (outward normal -Z)
        faces.append((0, b1, b0))
        # Top cap (outward normal +Z)
        faces.append((1, t0, t1))
        # Side quad
        faces.append((b0, b1, t1))
        faces.append((b0, t1, t0))

    return trimesh.Trimesh(vertices=np.asarray(verts, dtype=np.float64), faces=np.asarray(faces, dtype=np.int64))


def _fillet_polygon_2d(
    pts: list[tuple[float, float]],
    radii: list[float],
    arc_segments: int = 16,
) -> list[tuple[float, float]]:
    """Apply exact circular corner fillets (convex or concave) to a closed 2D polygon."""
    n = len(pts)
    out: list[tuple[float, float]] = []
    for i in range(n):
        p_prev = np.array(pts[(i - 1) % n], dtype=np.float64)
        p_curr = np.array(pts[i], dtype=np.float64)
        p_next = np.array(pts[(i + 1) % n], dtype=np.float64)
        r = radii[i]
        if r <= 1e-6:
            out.append((float(p_curr[0]), float(p_curr[1])))
            continue

        u = p_prev - p_curr
        v = p_next - p_curr
        u_len = float(np.linalg.norm(u))
        v_len = float(np.linalg.norm(v))
        u_dir = u / u_len
        v_dir = v / v_len
        dot_uv = max(-0.999999, min(0.999999, float(np.dot(u_dir, v_dir))))
        theta = math.acos(dot_uv)
        half_theta = theta / 2.0
        tan_dist = r / math.tan(half_theta)
        tan_dist = min(tan_dist, 0.45 * u_len, 0.45 * v_len)
        r_eff = tan_dist * math.tan(half_theta)

        t1 = p_curr + tan_dist * u_dir
        t2 = p_curr + tan_dist * v_dir
        bisect = u_dir + v_dir
        bisect_dir = bisect / float(np.linalg.norm(bisect))
        center = p_curr + (r_eff / math.sin(half_theta)) * bisect_dir

        a1 = math.atan2(float(t1[1] - center[1]), float(t1[0] - center[0]))
        a2 = math.atan2(float(t2[1] - center[1]), float(t2[0] - center[0]))
        # Shortest angular sweep around fillet center
        delta = (a2 - a1 + math.pi) % (2.0 * math.pi) - math.pi
        for step in range(arc_segments + 1):
            ang = a1 + delta * (step / arc_segments)
            px = float(center[0]) + r_eff * math.cos(ang)
            py = float(center[1]) + r_eff * math.sin(ang)
            out.append((round(px, 5), round(py, 5)))
    return out


def _extrude_yz_profile(
    yz_points: list[tuple[float, float]],
    x_min: float,
    x_max: float,
) -> trimesh.Trimesh:
    """Extrude a 2D polygon in the (Y, Z) plane along the X axis [x_min, x_max] via manifold3d."""
    man = m3d.CrossSection([yz_points]).extrude(x_max - x_min)
    raw = man.to_mesh()
    mesh = trimesh.Trimesh(vertices=np.asarray(raw.vert_properties[:, :3]), faces=np.asarray(raw.tri_verts))
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
    cyl = trimesh.creation.cylinder(radius=radius, height=(z_max - z_min), sections=sections)
    cyl.apply_translation([cx, cy, (z_min + z_max) / 2.0])
    return cyl


def _cylinder_y(cx: float, y_min: float, y_max: float, cz: float, radius: float, sections: int = 32) -> trimesh.Trimesh:
    """Create a Y-aligned watertight cylinder from y_min to y_max."""
    cyl = trimesh.creation.cylinder(radius=radius, height=(y_max - y_min), sections=sections)
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


def _boolean_intersect(meshes: list[trimesh.Trimesh]) -> trimesh.Trimesh:
    if len(meshes) == 1:
        return meshes[0]
    return trimesh.boolean.intersection(meshes, engine="manifold")


def _simplify_slivers(mesh: trimesh.Trimesh, tol_mm: float = 1e-3) -> trimesh.Trimesh:
    """Remove sub-micron sliver triangles from boolean operations while preserving manifold topology."""
    man = m3d.Manifold(
        m3d.Mesh(
            vert_properties=np.asarray(mesh.vertices, dtype=np.float32),
            tri_verts=np.asarray(mesh.faces, dtype=np.uint32),
        )
    ).simplify(tol_mm)
    raw = man.to_mesh()
    return trimesh.Trimesh(vertices=np.asarray(raw.vert_properties[:, :3]), faces=np.asarray(raw.tri_verts))


def build_engraved_text_manifold(
    lines: tuple[str, ...] | list[str],
    depth_mm: float,
    font_size_mm: float = 4.3,
    line_spacing_mm: float = 6.3,
    air_overcut_mm: float = 0.8,
) -> m3d.Manifold:
    """Convert multi-line text into clean watertight extruded solids via TextPath + manifold3d.

    Local coordinates before placement:
    - X: centered at 0.0 mm
    - Y: centered vertically around 0.0 mm (top line at +Y, bottom line at -Y)
    - Z: [-depth_mm, +air_overcut_mm] so Z=0 rests on the outer surface and Z<0 cuts inward.
    """
    prop = FontProperties(family="DejaVu Sans", weight="bold")
    total_h = (len(lines) - 1) * line_spacing_mm
    solids: list[m3d.Manifold] = []

    for idx, text in enumerate(lines):
        tp = TextPath((0.0, 0.0), text, size=font_size_mm, prop=prop)
        raw_polys = tp.to_polygons()
        polys: list[list[tuple[float, float]]] = []
        min_x, max_x = math.inf, -math.inf
        min_y, max_y = math.inf, -math.inf

        for arr in raw_polys:
            pts = arr[:-1] if np.allclose(arr[0], arr[-1]) else arr
            if len(pts) < 3:
                continue
            cleaned: list[tuple[float, float]] = []
            for px, py in pts:
                if not cleaned or math.hypot(px - cleaned[-1][0], py - cleaned[-1][1]) > 1e-4:
                    cleaned.append((float(px), float(py)))
                    min_x = min(min_x, float(px))
                    max_x = max(max_x, float(px))
                    min_y = min(min_y, float(py))
                    max_y = max(max_y, float(py))
            if len(cleaned) >= 3:
                polys.append(cleaned)

        if not polys:
            continue

        cx = (min_x + max_x) / 2.0
        cy = (min_y + max_y) / 2.0
        y_line_offset = (total_h / 2.0) - idx * line_spacing_mm
        centered_polys = [[(px - cx, py - cy + y_line_offset) for px, py in poly] for poly in polys]

        cs = m3d.CrossSection(centered_polys, m3d.FillRule.EvenOdd)
        extruded = cs.extrude(depth_mm + air_overcut_mm).translate((0.0, 0.0, -depth_mm))
        solids.append(extruded)

    return m3d.Manifold.compose(solids)


def _slope_text_cutter_mesh(spec: EnclosureSpec) -> trimesh.Trimesh:
    """Position the engraved team-names manifold cleanly onto the center of the sloped panel."""
    dy = spec.slope_y_end - spec.front_step_y_end
    dz = spec.top_deck_z_outer - spec.front_step_z_outer
    slope_rad = math.atan2(dz, dy)
    slope_deg = math.degrees(slope_rad)

    text_man = build_engraved_text_manifold(
        lines=spec.team_names,
        depth_mm=spec.engrave_depth_mm,
        font_size_mm=4.3,
        line_spacing_mm=6.3,
        air_overcut_mm=0.8,
    )
    # Tilt local Z outward normal to match slope outward normal (rotated +slope_deg around X)
    # Center text midway up the straight sloped face (between fillets at Y=14 and Y=56)
    y_mid = (spec.front_step_y_end + spec.slope_y_end) / 2.0
    z_mid = (spec.front_step_z_outer + spec.top_deck_z_outer) / 2.0
    x_mid = (spec.x_outer_min + spec.x_outer_max) / 2.0

    placed = text_man.rotate((slope_deg, 0.0, 0.0)).translate((x_mid, y_mid, z_mid))
    raw = placed.to_mesh()
    return trimesh.Trimesh(vertices=np.asarray(raw.vert_properties[:, :3]), faces=np.asarray(raw.tri_verts))


def build_base_mesh(spec: EnclosureSpec) -> trimesh.Trimesh:
    """Build watertight rounded enclosure_base mesh with 45-deg bottom chamfer, M3 standoffs & mating lip."""
    w = spec.wall_mm
    r_xy = spec.corner_radius_xy_mm
    x0, x1 = spec.x_outer_min, spec.x_outer_max
    y0, y1 = spec.y_outer_min, spec.y_outer_max
    x_in0, x_in1 = x0 + w, x1 - w
    y_in0, y_in1 = y0 + w, y1 - w

    # 45-deg bottom chamfer [0, 1.2 mm] + rounded vertical outer body [1.2 mm, split_z]
    chamfer = _loft_chamfered_rounded_rect(
        x0, y0, x1, y1, 0.0, spec.bottom_chamfer_mm, radius=r_xy, chamfer_mm=spec.bottom_chamfer_mm
    )
    upper_outer = _extrude_xy_rounded_rect(
        x0, y0, x1, y1, spec.bottom_chamfer_mm - 0.05, spec.split_z_mm, radius=r_xy
    )

    # Stepped rounded mating lip rising lip_height_mm above split_z
    lip_inset = 1.40
    lip_ring = _extrude_xy_rounded_rect(
        x0 + lip_inset,
        y0 + lip_inset,
        x1 - lip_inset,
        y1 - lip_inset,
        spec.split_z_mm - 0.5,
        spec.split_z_mm + spec.lip_height_mm,
        radius=max(1.0, r_xy - lip_inset),
    )
    solid = _boolean_union([chamfer, upper_outer, lip_ring])

    # Rounded inner cavity above floor
    cavity = _extrude_xy_rounded_rect(
        x_in0,
        y_in0,
        x_in1,
        y_in1,
        spec.floor_mm,
        spec.split_z_mm + spec.lip_height_mm + 1.0,
        radius=max(1.0, r_xy - w),
    )
    shell = _boolean_diff(solid, [cavity])

    # 4 internal M3 PCB standoffs + 4 corner closure bosses
    add_parts: list[trimesh.Trimesh] = [shell]
    cut_parts: list[trimesh.Trimesh] = []

    z_pcb_bot = spec.floor_mm + spec.standoff_height_mm
    for _, hx, hy, _ in spec.pcb_m3_holes:
        add_parts.append(_cylinder_z(hx, hy, spec.floor_mm - 0.2, z_pcb_bot, spec.standoff_od_mm / 2.0))
        cut_parts.append(_cylinder_z(hx, hy, spec.floor_mm + 0.8, z_pcb_bot + 0.5, spec.standoff_drill_mm / 2.0))

    for bx, by in spec.closure_bosses_xy:
        add_parts.append(_cylinder_z(bx, by, spec.floor_mm - 0.2, spec.split_z_mm, 3.20))
        cut_parts.append(_cylinder_z(bx, by, -0.5, spec.split_z_mm + 0.5, 1.70))
        cut_parts.append(_cylinder_z(bx, by, -0.5, 2.20, 3.00))

    # Front Micro-USB cutout through front wall & lip
    ux0, ux1 = spec.usb_slot_x_range
    uz0, uz1 = spec.usb_slot_z_range
    cut_parts.append(_box_mesh(ux0, y0 - 1.0, uz0, ux1, y_in0 + 1.0, uz1))

    return _simplify_slivers(_boolean_diff(_boolean_union(add_parts), cut_parts))


def build_top_shell_mesh(spec: EnclosureSpec) -> trimesh.Trimesh:
    """Build watertight ergonomic top_shell with XY corners, Y-Z fillets, engraved names & switch seat."""
    w = spec.wall_mm
    r_xy = spec.corner_radius_xy_mm
    r_yz = spec.profile_fillet_yz_mm
    x0, x1 = spec.x_outer_min, spec.x_outer_max
    y0, y1 = spec.y_outer_min, spec.y_outer_max
    x_in0, x_in1 = x0 + w, x1 - w
    y_in0, y_in1 = y0 + w, y1 - w

    # 1. Outer sloped Y-Z profile with >= 4.0 mm circular fillets, intersected with rounded XY footprint
    outer_raw_yz = [
        (y0, spec.split_z_mm),
        (y1, spec.split_z_mm),
        (y1, spec.top_deck_z_outer),
        (spec.slope_y_end, spec.top_deck_z_outer),
        (spec.front_step_y_end, spec.front_step_z_outer),
        (y0, spec.front_step_z_outer),
    ]
    outer_filleted_yz = _fillet_polygon_2d(
        outer_raw_yz,
        radii=[0.0, 0.0, r_yz, r_yz + 1.5, r_yz + 0.5, r_yz],
        arc_segments=16,
    )
    outer_yz_prism = _extrude_yz_profile(outer_filleted_yz, x0 - 1.0, x1 + 1.0)
    outer_xy_prism = _extrude_xy_rounded_rect(
        x0, y0, x1, y1, spec.split_z_mm, spec.top_deck_z_outer + 2.0, radius=r_xy
    )
    outer_solid = _boolean_intersect([outer_yz_prism, outer_xy_prism])

    # 2. Exact perpendicular inward-offset inner cavity (>= 2.40 mm wall everywhere including slope!)
    dy = spec.slope_y_end - spec.front_step_y_end
    dz = spec.top_deck_z_outer - spec.front_step_z_outer
    slope_angle = math.atan2(dz, dy)
    y_shift_slope = w * math.sin(slope_angle)
    z_shift_slope = w * math.cos(slope_angle)
    # Intersection of z = front_step_z - w with offset slope line:
    # (y - (front_step_y + y_shift_slope)) * tan(slope_angle) = (front_step_z - w) - (front_step_z - z_shift_slope)
    y_in_step = spec.front_step_y_end + y_shift_slope - (w - z_shift_slope) / math.tan(slope_angle)
    y_in_slope_end = spec.slope_y_end + y_shift_slope - (w - z_shift_slope) / math.tan(slope_angle)

    inner_raw_yz = [
        (y_in0, spec.split_z_mm - 1.0),
        (y_in1, spec.split_z_mm - 1.0),
        (y_in1, spec.top_deck_z_outer - w),
        (y_in_slope_end, spec.top_deck_z_outer - w),
        (y_in_step, spec.front_step_z_outer - w),
        (y_in0, spec.front_step_z_outer - w),
    ]
    inner_filleted_yz = _fillet_polygon_2d(
        inner_raw_yz,
        radii=[0.0, 0.0, max(1.0, r_yz - w), max(1.0, r_yz + 1.5 - w), r_yz + 0.5 + w, max(1.0, r_yz - w)],
        arc_segments=16,
    )
    inner_yz_prism = _extrude_yz_profile(inner_filleted_yz, x_in0 - 1.0, x_in1 + 1.0)
    inner_xy_prism = _extrude_xy_rounded_rect(
        x_in0,
        y_in0,
        x_in1,
        y_in1,
        spec.split_z_mm - 1.0,
        spec.top_deck_z_outer + 1.0,
        radius=max(1.0, r_xy - w),
    )
    inner_cavity = _boolean_intersect([inner_yz_prism, inner_xy_prism])

    # 3. Rounded mating lip receiver pocket at bottom of top_shell (0.30 mm fit tolerance)
    lip_inset = 1.40
    lip_pocket = _extrude_xy_rounded_rect(
        x0 + lip_inset - spec.fit_tolerance_mm,
        y0 + lip_inset - spec.fit_tolerance_mm,
        x1 - lip_inset + spec.fit_tolerance_mm,
        y1 - lip_inset + spec.fit_tolerance_mm,
        spec.split_z_mm - 0.5,
        spec.split_z_mm + spec.lip_height_mm + spec.fit_tolerance_mm,
        radius=max(1.0, r_xy - lip_inset + spec.fit_tolerance_mm),
    )

    add_parts: list[trimesh.Trimesh] = [outer_solid]
    cut_parts: list[trimesh.Trimesh] = [inner_cavity, lip_pocket]

    # 4. Flat raised seat (+0.8 mm bezel) for ON/OFF toggle switch plate (32 x 22 mm) + Ø12.2 mm bore
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
    cut_parts.append(
        _cylinder_z(
            sw_cx,
            sw_cy,
            spec.top_deck_z_outer - w - 1.0,
            spec.top_deck_z_outer + 1.5,
            spec.switch_hole_diam_mm / 2.0,
        )
    )

    # 5. 3 Rear aesthetic cable grommets / strain-relief collars
    for _, gx, gz, gdiam in spec.rear_grommets:
        add_parts.append(_cylinder_y(gx, y1 - 1.5, y1 + 4.0, gz, gdiam / 2.0 + 2.2))
        cut_parts.append(_cylinder_y(gx, y_in1 - 1.0, y1 + 4.5, gz, gdiam / 2.0))

    # 6. Engraved team names (0.60 mm depth) subtracted from sloped front-to-top panel
    cut_parts.append(_slope_text_cutter_mesh(spec))

    shell = _boolean_diff(_boolean_union(add_parts), cut_parts)

    # 7. Internal M3 corner bosses + front Micro-USB cutout + left-side ESC cooling slots
    boss_adds: list[trimesh.Trimesh] = [shell]
    boss_cuts: list[trimesh.Trimesh] = [lip_pocket]
    for bx, by in spec.closure_bosses_xy:
        boss_adds.append(_cylinder_z(bx, by, spec.split_z_mm, 34.0, 3.20))
        boss_cuts.append(_cylinder_z(bx, by, spec.split_z_mm - 0.5, 28.0, 1.40))

    ux0, ux1 = spec.usb_slot_x_range
    uz0, uz1 = spec.usb_slot_z_range
    boss_cuts.append(_box_mesh(ux0, y0 - 1.0, uz0 - 1.0, ux1, y_in0 + 1.0, uz1))

    for idx in range(5):
        vy0 = 16.0 + idx * 6.8
        boss_cuts.append(_box_mesh(x0 - 1.0, vy0, 21.0, x_in0 + 1.0, vy0 + 2.4, 32.0))

    return _simplify_slivers(_boolean_diff(_boolean_union(boss_adds), boss_cuts))


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
    """Render 4-view verification figure including close-up of fillets and engraved team names."""
    fig = plt.figure(figsize=(15.0, 11.0), dpi=180, facecolor="white")

    # 1. Isometric 3D view
    ax_iso = fig.add_subplot(2, 2, 1, projection="3d")
    base_tris = base_mesh.vertices[base_mesh.faces]
    top_tris = top_mesh.vertices[top_mesh.faces]
    ax_iso.add_collection3d(
        Poly3DCollection(base_tris, facecolors="#3B6EA5", alpha=0.80, linewidths=0.04, edgecolors="#1E3A5F")
    )
    ax_iso.add_collection3d(
        Poly3DCollection(top_tris, facecolors="#E2E8F0", alpha=0.40, linewidths=0.04, edgecolors="#475569")
    )
    _draw_box_faces(ax_iso, spec.pcb_keepout, "#2CA02C", alpha=0.55)
    _draw_box_faces(ax_iso, spec.esp32_keepout, "#1D4ED8", alpha=0.45)
    _draw_box_faces(ax_iso, spec.switch_keepout, "#DC2626", alpha=0.45)
    ax_iso.set_xlim(spec.x_outer_min - 4, spec.x_outer_max + 4)
    ax_iso.set_ylim(spec.y_outer_min - 4, spec.y_outer_max + 8)
    ax_iso.set_zlim(0, spec.top_deck_z_outer + 8)
    ax_iso.set_box_aspect((116, 116, 70))
    ax_iso.view_init(elev=26, azim=-52)
    ax_iso.set_title("1. Vista Isometrica (Curvas Ergonomicas + Grabado)", fontsize=10, fontweight="bold")
    ax_iso.set_xlabel("X (mm)")
    ax_iso.set_ylabel("Y (mm)")
    ax_iso.set_zlabel("Z (mm)")

    # 2. Close-up Front/Sloped View showing rounded corners, fillets & engraved team names
    ax_engr = fig.add_subplot(2, 2, 2, projection="3d")
    ax_engr.add_collection3d(
        Poly3DCollection(base_tris, facecolors="#3B6EA5", alpha=0.95, linewidths=0.05, edgecolors="#1E3A5F")
    )
    ax_engr.add_collection3d(
        Poly3DCollection(top_tris, facecolors="#CBD5E1", alpha=0.95, linewidths=0.06, edgecolors="#334155")
    )
    ax_engr.set_xlim(spec.x_outer_min + 2, spec.x_outer_max - 2)
    ax_engr.set_ylim(spec.y_outer_min, spec.slope_y_end + 18)
    ax_engr.set_zlim(10, spec.top_deck_z_outer + 4)
    ax_engr.set_box_aspect((100, 82, 56))
    ax_engr.view_init(elev=48, azim=-90)
    ax_engr.set_title("2. Acercamiento Panel Inclinado (Bajorrelieve 0.6 mm + Redondeos)", fontsize=10, fontweight="bold")
    ax_engr.set_xlabel("X (mm)")
    ax_engr.set_ylabel("Y (mm)")
    ax_engr.set_zlabel("Z (mm)")

    # 3. Side Cross-Section (Y-Z plane) showing rounded profile fillets & zero collisions
    ax_side = fig.add_subplot(2, 2, 3)
    raw_yz = [
        (spec.y_outer_min, spec.split_z_mm),
        (spec.y_outer_max, spec.split_z_mm),
        (spec.y_outer_max, spec.top_deck_z_outer),
        (spec.slope_y_end, spec.top_deck_z_outer),
        (spec.front_step_y_end, spec.front_step_z_outer),
        (spec.y_outer_min, spec.front_step_z_outer),
    ]
    filleted_yz = _fillet_polygon_2d(
        raw_yz,
        radii=[0.0, 0.0, spec.profile_fillet_yz_mm, spec.profile_fillet_yz_mm + 1.5, spec.profile_fillet_yz_mm + 0.5, spec.profile_fillet_yz_mm],
        arc_segments=16,
    )
    fy = [p[0] for p in filleted_yz] + [filleted_yz[0][0]]
    fz = [p[1] for p in filleted_yz] + [filleted_yz[0][1]]
    ax_side.plot(fy, fz, color="black", linewidth=2.0, label="Top Shell (Filetes Y-Z)")
    ax_side.plot(
        [spec.y_outer_min + spec.bottom_chamfer_mm, spec.y_outer_max - spec.bottom_chamfer_mm, spec.y_outer_max, spec.y_outer_max, spec.y_outer_min, spec.y_outer_min, spec.y_outer_min + spec.bottom_chamfer_mm],
        [0.0, 0.0, spec.bottom_chamfer_mm, spec.split_z_mm, spec.split_z_mm, spec.bottom_chamfer_mm, 0.0],
        color="#1E3A5F",
        linewidth=1.8,
        label="Base (Chaflan 1.2 mm 45 deg)",
    )
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
                linewidth=1.4,
                label=lbl,
            )
        )
    ax_side.set_xlim(spec.y_outer_min - 5, spec.y_outer_max + 8)
    ax_side.set_ylim(-2, spec.top_deck_z_outer + 8)
    ax_side.set_aspect("equal")
    ax_side.grid(True, linestyle=":", alpha=0.5)
    ax_side.legend(loc="upper left", fontsize=7.0)
    ax_side.set_title("3. Corte Lateral Y-Z (Filetes >= 4.5 mm + Holguras Internas)", fontsize=10, fontweight="bold")
    ax_side.set_xlabel("Y (mm)")
    ax_side.set_ylabel("Z (mm)")

    # 4. Top View (X-Y plane) showing rounded XY corners, M3 standoffs & switch keep-out
    ax_top = fig.add_subplot(2, 2, 4)
    xy_pts = _rounded_rect_points(
        spec.x_outer_min, spec.y_outer_min, spec.x_outer_max, spec.y_outer_max, spec.corner_radius_xy_mm
    )
    ax_top.plot([p[0] for p in xy_pts] + [xy_pts[0][0]], [p[1] for p in xy_pts] + [xy_pts[0][1]], color="black", linewidth=1.8, label="Contorno R6.5 mm")
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
    ax_top.legend(loc="upper right", fontsize=7.0)
    ax_top.set_title("4. Vista Superior X-Y (Esquinas R6.5 mm + Standoffs M3)", fontsize=10, fontweight="bold")
    ax_top.set_xlabel("X (mm)")
    ax_top.set_ylabel("Y (mm)")

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, format="png", dpi=180)
    plt.close(fig)
    return out_path


def build_all(output_dir: Path | None = None) -> dict[str, Path]:
    """Generate rounded & engraved enclosure_base.stl, enclosure_top_shell.stl, and enclosure_preview.png."""
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
