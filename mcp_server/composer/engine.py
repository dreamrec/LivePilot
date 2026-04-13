"""ComposerEngine — orchestrate prompt → layers → compiled plan.

Pure computation engine. Does NOT call MCP tools directly.
Returns compiled plan dicts that the tool layer (tools.py) executes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .prompt_parser import CompositionIntent, parse_prompt
from .layer_planner import LayerSpec, plan_layers, plan_sections


# ── Result Models ──────────────────────────────────────────────────

@dataclass
class CompositionResult:
    """Result of a full composition run."""

    intent: CompositionIntent = field(default_factory=CompositionIntent)
    layers: list[LayerSpec] = field(default_factory=list)
    sections: list[dict] = field(default_factory=list)
    plan: list[dict] = field(default_factory=list)        # compiled execution steps
    credits_estimated: int = 0
    dry_run: bool = False
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "intent": self.intent.to_dict(),
            "layer_count": len(self.layers),
            "layers": [l.to_dict() for l in self.layers],
            "sections": self.sections,
            "plan_step_count": len(self.plan),
            "plan": self.plan,
            "credits_estimated": self.credits_estimated,
            "dry_run": self.dry_run,
            "warnings": self.warnings,
        }


@dataclass
class AugmentResult:
    """Result of an augmentation run."""

    request: str = ""
    intent: CompositionIntent = field(default_factory=CompositionIntent)
    new_layers: list[LayerSpec] = field(default_factory=list)
    plan: list[dict] = field(default_factory=list)
    credits_estimated: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "request": self.request,
            "intent": self.intent.to_dict(),
            "new_layer_count": len(self.new_layers),
            "new_layers": [l.to_dict() for l in self.new_layers],
            "plan_step_count": len(self.plan),
            "plan": self.plan,
            "credits_estimated": self.credits_estimated,
            "warnings": self.warnings,
        }


# ── Compiled Step Builders ─────────────────────────────────────────

def _compile_set_tempo_step(tempo: int) -> dict:
    """Compile a set_tempo step."""
    return {
        "tool": "set_tempo",
        "params": {"tempo": tempo},
        "description": f"Set tempo to {tempo} BPM",
    }


def _compile_create_track_step(track_index: int, role: str) -> dict:
    """Compile a create_midi_track step."""
    return {
        "tool": "create_midi_track",
        "params": {"index": track_index},
        "description": f"Create MIDI track for {role}",
    }


def _compile_name_track_step(track_index: int, role: str) -> dict:
    """Compile a set_track_name step."""
    return {
        "tool": "set_track_name",
        "params": {"track_index": track_index, "name": role.title()},
        "description": f"Name track: {role.title()}",
    }


def _compile_search_step(layer: LayerSpec) -> dict:
    """Compile a Splice search step."""
    return {
        "tool": "search_samples",
        "params": {
            "query": layer.search_query,
            "source": "splice",
            "max_results": 10,
            **{k: v for k, v in layer.splice_filters.items()
               if k in ("key", "bpm_range", "material_type")},
        },
        "description": f"Search Splice: {layer.search_query}",
        "role": layer.role,
    }


def _compile_download_step(layer: LayerSpec) -> dict:
    """Compile a Splice download step (placeholder — filled at runtime)."""
    return {
        "tool": "_splice_download",
        "params": {"file_hash": "{best_match.file_hash}"},
        "description": f"Download best match for {layer.role}",
        "role": layer.role,
        "conditional": True,  # only if not already downloaded
    }


def _compile_load_sample_step(track_index: int, layer: LayerSpec) -> dict:
    """Compile a load_sample_to_simpler step."""
    return {
        "tool": "load_sample_to_simpler",
        "params": {
            "track_index": track_index,
            "file_path": "{downloaded_path}",
        },
        "description": f"Load sample into Simpler on track {track_index}",
        "role": layer.role,
    }


def _compile_technique_step(track_index: int, layer: LayerSpec) -> dict:
    """Compile a technique application step."""
    return {
        "tool": "_apply_technique",
        "params": {
            "track_index": track_index,
            "technique_id": layer.technique_id,
        },
        "description": f"Apply technique '{layer.technique_id}' on track {track_index}",
        "role": layer.role,
    }


def _compile_processing_steps(track_index: int, layer: LayerSpec) -> list[dict]:
    """Compile device insertion and parameter setting steps."""
    steps: list[dict] = []
    for i, device in enumerate(layer.processing):
        device_name = device.get("name", "")
        steps.append({
            "tool": "insert_device",
            "params": {
                "track_index": track_index,
                "device_name": device_name,
            },
            "description": f"Insert {device_name} on track {track_index}",
            "role": layer.role,
        })
        # Parameter setting
        for param_name, param_value in device.get("params", {}).items():
            steps.append({
                "tool": "set_device_parameter",
                "params": {
                    "track_index": track_index,
                    "device_index": -1,  # last inserted device
                    "parameter_name": param_name,
                    "value": param_value,
                },
                "description": f"Set {device_name} {param_name} = {param_value}",
                "role": layer.role,
            })
    return steps


def _compile_mix_steps(track_index: int, layer: LayerSpec) -> list[dict]:
    """Compile volume and pan steps."""
    steps = []
    steps.append({
        "tool": "set_track_volume",
        "params": {"track_index": track_index, "volume_db": layer.volume_db},
        "description": f"Set {layer.role} volume to {layer.volume_db}dB",
        "role": layer.role,
    })
    if layer.pan != 0.0:
        steps.append({
            "tool": "set_track_pan",
            "params": {"track_index": track_index, "pan": layer.pan},
            "description": f"Set {layer.role} pan to {layer.pan}",
            "role": layer.role,
        })
    return steps


def _compile_arrangement_steps(
    track_index: int,
    layer: LayerSpec,
    sections: list[dict],
) -> list[dict]:
    """Compile arrangement clip creation steps for the layer's sections."""
    steps: list[dict] = []

    for section in sections:
        if section["name"] not in layer.sections:
            continue

        # Check for volume offset in section layer refs (e.g. "drums:-6dB")
        volume_offset_db = 0.0
        for layer_ref in section.get("layers", []):
            parts = layer_ref.split(":")
            if parts[0] == layer.role and len(parts) > 1:
                try:
                    volume_offset_db = float(parts[1].replace("dB", ""))
                except ValueError:
                    pass

        start_bar = section["start_bar"]
        bar_count = section["bars"]

        steps.append({
            "tool": "create_arrangement_clip",
            "params": {
                "track_index": track_index,
                "start_time": start_bar * 4.0,  # bars → beats (4/4)
                "length": bar_count * 4.0,
            },
            "description": f"Create arrangement clip: {layer.role} in {section['name']} "
                           f"(bar {start_bar}, {bar_count} bars)",
            "role": layer.role,
            "section": section["name"],
        })

        # Add volume automation at section boundaries if there's an offset
        if volume_offset_db != 0.0:
            steps.append({
                "tool": "set_arrangement_automation",
                "params": {
                    "track_index": track_index,
                    "parameter_name": "Volume",
                    "time": start_bar * 4.0,
                    "value": layer.volume_db + volume_offset_db,
                },
                "description": f"Automate volume fade: {layer.role} at {volume_offset_db}dB "
                               f"in {section['name']}",
                "role": layer.role,
                "section": section["name"],
            })

    return steps


