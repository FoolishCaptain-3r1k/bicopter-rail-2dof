"""Pure Euclidean geometry Design Rule Check (DRC) & net connectivity engine."""

from __future__ import annotations

import math
from collections import defaultdict, deque
from dataclasses import dataclass, field

from hardware.pcb_spec import PcbBoard

MIN_NET_CLEARANCE_MM = 0.70
MIN_BANNER_CLEARANCE_MM = 1.50
MIN_SIGNAL_TRACE_WIDTH_MM = 1.00
MIN_GROUND_BRIDGE_WIDTH_MM = 1.50
MIN_POWER_TRACE_WIDTH_MM = 4.00
MIN_BANNER_STROKE_WIDTH_MM = 0.50
MIN_HEADER_PAD_MAJOR_MM = 1.90
MIN_ESC_SIG_PAD_MM = 2.50
MIN_POWER_PAD_MM = 5.00
M3_EXCLUSION_RADIUS_MM = 6.50
ESP32_ROW_SPACING_MM = 25.40


@dataclass(frozen=True)
class DrcViolation:
    """Single geometric or electrical DRC error."""

    category: str
    message: str
    measured_mm: float | None = None
    required_mm: float | None = None


@dataclass
class DrcReport:
    """Comprehensive DRC verification summary."""

    passed: bool
    errors: list[DrcViolation] = field(default_factory=list)
    min_net_clearance_mm: float = math.inf
    min_banner_clearance_mm: float = math.inf
    min_signal_width_mm: float = math.inf
    min_power_width_mm: float = math.inf
    min_banner_stroke_mm: float = math.inf
    connected_nets: dict[str, bool] = field(default_factory=dict)
    vin_isolated: bool = False
    esp32_row_pitch_mm: float = 0.0


