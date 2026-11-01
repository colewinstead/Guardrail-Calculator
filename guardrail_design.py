"""Established MDOT design data; values preserved from corrected baseline a280080."""

from enum import Enum


class Facility(str, Enum):
    TWO_LANE_TWO_WAY = "two_lane_two_way"
    DIVIDED_HIGHWAY = "divided_highway"


class HazardOffsetSource(str, Enum):
    DIRECT = "direct"
    CLEAR_ZONE = "clearzone"


class SideSlope(str, Enum):
    FLAT = "6:1_or_flatter"
    MODERATE = "5:1_to_4:1"


class ClearZoneSelection(str, Enum):
    MINIMUM = "min"
    MIDPOINT = "mid"
    MAXIMUM = "max"
    CUSTOM = "custom"


class DividedLayout(str, Enum):
    INSIDE = "inside"
    OUTSIDE = "outside"


class PlacementMode(str, Enum):
    STANDALONE = "standalone"
    LANDXML = "landxml"


class ReportStyle(int, Enum):
    SUMMARY = 1
    DETAIL = 2
    COMPLETE = 3


SUPPORTED_SPEEDS = (30, 35, 40, 45, 50, 55, 60, 65, 70)
SUPPORTED_FLARE_RATES = (30, 28, 26, 24, 21, 18, 16, 15, 13, 0)
DESIGN_REFERENCES = {
    "TABLE_9_6_A": "MDOT Roadway Design Manual (2020), Table 9-6-A",
    "TABLE_9_2_A": "MDOT Roadway Design Manual, Table 9-2-A (existing simplified transcription)",
    "DEFAULT_L1_FT": "MDOT Example 9-6-1",
    "DEFAULT_TERMINAL_SECTION_FT": "GR-4 (existing application interpretation)",
}

APP_VERSION = "V8.5"


INCR_GUARDRAIL_FT = 12.5


DEFAULT_L1_FT = 18 + (1.75 / 12.0)          # 18'-1.75" (Example 9-6-1)


DEFAULT_TERMINAL_SECTION_FT = 25.0          # GR-4 shows 25'-0" terminal section


DEFAULT_GATING_FT = 12.5                    # MDOT examples add 12.5' gating portion


TABLE_9_6_A = {
    70: {"LR": [360, 330, 290, 250]},
    65: {"LR": [330, 290, 250, 225]},
    60: {"LR": [300, 250, 210, 200]},
    55: {"LR": [265, 220, 185, 175]},
    50: {"LR": [230, 190, 160, 150]},
    45: {"LR": [195, 160, 135, 125]},
    40: {"LR": [160, 130, 110, 100]},
    35: {"LR": [135, 110, 95, 85]},
    30: {"LR": [110, 90, 80, 70]},
}


TABLE_9_2_A = {
    "40_or_less": {
        "under_750":     {"6:1_or_flatter": (7, 10),  "5:1_to_4:1": (7, 10)},
        "750_1500":      {"6:1_or_flatter": (10, 12), "5:1_to_4:1": (12, 14)},
        "1501_6000":     {"6:1_or_flatter": (12, 14), "5:1_to_4:1": (14, 16)},
        "over_6000":     {"6:1_or_flatter": (14, 16), "5:1_to_4:1": (16, 18)},
    },
    "45_50": {
        "under_750":     {"6:1_or_flatter": (10, 12), "5:1_to_4:1": (12, 14)},
        "750_1500":      {"6:1_or_flatter": (14, 16), "5:1_to_4:1": (16, 20)},
        "1501_6000":     {"6:1_or_flatter": (16, 18), "5:1_to_4:1": (20, 26)},
        "over_6000":     {"6:1_or_flatter": (20, 22), "5:1_to_4:1": (24, 28)},
    },
    "55": {
        "under_750":     {"6:1_or_flatter": (12, 14), "5:1_to_4:1": (14, 18)},
        "750_1500":      {"6:1_or_flatter": (16, 18), "5:1_to_4:1": (20, 24)},
        "1501_6000":     {"6:1_or_flatter": (20, 22), "5:1_to_4:1": (24, 30)},
        "over_6000":     {"6:1_or_flatter": (22, 24), "5:1_to_4:1": (26, 32)},
    },
    "60": {
        "under_750":     {"6:1_or_flatter": (16, 18), "5:1_to_4:1": (20, 24)},
        "750_1500":      {"6:1_or_flatter": (20, 24), "5:1_to_4:1": (26, 32)},
        "1501_6000":     {"6:1_or_flatter": (26, 30), "5:1_to_4:1": (32, 40)},
        "over_6000":     {"6:1_or_flatter": (30, 32), "5:1_to_4:1": (36, 44)},
    },
    "65_70": {
        "under_750":     {"6:1_or_flatter": (18, 20), "5:1_to_4:1": (20, 26)},
        "750_1500":      {"6:1_or_flatter": (24, 26), "5:1_to_4:1": (28, 36)},
        "1501_6000":     {"6:1_or_flatter": (28, 32), "5:1_to_4:1": (34, 42)},
        "over_6000":     {"6:1_or_flatter": (30, 34), "5:1_to_4:1": (38, 46)},
    },
}


LAYERS = {
    "alignment": "GR_ALIGNMENT", "road": "GR_ROAD", "bridge": "GR_BRIDGE",
    "lane": "GR_LANE_LINES", "shoulder": "GR_SHOULDER_FLARE", "normal_shoulder": "GR_NORMAL_SHOULDER",
    "foreslope": "GR_FORESLOPE_W",
    "rail": "GR_GUARDRAIL", "post": "GR_GUARDRAIL_POSTS", "terminal": "GR_TERMINAL", "gating": "GR_GATING",
    "dimension": "GR_DIMENSION", "leader": "GR_LEADERS", "text": "GR_TEXT",
    "traffic": "GR_TRAFFIC_ARROWS",
}

BRIDGE_END_SECTION = DEFAULT_L1_FT
GATING_LENGTH = DEFAULT_GATING_FT
SHOULDER_FLARE_LENGTH = 75.0

SHOULDER_TRANSITION_LENGTH = 150.0

NORMAL_SHOULDER_EXTENSION = 50.0

PATH_TOLERANCE = 0.01  # Maximum sampled chord deviation, in feet.

TEXT_HEIGHT = 2.5

ENGINEERING_TEXT_STYLE = "Engineering Regular"

ENGINEERING_FONT_FILE = "EngineeringRegular.ttf"

SHOULDER_CLEARANCE_BEHIND_RAIL = 3.0

TERMINAL_LATERAL_FLARE = 4.0 + 8.0 / 12.0

TERMINAL_END_LATERAL_FLARE = 2.0

GATING_LATERAL_FLARE = TERMINAL_LATERAL_FLARE - TERMINAL_END_LATERAL_FLARE

TERMINAL_SHOULDER_CLEARANCE = 4.0

GUARDRAIL_POST_SPACING = 6.25