# ── Engine ─────────────────────────────────────────────────────────

class ComposerEngine:
    """Orchestrates the full composition pipeline.

    Pure computation — returns compiled plan dicts.
    The tool layer (tools.py) handles actual execution.
    """

    def compose(
        self,
        intent: CompositionIntent,
        dry_run: bool = False,
        max_credits: int = 10,
    ) -> CompositionResult:
        """Plan a full multi-layer composition from a CompositionIntent.

        Returns a CompositionResult with compiled execution steps.
        """
        result = CompositionResult(
            intent=intent,
            dry_run=dry_run,
        )

        # Plan layers and sections
        layers = plan_layers(intent)
        sections = plan_sections(intent)
        result.layers = layers
        result.sections = sections

        # Estimate credits needed (1 per non-downloaded layer)
        credits_needed = len(layers)
        result.credits_estimated = credits_needed

        if credits_needed > max_credits:
            result.warnings.append(
                f"Estimated {credits_needed} credits needed, "
                f"but budget is {max_credits}. Some layers may use "
                f"downloaded samples or browser fallback."
            )

        # Compile the execution plan
        plan: list[dict] = []

        # Step 1: Set tempo
        plan.append(_compile_set_tempo_step(intent.tempo))

        # Step 2: Create tracks and layers
        for track_idx, layer in enumerate(layers):
            # Create track
            plan.append(_compile_create_track_step(track_idx, layer.role))
            plan.append(_compile_name_track_step(track_idx, layer.role))

            # Search for sample
            plan.append(_compile_search_step(layer))

            # Download if needed
            plan.append(_compile_download_step(layer))

            # Load into Simpler
            plan.append(_compile_load_sample_step(track_idx, layer))

            # Apply technique
            if layer.technique_id:
                plan.append(_compile_technique_step(track_idx, layer))

            # Insert processing devices
            plan.extend(_compile_processing_steps(track_idx, layer))

            # Set mix levels
            plan.extend(_compile_mix_steps(track_idx, layer))

            # Arrange into sections
            plan.extend(_compile_arrangement_steps(track_idx, layer, sections))

        result.plan = plan
        return result

    def augment(
        self,
        request: str,
        max_credits: int = 3,
        max_layers: int = 3,
    ) -> AugmentResult:
        """Plan augmentation layers to add to an existing session.

        Parses the request as a composition prompt but limits to max_layers.
        """
        intent = parse_prompt(request)

        # Override layer count to respect max_layers
        intent.layer_count = min(intent.layer_count or max_layers, max_layers)

        result = AugmentResult(
            request=request,
            intent=intent,
        )

        # Plan layers
        layers = plan_layers(intent)
        # Limit to max_layers
        layers = layers[:max_layers]
        result.new_layers = layers

        # Estimate credits
        result.credits_estimated = len(layers)

        if result.credits_estimated > max_credits:
            result.warnings.append(
                f"Estimated {result.credits_estimated} credits needed, "
                f"but budget is {max_credits}."
            )

        # Compile augmentation plan
        # Track indices start from a placeholder — the tool layer will
        # determine the actual track offset at runtime
        plan: list[dict] = []
        for offset, layer in enumerate(layers):
            track_placeholder = f"{{existing_track_count}} + {offset}"

            plan.append({
                "tool": "create_midi_track",
                "params": {"index": -1},  # append at end
                "description": f"Create MIDI track for {layer.role}",
                "role": layer.role,
            })

            plan.append({
                "tool": "set_track_name",
                "params": {"track_index": -1, "name": f"+ {layer.role.title()}"},
                "description": f"Name new track: + {layer.role.title()}",
                "role": layer.role,
            })

            plan.append(_compile_search_step(layer))
            plan.append(_compile_download_step(layer))

            plan.append({
                "tool": "load_sample_to_simpler",
                "params": {"track_index": -1, "file_path": "{downloaded_path}"},
                "description": f"Load sample into Simpler",
                "role": layer.role,
            })

            if layer.technique_id:
                plan.append({
                    "tool": "_apply_technique",
                    "params": {"track_index": -1, "technique_id": layer.technique_id},
                    "description": f"Apply technique '{layer.technique_id}'",
                    "role": layer.role,
                })

            for device in layer.processing:
                device_name = device.get("name", "")
                plan.append({
                    "tool": "insert_device",
                    "params": {"track_index": -1, "device_name": device_name},
                    "description": f"Insert {device_name}",
                    "role": layer.role,
                })
                for param_name, param_value in device.get("params", {}).items():
                    plan.append({
                        "tool": "set_device_parameter",
                        "params": {
                            "track_index": -1,
                            "device_index": -1,
                            "parameter_name": param_name,
                            "value": param_value,
                        },
                        "description": f"Set {device_name} {param_name} = {param_value}",
                        "role": layer.role,
                    })

            plan.append({
                "tool": "set_track_volume",
                "params": {"track_index": -1, "volume_db": layer.volume_db},
                "description": f"Set {layer.role} volume to {layer.volume_db}dB",
                "role": layer.role,
            })
            if layer.pan != 0.0:
                plan.append({
                    "tool": "set_track_pan",
                    "params": {"track_index": -1, "pan": layer.pan},
                    "description": f"Set {layer.role} pan to {layer.pan}",
                    "role": layer.role,
                })

        result.plan = plan
        return result

    def get_plan(
        self,
        intent: CompositionIntent,
    ) -> dict:
        """Dry run — return the full composition plan without execution."""
        result = self.compose(intent, dry_run=True, max_credits=0)
        return result.to_dict()