def point_to_segment_dist(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    """Exact Euclidean distance from point (px, py) to closed line segment (x1, y1)-(x2, y2)."""
    dx = x2 - x1
    dy = y2 - y1
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq <= 1e-12:
        return math.hypot(px - x1, py - y1)
    t = ((px - x1) * dx + (py - y1) * dy) / seg_len_sq
    t = max(0.0, min(1.0, t))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def _ccw(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> float:
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def _segments_intersect(
    x1: float, y1: float, x2: float, y2: float, x3: float, y3: float, x4: float, y4: float
) -> bool:
    d1 = _ccw(x3, y3, x4, y4, x1, y1)
    d2 = _ccw(x3, y3, x4, y4, x2, y2)
    d3 = _ccw(x1, y1, x2, y2, x3, y3)
    d4 = _ccw(x1, y1, x2, y2, x4, y4)
    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return True
    eps = 1e-9
    if abs(d1) <= eps and point_to_segment_dist(x1, y1, x3, y3, x4, y4) <= eps:
        return True
    if abs(d2) <= eps and point_to_segment_dist(x2, y2, x3, y3, x4, y4) <= eps:
        return True
    if abs(d3) <= eps and point_to_segment_dist(x3, y3, x1, y1, x2, y2) <= eps:
        return True
    if abs(d4) <= eps and point_to_segment_dist(x4, y4, x1, y1, x2, y2) <= eps:
        return True
    return False


def segment_to_segment_dist(
    x1: float, y1: float, x2: float, y2: float, x3: float, y3: float, x4: float, y4: float
) -> float:
    """Exact Euclidean distance between two 2D closed line segments."""
    if _segments_intersect(x1, y1, x2, y2, x3, y3, x4, y4):
        return 0.0
    return min(
        point_to_segment_dist(x1, y1, x3, y3, x4, y4),
        point_to_segment_dist(x2, y2, x3, y3, x4, y4),
        point_to_segment_dist(x3, y3, x1, y1, x2, y2),
        point_to_segment_dist(x4, y4, x1, y1, x2, y2),
    )


def capsule_clearance(
    cap_a: tuple[float, float, float, float, float],
    cap_b: tuple[float, float, float, float, float],
) -> float:
    """Return copper-to-copper edge distance between two capsules (negative if overlapping)."""
    x1, y1, x2, y2, r1 = cap_a
    x3, y3, x4, y4, r2 = cap_b
    center_dist = segment_to_segment_dist(x1, y1, x2, y2, x3, y3, x4, y4)
    return center_dist - (r1 + r2)


def run_drc(board: PcbBoard) -> DrcReport:
    """Execute geometric and graph-connectivity DRC checks on the 1-layer board."""
    errors: list[DrcViolation] = []

    # 0. Board envelope, 1-layer planar invariants & M3 holes
    if board.width_mm > 94.0 or board.height_mm > 90.0:
        errors.append(
            DrcViolation(
                "board_dims",
                f"Board {board.width_mm}x{board.height_mm} mm exceeds 94x90 mm limit",
            )
        )
    if board.layer != "B.Cu" or board.jumpers_count != 0 or board.passive_components_count != 0:
        errors.append(
            DrcViolation(
                "planar_1layer",
                "Board must be strictly 1-layer B.Cu with 0 jumpers and 0 passive components",
            )
        )
    if len(board.mounting_holes) != 4:
        errors.append(DrcViolation("mounting_holes", f"Expected 4 M3 holes, found {len(board.mounting_holes)}"))

    # Verify ESP32 25.40 mm row spacing
    esp_left_xs = {p.x_mm for p in board.pads if p.component == "ESP32" and p.name in {f"ESP32_{k}" for k in ("EN", "GND_L", "VIN")}}
    esp_right_xs = {p.x_mm for p in board.pads if p.component == "ESP32" and p.name in {f"ESP32_{k}" for k in ("D23", "GND_R", "3V3")}}
    esp32_row_pitch = 0.0
    if len(esp_left_xs) == 1 and len(esp_right_xs) == 1:
        esp32_row_pitch = round(next(iter(esp_right_xs)) - next(iter(esp_left_xs)), 4)
    if abs(esp32_row_pitch - ESP32_ROW_SPACING_MM) > 1e-3:
        errors.append(
            DrcViolation(
                "esp32_pitch",
                f"ESP32 row spacing {esp32_row_pitch} mm != {ESP32_ROW_SPACING_MM} mm",
                measured_mm=esp32_row_pitch,
                required_mm=ESP32_ROW_SPACING_MM,
            )
        )

    # 1. Pad and trace dimensional checks
    power_pad_names = {
        "BAT_VBAT_IN",
        "ESC_L_VBAT",
        "ESC_R_VBAT",
        "BAT_GND_IN",
        "ESC_L_GND_PWR",
        "ESC_R_GND_PWR",
    }
    esc_sig_pad_names = {"ESC_L_SIG", "ESC_R_SIG", "ESC_L_GND_SIG", "ESC_R_GND_SIG"}

    for pad in board.pads:
        if pad.drill_mm <= 0.0:
            errors.append(DrcViolation("pad_drill", f"Pad {pad.name} missing central drill guide"))
        if pad.name in power_pad_names:
            if pad.major_mm < MIN_POWER_PAD_MM or abs(pad.drill_mm - 1.60) > 1e-3:
                errors.append(
                    DrcViolation(
                        "power_pad",
                        f"Power pad {pad.name} must be >= 5.0 mm with 1.6 mm drill",
                        measured_mm=pad.major_mm,
                        required_mm=MIN_POWER_PAD_MM,
                    )
                )
        elif pad.name in esc_sig_pad_names:
            if pad.major_mm < MIN_ESC_SIG_PAD_MM:
                errors.append(
                    DrcViolation(
                        "esc_sig_pad",
                        f"ESC signal pad {pad.name} must be >= 2.5 mm",
                        measured_mm=pad.major_mm,
                        required_mm=MIN_ESC_SIG_PAD_MM,
                    )
                )
        else:
            if pad.major_mm < MIN_HEADER_PAD_MAJOR_MM:
                errors.append(
                    DrcViolation(
                        "header_pad",
                        f"Header pad {pad.name} major dimension < 1.90 mm",
                        measured_mm=pad.major_mm,
                        required_mm=MIN_HEADER_PAD_MAJOR_MM,
                    )
                )

    min_signal_w = math.inf
    min_power_w = math.inf
    has_gnd_bridge = False

    for tr in board.traces:
        if tr.is_power_bus:
            min_power_w = min(min_power_w, tr.width_mm)
            if tr.width_mm < MIN_POWER_TRACE_WIDTH_MM - 1e-6:
                errors.append(
                    DrcViolation(
                        "power_trace_width",
                        f"Power trace on {tr.net} width {tr.width_mm} mm < 4.00 mm",
                        measured_mm=tr.width_mm,
                        required_mm=MIN_POWER_TRACE_WIDTH_MM,
                    )
                )
        else:
            min_signal_w = min(min_signal_w, tr.width_mm)
            if tr.width_mm < MIN_SIGNAL_TRACE_WIDTH_MM - 1e-6:
                errors.append(
                    DrcViolation(
                        "signal_trace_width",
                        f"Signal trace on {tr.net} width {tr.width_mm} mm < 1.00 mm",
                        measured_mm=tr.width_mm,
                        required_mm=MIN_SIGNAL_TRACE_WIDTH_MM,
                    )
                )
        # Check internal GND bridge under ESP32 (ESP32_GND_L to ESP32_GND_R)
        if tr.net == "GND" and abs(tr.y1_mm - 14.54) < 1e-2 and abs(tr.y2_mm - 14.54) < 1e-2:
            if min(tr.x1_mm, tr.x2_mm) <= 33.30 + 1e-2 and max(tr.x1_mm, tr.x2_mm) >= 58.70 - 1e-2:
                has_gnd_bridge = True
                if tr.width_mm < MIN_GROUND_BRIDGE_WIDTH_MM - 1e-6:
                    errors.append(
                        DrcViolation(
                            "gnd_bridge_width",
                            f"Internal GND bridge width {tr.width_mm} mm < 1.50 mm",
                            measured_mm=tr.width_mm,
                            required_mm=MIN_GROUND_BRIDGE_WIDTH_MM,
                        )
                    )

    if not has_gnd_bridge:
        errors.append(DrcViolation("gnd_bridge", "Missing horizontal internal GND bridge between ESP32_GND_L and ESP32_GND_R"))

    min_banner_w = math.inf
    for bp in board.banner_primitives:
        min_banner_w = min(min_banner_w, bp.width_mm)
        if bp.width_mm < MIN_BANNER_STROKE_WIDTH_MM - 1e-6:
            errors.append(
                DrcViolation(
                    "banner_stroke_width",
                    f"Banner stroke '{bp.label}' width {bp.width_mm} mm < 0.50 mm",
                    measured_mm=bp.width_mm,
                    required_mm=MIN_BANNER_STROKE_WIDTH_MM,
                )
            )

    # 2. Collect all electrical primitives and verify board edge & M3 keepout
    elec_items: list[tuple[str, str, tuple[float, float, float, float, float]]] = []
    for pad in board.pads:
        elec_items.append((pad.net, f"Pad:{pad.name}", pad.to_capsule()))
    for idx, tr in enumerate(board.traces):
        elec_items.append((tr.net, f"Trace:{tr.net}#{idx}", tr.to_capsule()))

    all_copper_items: list[tuple[str, tuple[float, float, float, float, float]]] = [
        (label, cap) for _, label, cap in elec_items
    ]
    for idx, bp in enumerate(board.banner_primitives):
        all_copper_items.append((f"Banner:{bp.label}#{idx}", bp.to_capsule(mirrored=False)))

    for label, (x1, y1, x2, y2, r) in all_copper_items:
        if (
            min(x1, x2) - r < 0.0
            or max(x1, x2) + r > board.width_mm
            or min(y1, y2) - r < 0.0
            or max(y1, y2) + r > board.height_mm
        ):
            errors.append(DrcViolation("board_bounds", f"{label} extends outside board outline"))
        for mh in board.mounting_holes:
            dist_to_hole_center = point_to_segment_dist(mh.x_mm, mh.y_mm, x1, y1, x2, y2) - r
            req_r = max(mh.exclusion_radius_mm, M3_EXCLUSION_RADIUS_MM)
            if dist_to_hole_center < req_r - 1e-6:
                errors.append(
                    DrcViolation(
                        "m3_keepout",
                        f"{label} violates M3 hole {mh.name} exclusion ({dist_to_hole_center:.2f} mm < {req_r:.2f} mm)",
                        measured_mm=dist_to_hole_center,
                        required_mm=req_r,
                    )
                )

    # 3. Pairwise net-to-net clearance (>= 0.70 mm)
    min_net_clearance = math.inf
    n_elec = len(elec_items)
    for i in range(n_elec):
        net_a, label_a, cap_a = elec_items[i]
        for j in range(i + 1, n_elec):
            net_b, label_b, cap_b = elec_items[j]
            if net_a == net_b:
                continue
            clr = capsule_clearance(cap_a, cap_b)
            min_net_clearance = min(min_net_clearance, clr)
            if clr < MIN_NET_CLEARANCE_MM - 1e-6:
                errors.append(
                    DrcViolation(
                        "net_clearance",
                        f"Clearance violation between {label_a} ({net_a}) and {label_b} ({net_b}): {clr:.3f} mm < 0.70 mm",
                        measured_mm=clr,
                        required_mm=MIN_NET_CLEARANCE_MM,
                    )
                )

    # 4. Banner-to-electrical clearance (>= 1.50 mm, tested in both normal and mirrored states)
    min_banner_clearance = math.inf
    for bp in board.banner_primitives:
        for mirrored in (False, True):
            b_cap = bp.to_capsule(mirrored=mirrored, center_x_mm=board.banner_center_x_mm)
            for net_a, label_a, cap_a in elec_items:
                clr = capsule_clearance(b_cap, cap_a)
                min_banner_clearance = min(min_banner_clearance, clr)
                if clr < MIN_BANNER_CLEARANCE_MM - 1e-6:
                    errors.append(
                        DrcViolation(
                            "banner_clearance",
                            f"Banner '{bp.label}' too close to {label_a} ({net_a}): {clr:.3f} mm < 1.50 mm",
                            measured_mm=clr,
                            required_mm=MIN_BANNER_CLEARANCE_MM,
                        )
                    )

    # 5. Graph connectivity per net & strict isolation of ESP32_VIN
    net_to_indices: dict[str, list[int]] = defaultdict(list)
    for idx, (net, _, _) in enumerate(elec_items):
        net_to_indices[net].append(idx)

    pad_indices_by_net: dict[str, list[int]] = defaultdict(list)
    for idx, pad in enumerate(board.pads):
        pad_indices_by_net[pad.net].append(idx)

    connected_nets: dict[str, bool] = {}
    active_nets = ("+VBAT_SW", "GND", "3V3", "I2C_SCL", "I2C_SDA", "TOF_XSHUT", "ESC_L_SIG", "ESC_R_SIG")

    for net in active_nets:
        indices = net_to_indices.get(net, [])
        pad_idxs = pad_indices_by_net.get(net, [])
        if len(pad_idxs) < 2:
            connected_nets[net] = False
            errors.append(DrcViolation("connectivity", f"Net {net} has fewer than 2 pads"))
            continue

        # BFS over same-net primitives where capsule_clearance <= 1e-3
        visited: set[int] = {pad_idxs[0]}
        queue: deque[int] = deque([pad_idxs[0]])
        while queue:
            curr = queue.popleft()
            cap_curr = elec_items[curr][2]
            for nxt in indices:
                if nxt not in visited:
                    if capsule_clearance(cap_curr, elec_items[nxt][2]) <= 1e-3:
                        visited.add(nxt)
                        queue.append(nxt)

        all_pads_reached = all(p_idx in visited for p_idx in pad_idxs)
        connected_nets[net] = all_pads_reached
        if not all_pads_reached:
            errors.append(
                DrcViolation(
                    "connectivity",
                    f"Net {net} is not fully connected into a single component",
                )
            )

    # Verify ESP32_VIN is strictly isolated (1 pad, 0 traces, >= 0.70 mm clearance to all copper)
    vin_pads = [p for p in board.pads if p.name == "ESP32_VIN"]
    vin_traces = [t for t in board.traces if t.net == "ESP32_VIN"]
    vin_isolated = len(vin_pads) == 1 and len(vin_traces) == 0
    if not vin_isolated:
        errors.append(DrcViolation("vin_isolation", "ESP32_VIN must have 0 connected traces"))
    else:
        vin_cap = vin_pads[0].to_capsule()
        for net_a, label_a, cap_a in elec_items:
            if label_a == "Pad:ESP32_VIN":
                continue
            if capsule_clearance(vin_cap, cap_a) < MIN_NET_CLEARANCE_MM - 1e-6:
                vin_isolated = False
                errors.append(DrcViolation("vin_isolation", f"ESP32_VIN shorted or too close to {label_a}"))

    return DrcReport(
        passed=len(errors) == 0,
        errors=errors,
        min_net_clearance_mm=min_net_clearance,
        min_banner_clearance_mm=min_banner_clearance,
        min_signal_width_mm=min_signal_w,
        min_power_width_mm=min_power_w,
        min_banner_stroke_mm=min_banner_w,
        connected_nets=connected_nets,
        vin_isolated=vin_isolated,
        esp32_row_pitch_mm=esp32_row_pitch,
    )
