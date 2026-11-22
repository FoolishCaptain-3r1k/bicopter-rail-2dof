"""Parametric enclosure specification coupled directly to hardware/pcb_spec.py (DRY)."""

from __future__ import annotations

from dataclasses import dataclass

from hardware.pcb_spec import PcbBoard, build_default_board


@dataclass(frozen=True)
class BoundingBox3D:
    """Axis-aligned 3D keep-out / bounding envelope in enclosure coordinates (mm)."""

    name: str
    x_min: float
    y_min: float
    z_min: float
    x_max: float
    y_max: float
    z_max: float

    @property
    def size_xyz(self) -> tuple[float, float, float]:
        return (self.x_max - self.x_min, self.y_max - self.y_min, self.z_max - self.z_min)

    @property
    def center_xyz(self) -> tuple[float, float, float]:
        return (
            (self.x_min + self.x_max) / 2.0,
            (self.y_min + self.y_max) / 2.0,
            (self.z_min + self.z_max) / 2.0,
        )


@dataclass(frozen=True)
class EnclosureSpec:
    """Complete parametric 2-piece console enclosure coupled to PcbBoard geometry."""

    board_w_mm: float
    board_h_mm: float
    pcb_thickness_mm: float
    wall_mm: float
    floor_mm: float
    fit_tolerance_mm: float
    standoff_height_mm: float
    standoff_od_mm: float
    standoff_drill_mm: float
    pcb_m3_holes: tuple[tuple[str, float, float, float], ...]
    closure_bosses_xy: tuple[tuple[float, float], ...]
    x_outer_min: float
    x_outer_max: float
    y_outer_min: float
    y_outer_max: float
    split_z_mm: float
    lip_height_mm: float
    front_step_y_end: float
    front_step_z_outer: float
    slope_y_end: float
    top_deck_z_outer: float
    switch_hole_diam_mm: float
    switch_center_xy: tuple[float, float]
    usb_slot_x_range: tuple[float, float]
    usb_slot_z_range: tuple[float, float]
    rear_grommets: tuple[tuple[str, float, float, float], ...]  # (name, x, z, diam)
    pcb_keepout: BoundingBox3D
    esp32_keepout: BoundingBox3D
    left_esc_keepout: BoundingBox3D
    switch_keepout: BoundingBox3D


