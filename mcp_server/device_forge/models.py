"""Device Forge data models — specs for generated M4L devices."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class DeviceType(Enum):
    """M4L device types with binary format metadata."""

    AUDIO_EFFECT = ("aaaa", 7, "Max Audio Effect", ("plugin~", "plugout~"))
    MIDI_EFFECT = ("mmmm", 1, "Max MIDI Effect", ("midiin", "midiout"))
    INSTRUMENT = ("iiii", 2, "Max Instrument", ("midiin", "plugout~"))
    MIDI_GENERATOR = ("nagg", 3, "Max MIDI Generator", ("midiout",))
    MIDI_TRANSFORMATION = ("natt", 4, "Max MIDI Transformation", ("midiin", "midiout"))

    def __init__(self, ampf: str, meta: int, title: str, io: tuple):
        self._ampf = ampf.encode("ascii")
        self._meta = meta
        self._title = title
        self._io = io

    @property
    def ampf_marker(self) -> bytes:
        return self._ampf

    @property
    def meta_value(self) -> int:
        return self._meta

    @property
    def title(self) -> str:
        return self._title

    @property
    def required_io(self) -> tuple:
        return self._io


# Parameter unit styles matching Live's enum
UNIT_STYLE_INT = 0
UNIT_STYLE_FLOAT = 1
UNIT_STYLE_TIME = 2
UNIT_STYLE_HERTZ = 3
UNIT_STYLE_DB = 4
UNIT_STYLE_PERCENT = 5
UNIT_STYLE_PAN = 6
UNIT_STYLE_SEMITONES = 7


@dataclass
class GenExprParam:
    """A gen~ parameter exposed to Ableton as a live.dial."""

    name: str
    default: float = 0.5
    min_val: float = 0.0
    max_val: float = 1.0
    unit_style: int = UNIT_STYLE_FLOAT
    exponent: float = 1.0  # 1.0 = linear

    def to_genexpr(self) -> str:
        """Generate the Param declaration for gen~ codebox."""
        return f"Param {self.name}({self.default});"

    def to_live_dial_json(self, obj_id: str, rect: list[float]) -> dict:
        """Generate the JSON for a live.dial box wired to this parameter."""
        return {
            "box": {
                "id": obj_id,
                "maxclass": "live.dial",
                "numinlets": 1,
                "numoutlets": 2,
                "outlettype": ["", "float"],
                "parameter_enable": 1,
                "patching_rect": rect,
                "presentation": 1,
                "presentation_rect": rect,
                "saved_attribute_attributes": {
                    "valueof": {
                        "parameter_longname": self.name,
                        "parameter_shortname": self.name[:7],
                        "parameter_type": 0,
                        "parameter_mmin": self.min_val,
                        "parameter_mmax": self.max_val,
                        "parameter_unitstyle": self.unit_style,
                        "parameter_initial_enable": 1,
                        "parameter_initial": [self.default],
                        "parameter_exponent": self.exponent,
                    }
                },
                "varname": self.name,
            }
        }


@dataclass
class GenExprTemplate:
    """A reusable gen~ DSP building block."""

    template_id: str
    name: str
    description: str
    category: str  # chaos, delay, distortion, filter, modulation, synthesis, texture, utility
    code: str  # GenExpr source code
    params: list[GenExprParam] = field(default_factory=list)
    num_inputs: int = 1
    num_outputs: int = 1

    def to_dict(self) -> dict:
        """Summary dict — does NOT expose raw code."""
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "params": [p.name for p in self.params],
            "num_inputs": self.num_inputs,
            "num_outputs": self.num_outputs,
        }


@dataclass
class DeviceSpec:
    """Complete specification for a generated M4L device."""

    name: str
    device_type: DeviceType
    gen_code: str  # GenExpr source for the gen~ codebox
    description: str = ""
    params: list[GenExprParam] = field(default_factory=list)
    width: int = 300
    height: int = 100
    tags: str = "livepilot generated"

    @property
    def safe_filename(self) -> str:
        """Filesystem-safe .amxd filename."""
        clean = re.sub(r"[^a-zA-Z0-9_ ]", "", self.name)
        return clean.strip().replace(" ", "_") + ".amxd"
