"""Parametric 1-layer (B.Cu) PCB specification for the Bicopter Rail 2-DOF testbed.

All primary coordinates are defined in Top View (millimeters, origin at bottom-left):
- Pads and electrical traces are exported directly in Top View coordinates for B.Cu
  toner transfer (flipping glossy paper face-down onto B.Cu mirrors horizontally,
  matching the underside of through-hole components inserted from the top).
- The artistic copper banner (Anáhuac México emblem + team names) is stored in
  Top View (normal left-to-right reading) and mirrored horizontally only when
  exporting the B.Cu toner transfer mask so that etched copper reads left-to-right.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Pad:
    """Through-hole copper pad with central drill guide."""

    name: str
    net: str
    x_mm: float
    y_mm: float
    shape: str  # "circle" or "oblong"
    major_mm: float  # X dimension (diameter for circle, total width for horizontal oblong)
    minor_mm: float  # Y dimension (diameter for circle, total height for horizontal oblong)
    drill_mm: float
    component: str
    pin_label: str

    def to_capsule(self) -> tuple[float, float, float, float, float]:
        """Return (x1, y1, x2, y2, radius) exact 2D capsule geometry."""
        radius = self.minor_mm / 2.0
        if self.shape == "oblong" and self.major_mm > self.minor_mm:
            half_seg = (self.major_mm - self.minor_mm) / 2.0
            return (self.x_mm - half_seg, self.y_mm, self.x_mm + half_seg, self.y_mm, radius)
        return (self.x_mm, self.y_mm, self.x_mm, self.y_mm, self.major_mm / 2.0)


@dataclass(frozen=True)
class Trace:
    """Straight copper track segment on B.Cu."""

    net: str
    x1_mm: float
    y1_mm: float
    x2_mm: float
    y2_mm: float
    width_mm: float
    is_power_bus: bool = False

    def to_capsule(self) -> tuple[float, float, float, float, float]:
        """Return (x1, y1, x2, y2, radius) exact 2D capsule geometry."""
        return (self.x1_mm, self.y1_mm, self.x2_mm, self.y2_mm, self.width_mm / 2.0)


@dataclass(frozen=True)
class MountingHole:
    """Mechanical M3 mounting hole with copper keepout radius."""

    name: str
    x_mm: float
    y_mm: float
    drill_mm: float = 3.2
    exclusion_radius_mm: float = 6.5


@dataclass(frozen=True)
class BannerPrimitive:
    """Isolated artistic copper stroke (Anáhuac emblem or team member name)."""

    group: str  # "emblem" or "names"
    label: str
    x1_mm: float
    y1_mm: float
    x2_mm: float
    y2_mm: float
    width_mm: float = 0.55

    def to_capsule(
        self,
        mirrored: bool = False,
        center_x_mm: float = 46.0,
    ) -> tuple[float, float, float, float, float]:
        """Return (x1, y1, x2, y2, radius) in normal or horizontally mirrored coordinates."""
        if mirrored:
            mx1 = 2.0 * center_x_mm - self.x1_mm
            mx2 = 2.0 * center_x_mm - self.x2_mm
            return (mx1, self.y1_mm, mx2, self.y2_mm, self.width_mm / 2.0)
        return (self.x1_mm, self.y1_mm, self.x2_mm, self.y2_mm, self.width_mm / 2.0)


@dataclass
class PcbBoard:
    """Complete 1-layer planar PCB specification."""

    width_mm: float = 92.0
    height_mm: float = 88.0
    phenolic_stock_mm: tuple[float, float] = (100.0, 100.0)
    layer: str = "B.Cu"
    jumpers_count: int = 0
    passive_components_count: int = 0
    banner_center_x_mm: float = 46.0
    banner_texts: tuple[str, ...] = (
        "Anáhuac México",
        "Leonardo Monter",
        "Renata Bello",
        "Adrian Ruiz",
        "Alonso Madrigal",
    )
    switch_dims_mm: tuple[float, float, float] = (30.0, 20.0, 20.0)
    pads: list[Pad] = field(default_factory=list)
    traces: list[Trace] = field(default_factory=list)
    mounting_holes: list[MountingHole] = field(default_factory=list)
    banner_primitives: list[BannerPrimitive] = field(default_factory=list)

    def get_pad(self, name: str) -> Pad:
        """Look up a pad by its unique identifier."""
        for pad in self.pads:
            if pad.name == name:
                return pad
        raise KeyError(f"Pad not found: {name}")


# Exact verified 30-pin ESP32 DevKit V1 pinout (top-to-bottom in Top View)
ESP32_LEFT_PINS: tuple[str, ...] = (
    "EN",
    "VP",
    "VN",
    "D34",
    "D35",
    "D32",
    "D33",
    "D25",
    "D26",
    "D27",
    "D14",
    "D12",
    "D13",
    "GND_L",
    "VIN",
)

ESP32_RIGHT_PINS: tuple[str, ...] = (
    "D23",
    "D22",
    "TX0",
    "RX0",
    "D21",
    "D19",
    "D18",
    "D5",
    "TX2",
    "RX2",
    "D4",
    "D2",
    "D15",
    "GND_R",
    "3V3",
)

J_TOF_PINS: tuple[str, ...] = ("SCL", "SDA", "XSHUT", "GND", "3V3")
J_IMU_PINS: tuple[str, ...] = ("SCL", "SDA", "GND", "3V3")

# Minimal vector stroke glyphs on normalized [0..1] x [0..1] grid for copper etching
_GLYPH_STROKES: dict[str, list[tuple[float, float, float, float]]] = {
    "A": [(0.0, 0.0, 0.5, 1.0), (0.5, 1.0, 1.0, 0.0), (0.2, 0.38, 0.8, 0.38)],
    "B": [
        (0.0, 0.0, 0.0, 1.0),
        (0.0, 1.0, 0.8, 1.0),
        (0.8, 1.0, 0.8, 0.52),
        (0.0, 0.52, 0.9, 0.52),
        (0.9, 0.52, 0.9, 0.0),
        (0.9, 0.0, 0.0, 0.0),
    ],
    "C": [(1.0, 0.9, 0.1, 1.0), (0.1, 1.0, 0.0, 0.5), (0.0, 0.5, 0.1, 0.0), (0.1, 0.0, 1.0, 0.1)],
    "D": [
        (0.0, 0.0, 0.0, 1.0),
        (0.0, 1.0, 0.75, 0.9),
        (0.75, 0.9, 1.0, 0.5),
        (1.0, 0.5, 0.75, 0.1),
        (0.75, 0.1, 0.0, 0.0),
    ],
    "E": [(0.0, 0.0, 0.0, 1.0), (0.0, 1.0, 0.95, 1.0), (0.0, 0.5, 0.8, 0.5), (0.0, 0.0, 0.95, 0.0)],
    "G": [
        (0.95, 0.9, 0.0, 1.0),
        (0.0, 1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0),
        (1.0, 0.0, 1.0, 0.48),
        (0.5, 0.48, 1.0, 0.48),
    ],
    "H": [(0.0, 0.0, 0.0, 1.0), (1.0, 0.0, 1.0, 1.0), (0.0, 0.5, 1.0, 0.5)],
    "I": [(0.15, 1.0, 0.85, 1.0), (0.5, 0.0, 0.5, 1.0), (0.15, 0.0, 0.85, 0.0)],
    "L": [(0.0, 1.0, 0.0, 0.0), (0.0, 0.0, 0.95, 0.0)],
    "M": [(0.0, 0.0, 0.0, 1.0), (0.0, 1.0, 0.5, 0.35), (0.5, 0.35, 1.0, 1.0), (1.0, 1.0, 1.0, 0.0)],
    "N": [(0.0, 0.0, 0.0, 1.0), (0.0, 1.0, 1.0, 0.0), (1.0, 0.0, 1.0, 1.0)],
    "O": [(0.0, 0.0, 0.0, 1.0), (0.0, 1.0, 1.0, 1.0), (1.0, 1.0, 1.0, 0.0), (1.0, 0.0, 0.0, 0.0)],
    "R": [
        (0.0, 0.0, 0.0, 1.0),
        (0.0, 1.0, 0.9, 1.0),
        (0.9, 1.0, 0.9, 0.52),
        (0.9, 0.52, 0.0, 0.52),
        (0.35, 0.52, 1.0, 0.0),
    ],
    "S": [
        (0.95, 1.0, 0.0, 1.0),
        (0.0, 1.0, 0.0, 0.52),
        (0.0, 0.52, 0.95, 0.48),
        (0.95, 0.48, 0.95, 0.0),
        (0.95, 0.0, 0.0, 0.0),
    ],
    "T": [(0.0, 1.0, 1.0, 1.0), (0.5, 0.0, 0.5, 1.0)],
    "U": [(0.0, 1.0, 0.0, 0.0), (0.0, 0.0, 1.0, 0.0), (1.0, 0.0, 1.0, 1.0)],
    "X": [(0.0, 0.0, 1.0, 1.0), (0.0, 1.0, 1.0, 0.0)],
    "Z": [(0.0, 1.0, 1.0, 1.0), (1.0, 1.0, 0.0, 0.0), (0.0, 0.0, 1.0, 0.0)],
}


def _normalize_ascii(text: str) -> str:
    replacements = str.maketrans({"á": "A", "é": "E", "í": "I", "ó": "O", "ú": "U", "Á": "A", "É": "E"})
    return text.translate(replacements).upper()


def _render_vector_text(
    text: str,
    label: str,
    group: str,
    center_x_mm: float,
    y_bottom_mm: float,
    char_w_mm: float,
    char_h_mm: float,
    spacing_mm: float,
    stroke_mm: float = 0.55,
) -> list[BannerPrimitive]:
    clean = _normalize_ascii(text)
    total_w = len(clean) * char_w_mm + max(0, len(clean) - 1) * spacing_mm
    start_x = center_x_mm - total_w / 2.0
    primitives: list[BannerPrimitive] = []

    for idx, ch in enumerate(clean):
        if ch == " ":
            continue
        x0 = start_x + idx * (char_w_mm + spacing_mm)
        for sx1, sy1, sx2, sy2 in _GLYPH_STROKES.get(ch, _GLYPH_STROKES["O"]):
            primitives.append(
                BannerPrimitive(
                    group=group,
                    label=label,
                    x1_mm=round(x0 + sx1 * char_w_mm, 3),
                    y1_mm=round(y_bottom_mm + sy1 * char_h_mm, 3),
                    x2_mm=round(x0 + sx2 * char_w_mm, 3),
                    y2_mm=round(y_bottom_mm + sy2 * char_h_mm, 3),
                    width_mm=stroke_mm,
                )
            )
    return primitives


def _build_anahuac_banner(center_x_mm: float = 46.0) -> list[BannerPrimitive]:
    """Build isolated monochromatic Anáhuac México emblem and 4 team member names."""
    primitives: list[BannerPrimitive] = []
    stroke = 0.55  # >= 0.50 mm for ferric chloride resistance

    # Decorative outer banner frame (Y: 57.0 .. 83.0, X: 17.5 .. 74.5)
    bx1, bx2 = 17.5, 74.5
    by1, by2 = 57.0, 83.0
    frame_pts = [(bx1, by1, bx2, by1), (bx2, by1, bx2, by2), (bx2, by2, bx1, by2), (bx1, by2, bx1, by1)]
    for x1, y1, x2, y2 in frame_pts:
        primitives.append(
            BannerPrimitive(group="emblem", label="Anáhuac México", x1_mm=x1, y1_mm=y1, x2_mm=x2, y2_mm=y2, width_mm=0.60)
        )

    # Anáhuac México geometric crest / pinole emblem on left of top banner band (center (24.5, 76.5))
    cx, cy, r = 24.5, 76.5, 3.6
    crest_segments = [
        (cx - r, cy - r, cx + r, cy - r),
        (cx + r, cy - r, cx + r, cy + r),
        (cx + r, cy + r, cx - r, cy + r),
        (cx - r, cy + r, cx - r, cy - r),
        (cx - r, cy - r, cx + r, cy + r),
        (cx - r, cy + r, cx + r, cy - r),
        (cx, cy - r - 0.8, cx, cy + r + 0.8),
        (cx - r - 0.8, cy, cx + r + 0.8, cy),
    ]
    for x1, y1, x2, y2 in crest_segments:
        primitives.append(
            BannerPrimitive(
                group="emblem",
                label="Anáhuac México",
                x1_mm=round(x1, 3),
                y1_mm=round(y1, 3),
                x2_mm=round(x2, 3),
                y2_mm=round(y2, 3),
                width_mm=0.60,
            )
        )

    # University title "ANAHUAC MEXICO"
    primitives.extend(
        _render_vector_text(
            text="ANAHUAC MEXICO",
            label="Anáhuac México",
            group="emblem",
            center_x_mm=51.5,
            y_bottom_mm=74.8,
            char_w_mm=1.85,
            char_h_mm=3.6,
            spacing_mm=0.75,
            stroke_mm=stroke,
        )
    )

    # Team member names in 2x2 balanced layout inside banner frame
    team_layout = [
        ("Leonardo Monter", 32.5, 67.5),
        ("Renata Bello", 60.5, 67.5),
        ("Adrian Ruiz", 32.5, 60.5),
        ("Alonso Madrigal", 60.5, 60.5),
    ]
    for member_name, mx, my in team_layout:
        primitives.extend(
            _render_vector_text(
                text=member_name,
                label=member_name,
                group="names",
                center_x_mm=mx,
                y_bottom_mm=my,
                char_w_mm=1.15,
                char_h_mm=2.5,
                spacing_mm=0.48,
                stroke_mm=stroke,
            )
        )

    return primitives


def build_default_board() -> PcbBoard:
    """Construct the verified 1-layer planar PCB specification."""
    board = PcbBoard()

    # 1. Corner M3 mounting holes (3.2 mm drill, >= 6.5 mm copper exclusion radius)
    board.mounting_holes = [
        MountingHole("M3_BL", 6.0, 6.0, drill_mm=3.2, exclusion_radius_mm=6.5),
        MountingHole("M3_BR", 86.0, 6.0, drill_mm=3.2, exclusion_radius_mm=6.5),
        MountingHole("M3_TL", 6.0, 82.0, drill_mm=3.2, exclusion_radius_mm=6.5),
        MountingHole("M3_TR", 86.0, 82.0, drill_mm=3.2, exclusion_radius_mm=6.5),
    ]

    # 2. ESP32 DevKit V1 (30 pins: 2x15 at 2.54 mm pitch, 25.40 mm row spacing, USB at bottom)
    x_esp_left = 33.30
    x_esp_right = 58.70  # 58.70 - 33.30 == 25.40 mm exact
    y_pin1 = 47.56
    pitch = 2.54

    left_net_map = {
        "D25": "ESC_L_SIG",
        "D26": "ESC_R_SIG",
        "GND_L": "GND",
        "VIN": "ESP32_VIN",
    }
    right_net_map = {
        "D22": "I2C_SCL",
        "D21": "I2C_SDA",
        "D19": "TOF_XSHUT",
        "GND_R": "GND",
        "3V3": "3V3",
    }

    for idx, pin_label in enumerate(ESP32_LEFT_PINS):
        y = round(y_pin1 - idx * pitch, 2)
        net = left_net_map.get(pin_label, f"NC_ESP32_L_{pin_label}")
        pad_name = f"ESP32_{pin_label}"
        board.pads.append(
            Pad(
                name=pad_name,
                net=net,
                x_mm=x_esp_left,
                y_mm=y,
                shape="oblong",
                major_mm=2.40,
                minor_mm=1.76,
                drill_mm=0.90,
                component="ESP32",
                pin_label=pin_label,
            )
        )

    for idx, pin_label in enumerate(ESP32_RIGHT_PINS):
        y = round(y_pin1 - idx * pitch, 2)
        net = right_net_map.get(pin_label, f"NC_ESP32_R_{pin_label}")
        pad_name = f"ESP32_{pin_label}"
        board.pads.append(
            Pad(
                name=pad_name,
                net=net,
                x_mm=x_esp_right,
                y_mm=y,
                shape="oblong",
                major_mm=2.40,
                minor_mm=1.76,
                drill_mm=0.90,
                component="ESP32",
                pin_label=pin_label,
            )
        )

    # 3. Left Zone: Power (+VBAT_SW & GND_PWR) and 2 ESCs (direct solder pads)
    power_pads = [
        ("ESC_L_VBAT", "+VBAT_SW", 10.50, 48.00, 5.20, 1.60, "ESC_L +VBAT"),
        ("ESC_R_VBAT", "+VBAT_SW", 10.50, 36.00, 5.20, 1.60, "ESC_R +VBAT"),
        ("BAT_VBAT_IN", "+VBAT_SW", 10.50, 24.00, 5.20, 1.60, "+VBAT_SW IN"),
        ("ESC_L_GND_PWR", "GND", 18.00, 48.00, 5.20, 1.60, "ESC_L GND PWR"),
        ("ESC_R_GND_PWR", "GND", 18.00, 36.00, 5.20, 1.60, "ESC_R GND PWR"),
        ("BAT_GND_IN", "GND", 18.00, 24.00, 5.20, 1.60, "BAT GND IN"),
        ("ESC_L_GND_SIG", "GND", 25.00, 42.00, 2.60, 1.00, "ESC_L GND SIG"),
        ("ESC_L_SIG", "ESC_L_SIG", 25.00, 33.50, 2.60, 1.00, "ESC_L PWM"),
        ("ESC_R_SIG", "ESC_R_SIG", 25.00, 27.24, 2.60, 1.00, "ESC_R PWM"),
        ("ESC_R_GND_SIG", "GND", 25.00, 20.00, 2.60, 1.00, "ESC_R GND SIG"),
    ]
    for name, net, x, y, diam, drill, label in power_pads:
        board.pads.append(
            Pad(
                name=name,
                net=net,
                x_mm=x,
                y_mm=y,
                shape="circle",
                major_mm=diam,
                minor_mm=diam,
                drill_mm=drill,
                component="PWR_ESC",
                pin_label=label,
            )
        )

    # 4. Right Zone: J_TOF (1x5) and J_IMU (1x4) 2.54 mm headers
    x_tof = 71.00
    y_tof_pin1 = 39.94  # Aligned so SDA (37.40) and XSHUT (34.86) are straight horizontal!
    tof_nets = {
        "SCL": "I2C_SCL",
        "SDA": "I2C_SDA",
        "XSHUT": "TOF_XSHUT",
        "GND": "GND",
        "3V3": "3V3",
    }
    for idx, pin_label in enumerate(J_TOF_PINS):
        y = round(y_tof_pin1 - idx * pitch, 2)
        board.pads.append(
            Pad(
                name=f"J_TOF_{pin_label}",
                net=tof_nets[pin_label],
                x_mm=x_tof,
                y_mm=y,
                shape="oblong",
                major_mm=2.40,
                minor_mm=1.76,
                drill_mm=0.90,
                component="J_TOF",
                pin_label=pin_label,
            )
        )

    x_imu = 82.00
    y_imu_pin1 = 39.94  # Aligned so SCL (39.94) and SDA (37.40) continue straight across!
    imu_nets = {
        "SCL": "I2C_SCL",
        "SDA": "I2C_SDA",
        "GND": "GND",
        "3V3": "3V3",
    }
    for idx, pin_label in enumerate(J_IMU_PINS):
        y = round(y_imu_pin1 - idx * pitch, 2)
        board.pads.append(
            Pad(
                name=f"J_IMU_{pin_label}",
                net=imu_nets[pin_label],
                x_mm=x_imu,
                y_mm=y,
                shape="oblong",
                major_mm=2.40,
                minor_mm=1.76,
                drill_mm=0.90,
                component="J_IMU",
                pin_label=pin_label,
            )
        )

    # 5. Planar 1-Layer Traces (B.Cu)
    board.traces = [
        # +VBAT_SW power bus (>= 4.0 mm)
        Trace("+VBAT_SW", 10.50, 24.00, 10.50, 36.00, width_mm=4.20, is_power_bus=True),
        Trace("+VBAT_SW", 10.50, 36.00, 10.50, 48.00, width_mm=4.20, is_power_bus=True),
        # GND_PWR power bus (>= 4.0 mm) + Star Ground below D26
        Trace("GND", 18.00, 48.00, 18.00, 42.00, width_mm=4.20, is_power_bus=True),
        Trace("GND", 18.00, 42.00, 18.00, 36.00, width_mm=4.20, is_power_bus=True),
        Trace("GND", 18.00, 36.00, 18.00, 24.00, width_mm=4.20, is_power_bus=True),
        Trace("GND", 18.00, 24.00, 18.00, 20.00, width_mm=4.20, is_power_bus=True),
        Trace("GND", 18.00, 20.00, 18.00, 14.54, width_mm=4.20, is_power_bus=True),
        Trace("GND", 18.00, 42.00, 25.00, 42.00, width_mm=4.00, is_power_bus=True),
        Trace("GND", 18.00, 20.00, 25.00, 20.00, width_mm=4.00, is_power_bus=True),
        Trace("GND", 18.00, 14.54, 29.50, 14.54, width_mm=4.20, is_power_bus=True),
        # Star Ground entry into ESP32_GND_L and internal ground bridge under ESP32 (>= 1.5 mm)
        Trace("GND", 29.50, 14.54, 33.30, 14.54, width_mm=1.50, is_power_bus=False),
        Trace("GND", 33.30, 14.54, 58.70, 14.54, width_mm=1.50, is_power_bus=False),
        # Direct ESC PWM signal lines (>= 1.0 mm)
        Trace("ESC_L_SIG", 33.30, 29.78, 28.50, 29.78, width_mm=1.20, is_power_bus=False),
        Trace("ESC_L_SIG", 28.50, 29.78, 25.00, 33.50, width_mm=1.20, is_power_bus=False),
        Trace("ESC_R_SIG", 33.30, 27.24, 25.00, 27.24, width_mm=1.20, is_power_bus=False),
        # Right Zone I2C & ToF signals (>= 1.0 mm, planar horizontal without crossings)
        # I2C_SCL: ESP32_D22 (58.70, 45.02) -> J_TOF_SCL (71.00, 39.94) -> J_IMU_SCL (82.00, 39.94)
        Trace("I2C_SCL", 58.70, 45.02, 63.50, 45.02, width_mm=1.10, is_power_bus=False),
        Trace("I2C_SCL", 63.50, 45.02, 67.00, 39.94, width_mm=1.10, is_power_bus=False),
        Trace("I2C_SCL", 67.00, 39.94, 71.00, 39.94, width_mm=1.10, is_power_bus=False),
        Trace("I2C_SCL", 71.00, 39.94, 82.00, 39.94, width_mm=1.10, is_power_bus=False),
        # I2C_SDA: ESP32_D21 (58.70, 37.40) -> J_TOF_SDA (71.00, 37.40) -> J_IMU_SDA (82.00, 37.40)
        Trace("I2C_SDA", 58.70, 37.40, 71.00, 37.40, width_mm=1.10, is_power_bus=False),
        Trace("I2C_SDA", 71.00, 37.40, 82.00, 37.40, width_mm=1.10, is_power_bus=False),
        # TOF_XSHUT: ESP32_D19 (58.70, 34.86) -> J_TOF_XSHUT (71.00, 34.86)
        Trace("TOF_XSHUT", 58.70, 34.86, 71.00, 34.86, width_mm=1.10, is_power_bus=False),
        # Sensor GND: ESP32_GND_R (58.70, 14.54) -> J_TOF_GND (71.00, 32.32) -> J_IMU_GND (82.00, 34.86)
        Trace("GND", 58.70, 14.54, 63.50, 14.54, width_mm=1.20, is_power_bus=False),
        Trace("GND", 63.50, 14.54, 63.50, 29.50, width_mm=1.20, is_power_bus=False),
        Trace("GND", 63.50, 29.50, 66.32, 32.32, width_mm=1.20, is_power_bus=False),
        Trace("GND", 66.32, 32.32, 71.00, 32.32, width_mm=1.20, is_power_bus=False),
        Trace("GND", 71.00, 32.32, 75.50, 32.32, width_mm=1.20, is_power_bus=False),
        Trace("GND", 75.50, 32.32, 78.00, 34.86, width_mm=1.20, is_power_bus=False),
        Trace("GND", 78.00, 34.86, 82.00, 34.86, width_mm=1.20, is_power_bus=False),
        # Sensor 3V3: ESP32_3V3 (58.70, 12.00) -> J_TOF_3V3 (71.00, 29.78) -> J_IMU_3V3 (82.00, 32.32)
        Trace("3V3", 58.70, 12.00, 66.50, 12.00, width_mm=1.20, is_power_bus=False),
        Trace("3V3", 66.50, 12.00, 66.50, 27.50, width_mm=1.20, is_power_bus=False),
        Trace("3V3", 66.50, 27.50, 68.78, 29.78, width_mm=1.20, is_power_bus=False),
        Trace("3V3", 68.78, 29.78, 71.00, 29.78, width_mm=1.20, is_power_bus=False),
        Trace("3V3", 71.00, 29.78, 77.50, 29.78, width_mm=1.20, is_power_bus=False),
        Trace("3V3", 77.50, 29.78, 80.00, 32.32, width_mm=1.20, is_power_bus=False),
        Trace("3V3", 80.00, 32.32, 82.00, 32.32, width_mm=1.20, is_power_bus=False),
    ]

    # 6. Top Zone: Artistic copper banner (Anáhuac México emblem + 4 team names)
    board.banner_primitives = _build_anahuac_banner(center_x_mm=board.banner_center_x_mm)

    return board