def build_enclosure_spec(board: PcbBoard | None = None) -> EnclosureSpec:
    """Derive enclosure dimensions and keep-outs directly from hardware.pcb_spec.PcbBoard."""
    if board is None:
        board = build_default_board()

    wall = 2.40
    floor = 2.40
    fit_tol = 0.30
    standoff_h = 6.00
    pcb_thick = 1.60

    pcb_z_bot = floor + standoff_h  # 8.40 mm
    pcb_z_top = pcb_z_bot + pcb_thick  # 10.00 mm

    # Derive ESP32 footprint directly from board.pads (zero duplicated coordinates)
    esp_pads = [p for p in board.pads if p.component == "ESP32"]
    esp_x_min = min(p.x_mm for p in esp_pads) - 1.80  # 31.50 mm
    esp_x_max = max(p.x_mm for p in esp_pads) + 1.80  # 60.50 mm
    esp_y_min = 0.0  # USB connector sits at front edge Y=0
    esp_y_max = max(p.y_mm for p in esp_pads) + 4.00  # 51.56 mm

    esp32_keepout = BoundingBox3D(
        name="ESP32_KEEP_OUT",
        x_min=round(esp_x_min, 3),
        y_min=round(esp_y_min, 3),
        z_min=round(pcb_z_top, 3),
        x_max=round(esp_x_max, 3),
        y_max=round(esp_y_max, 3),
        z_max=round(pcb_z_top + 24.0, 3),  # 34.00 mm
    )

    # Derive Left ESC keep-out from PWR_ESC pads (+24 mm height above PCB)
    esc_pads = [p for p in board.pads if p.component == "PWR_ESC"]
    esc_x_min = max(1.0, min(p.x_mm for p in esc_pads) - 6.0)
    esc_x_max = max(p.x_mm for p in esc_pads) + 4.5
    esc_y_min = min(p.y_mm for p in esc_pads) - 6.0
    esc_y_max = max(p.y_mm for p in esc_pads) + 4.0

    left_esc_keepout = BoundingBox3D(
        name="LEFT_ESC_KEEP_OUT",
        x_min=round(esc_x_min, 3),
        y_min=round(esc_y_min, 3),
        z_min=round(pcb_z_top, 3),
        x_max=round(esc_x_max, 3),
        y_max=round(esc_y_max, 3),
        z_max=round(pcb_z_top + 24.0, 3),
    )

    pcb_keepout = BoundingBox3D(
        name="PCB_KEEP_OUT",
        x_min=0.0,
        y_min=0.0,
        z_min=round(pcb_z_bot, 3),
        x_max=board.width_mm,
        y_max=board.height_mm,
        z_max=round(pcb_z_top, 3),
    )

    # Outer envelope: 5.6 mm inner lateral margin + 2.4 mm wall = 8.0 mm around PCB (108 x 104 mm)
    lat_margin = 5.60
    x_outer_min = -(lat_margin + wall)  # -8.00 mm
    x_outer_max = board.width_mm + lat_margin + wall  # 100.00 mm
    y_outer_min = -(lat_margin + wall)  # -8.00 mm
    y_outer_max = board.height_mm + lat_margin + wall  # 96.00 mm

    pcb_m3 = tuple((mh.name, mh.x_mm, mh.y_mm, mh.drill_mm) for mh in board.mounting_holes)

    # 4 corner M3 closure bosses outside PCB envelope
    closure_bosses = (
        (-3.20, -3.20),
        (board.width_mm + 3.20, -3.20),
        (-3.20, board.height_mm + 3.20),
        (board.width_mm + 3.20, board.height_mm + 3.20),
    )

    # Toggle switch (30x20x24 mm keep-out incl. lower screw terminals) in upper-rear deck
    sw_w, sw_d, sw_h = board.switch_dims_mm[0], board.switch_dims_mm[1], 24.0
    sw_cx = board.banner_center_x_mm  # 46.0 mm
    sw_cy = 73.00  # Rear half: Y in [63.0, 83.0], strictly behind ESP32 (Y<=51.56)
    top_deck_z_outer = 61.50
    roof_inner_z = top_deck_z_outer - wall  # 59.10 mm

    switch_keepout = BoundingBox3D(
        name="SWITCH_KEEP_OUT",
        x_min=round(sw_cx - sw_w / 2.0, 3),
        y_min=round(sw_cy - sw_d / 2.0, 3),
        z_min=round(roof_inner_z - sw_h, 3),  # 35.10 mm (> 34.00 mm ESP32 top!)
        x_max=round(sw_cx + sw_w / 2.0, 3),
        y_max=round(sw_cy + sw_d / 2.0, 3),
        z_max=round(roof_inner_z, 3),  # 59.10 mm
    )

    # USB slot centered on ESP32 X centerline
    esp_cx = (esp_x_min + esp_x_max) / 2.0  # 46.0 mm

    rear_grommets = (
        ("lipo_2s_in", 14.0, 26.0, 9.0),
        ("motor_3ph_out", 46.0, 26.0, 10.0),
        ("i2c_sensors_out", 76.0, 26.0, 8.0),
    )

    return EnclosureSpec(
        board_w_mm=board.width_mm,
        board_h_mm=board.height_mm,
        pcb_thickness_mm=pcb_thick,
        wall_mm=wall,
        floor_mm=floor,
        fit_tolerance_mm=fit_tol,
        standoff_height_mm=standoff_h,
        standoff_od_mm=6.80,
        standoff_drill_mm=2.80,
        pcb_m3_holes=pcb_m3,
        closure_bosses_xy=closure_bosses,
        x_outer_min=x_outer_min,
        x_outer_max=x_outer_max,
        y_outer_min=y_outer_min,
        y_outer_max=y_outer_max,
        split_z_mm=16.00,
        lip_height_mm=3.00,
        front_step_y_end=14.00,
        front_step_z_outer=38.50,
        slope_y_end=56.00,
        top_deck_z_outer=top_deck_z_outer,
        switch_hole_diam_mm=12.20,
        switch_center_xy=(sw_cx, sw_cy),
        usb_slot_x_range=(esp_cx - 7.0, esp_cx + 7.0),
        usb_slot_z_range=(pcb_z_bot + 0.6, 26.0),
        rear_grommets=rear_grommets,
        pcb_keepout=pcb_keepout,
        esp32_keepout=esp32_keepout,
        left_esc_keepout=left_esc_keepout,
        switch_keepout=switch_keepout,
    )
