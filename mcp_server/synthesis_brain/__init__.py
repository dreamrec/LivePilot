"""Synthesis brain — native-synth-aware branch production.

Parallel subsystem to mcp_server.sound_design. Where sound_design reasons
at the block-type level (oscillator / filter / envelope / ...), the
synthesis brain reasons at the native-device level with per-adapter
knowledge of Wavetable / Operator / Analog / Drift / Meld parameter
spaces, modulation graphs, and articulation profiles.

Each adapter implements the SynthAdapter protocol:
  - device_name: the Ableton device name it claims
  - extract_profile(device_parameters): read a SynthProfile from live params
  - propose_branches(profile, target, kernel): emit BranchSeed objects plus
    pre-compiled plans (set_device_parameter / batch_set_parameters steps)

PR9 ships Wavetable and Operator adapters. PR10 adds Analog, Drift, Meld
and render-based timbre extraction on top of ``capture_audio``.

No MCP @tool() decorators in this PR — the subsystem is callable from
Python (Wonder's generate_branch_seeds, composer, etc.). PR12 wires
dedicated MCP tools and does the tool-count metadata sweep in one pass.
"""

from .models import (
    SynthProfile,
    TimbralFingerprint,
    ModulationGraph,
    ArticulationProfile,
    OPAQUE,
    NATIVE,
)
from .adapters import get_adapter, SynthAdapter
from .engine import (
    analyze_synth_patch,
    propose_synth_branches,
    supported_devices,
)

__all__ = [
    "SynthProfile",
    "TimbralFingerprint",
    "ModulationGraph",
    "ArticulationProfile",
    "OPAQUE",
    "NATIVE",
    "SynthAdapter",
    "get_adapter",
    "analyze_synth_patch",
    "propose_synth_branches",
    "supported_devices",
]
