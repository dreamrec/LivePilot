"""ComposerEngine — orchestrate prompt → layers → executable plan.

Pure computation engine. Does NOT call MCP tools directly.
Returns compiled plan dicts that the tool layer (tools.py) executes.

Executability contract (Phase 7 rewrite)
----------------------------------------
The returned plan contains only REAL tool calls with concrete params. It
never emits:
  - pseudo-tools like _agent_pick_best_sample or _apply_technique
  - placeholder strings like "{downloaded_path}"
  - invalid sentinels like device_index: -1 or track_index: -1
  - hardcoded clip_slot_index: 0 for tracks with no source clip

Samples are resolved at PLAN time via sample_resolver.resolve_sample_for_layer.
Layers that don't resolve to a concrete local file are dropped from `plan`
but kept in `layers` for descriptive output, and the unresolved role is
named in `warnings`. Processing chains use step_id + $from_step bindings
to bind set_device_parameter.device_index to the actual inserted device
position returned by insert_device.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .prompt_parser import CompositionIntent, parse_prompt
from .layer_planner import LayerSpec, plan_layers, plan_sections
from .sample_resolver import resolve_sample_for_layer


# ── Result Models ──────────────────────────────────────────────────

@dataclass
class CompositionResult:
    """Result of a full composition run."""

    intent: CompositionIntent = field(default_factory=CompositionIntent)
    layers: list[LayerSpec] = field(default_factory=list)
    sections: list[dict] = field(default_factory=list)
    plan: list[dict] = field(default_factory=list)        # executable steps only
    credits_estimated: int = 0
    dry_run: bool = False
    warnings: list[str] = field(default_factory=list)
    resolved_samples: dict = field(default_factory=dict)  # role -> local_path

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
            "resolved_samples": self.resolved_samples,
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
    resolved_samples: dict = field(default_factory=dict)

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
            "resolved_samples": self.resolved_samples,
        }


# ── Step builders ──────────────────────────────────────────────────

def _step_set_tempo(tempo: int) -> dict:
    return {
        "tool": "set_tempo",
        "params": {"tempo": tempo},
        "description": f"Set tempo to {tempo} BPM",
    }


def _step_create_midi_track(track_index: int, role: str, step_id: str) -> dict:
    return {
        "step_id": step_id,
        "tool": "create_midi_track",
        "params": {"index": track_index},
        "description": f"Create MIDI track for {role}",
        "role": role,
    }


def _step_set_track_name(track_index: int, role: str) -> dict:
    return {
        "tool": "set_track_name",
        "params": {"track_index": track_index, "name": role.title()},
        "description": f"Name track: {role.title()}",
        "role": role,
    }


def _step_load_sample_to_simpler(track_index: int, layer: LayerSpec, file_path: str) -> dict:
    return {
        "tool": "load_sample_to_simpler",
        "params": {"track_index": track_index, "file_path": file_path},
        "description": f"Load sample into Simpler on track {track_index}",
        "backend": "mcp_tool",
        "role": layer.role,
    }


def _step_suggest_technique(track_index: int, layer: LayerSpec) -> dict:
    """Real tool — returns technique recipe for the agent to interpret.

    Not a pseudo-tool: suggest_sample_technique is a registered MCP tool.
    The agent reads the returned recipe and applies the steps manually; we
    don't try to auto-apply here because the recipe is open-ended.
    """
    return {
        "tool": "suggest_sample_technique",
        "params": {"technique_id": layer.technique_id},
        "description": f"Get technique recipe '{layer.technique_id}' for track {track_index}",
        "role": layer.role,
    }


def _processing_steps_with_binding(
    track_index: int,
    layer: LayerSpec,
    layer_idx: int,
) -> list[dict]:
    """Build insert_device + set_device_parameter pairs using step_id bindings.

    Each insert_device carries a unique step_id like 'layer_0_dev_1'. The
    following set_device_parameter steps bind their device_index param to
    that id via $from_step — the async router resolves it to the real
    device index returned by insert_device at runtime.
    """
    steps: list[dict] = []
    for dev_idx, device in enumerate(layer.processing):
        device_name = device.get("name", "")
        if not device_name:
            continue
        step_id = f"layer_{layer_idx}_dev_{dev_idx}"
        steps.append({
            "step_id": step_id,
            "tool": "insert_device",
            "params": {
                "track_index": track_index,
                "device_name": device_name,
            },
            "description": f"Insert {device_name} on track {track_index}",
            "role": layer.role,
        })
        for param_name, param_value in device.get("params", {}).items():
            steps.append({
                "tool": "set_device_parameter",
                "params": {
                    "track_index": track_index,
                    "device_index": {"$from_step": step_id, "path": "device_index"},
                    "parameter_name": param_name,
                    "value": param_value,
                },
                "description": f"Set {device_name} {param_name} = {param_value}",
                "role": layer.role,
            })
    return steps


def _mix_steps(track_index: int, layer: LayerSpec) -> list[dict]:
    steps: list[dict] = []
    # dB to linear with 0dB -> 0.85 convention (Ableton native scale)
    linear = max(0.0, min(1.0, 10 ** (layer.volume_db / 20.0) * 0.85))
    steps.append({
        "tool": "set_track_volume",
        "params": {"track_index": track_index, "volume": round(linear, 3)},
        "description": f"Set {layer.role} volume to {layer.volume_db}dB ({linear:.3f} linear)",
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


def _arrangement_steps(
    track_index: int,
    layer: LayerSpec,
    sections: list[dict],
) -> list[dict]:
    """Arrangement clips — only for tracks that already have a source clip.

    Skipped entirely for newly-created Simpler tracks (they have no source
    clip to tile into the arrangement). The composer can be extended later
    to also emit create_clip steps first, but that's out of scope here.
    """
    # For now we skip arrangement emission from the composer since the tracks
    # we create are empty Simplers — create_arrangement_clip with
    # clip_slot_index=0 is invalid and would fail at runtime. Leaving this as
    # a stub so the descriptive `sections` field is still populated upstream.
    return []


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
        search_roots: Optional[list] = None,
    ) -> CompositionResult:
        """Plan a full multi-layer composition from a CompositionIntent.

        Returns a CompositionResult where `plan` contains only executable
        steps. Unresolved layers are kept in `layers` (descriptive) but
        dropped from `plan`, with warnings naming the unresolved roles.
        """
        result = CompositionResult(intent=intent, dry_run=dry_run)

        layers = plan_layers(intent)
        sections = plan_sections(intent)
        result.layers = layers
        result.sections = sections
        result.credits_estimated = len(layers)

        if result.credits_estimated > max_credits:
            result.warnings.append(
                f"Estimated {result.credits_estimated} credits needed, "
                f"but budget is {max_credits}. Some layers may use "
                f"downloaded samples or browser fallback."
            )

        plan: list[dict] = []

        # Step 1: Tempo
        plan.append(_step_set_tempo(intent.tempo))

        # Step 2: Per-layer build, resolving samples at plan time
        for layer_idx, layer in enumerate(layers):
            track_index = layer_idx

            file_path, source = resolve_sample_for_layer(layer, search_roots=search_roots)
            if not file_path:
                # Layer is descriptive-only. Skip emission, warn.
                result.warnings.append(
                    f"Unresolved sample for layer '{layer.role}' "
                    f"(query: {layer.search_query!r}). Dropped from plan."
                )
                continue

            result.resolved_samples[layer.role] = file_path

            track_step_id = f"layer_{layer_idx}_track"
            plan.append(_step_create_midi_track(track_index, layer.role, track_step_id))
            plan.append(_step_set_track_name(track_index, layer.role))

            plan.append(_step_load_sample_to_simpler(track_index, layer, file_path))

            if layer.technique_id:
                plan.append(_step_suggest_technique(track_index, layer))

            plan.extend(_processing_steps_with_binding(track_index, layer, layer_idx))
            plan.extend(_mix_steps(track_index, layer))
            plan.extend(_arrangement_steps(track_index, layer, sections))

        result.plan = plan
        return result

    def augment(
        self,
        request: str,
        max_credits: int = 3,
        max_layers: int = 3,
        search_roots: Optional[list] = None,
    ) -> AugmentResult:
        """Plan augmentation layers to add to an existing session.

        Like compose(), resolves samples at plan time and drops unresolved
        layers. Since the actual track count isn't known at plan time, this
        uses track_index: -1 only for create_midi_track (where the Remote
        Script interprets -1 as append-at-end) and then binds later steps
        to the actual created track via $from_step — same pattern as the
        device_index binding in compose().
        """
        intent = parse_prompt(request)
        intent.layer_count = min(intent.layer_count or max_layers, max_layers)

        result = AugmentResult(request=request, intent=intent)

        layers = plan_layers(intent)[:max_layers]
        result.new_layers = layers
        result.credits_estimated = len(layers)

        if result.credits_estimated > max_credits:
            result.warnings.append(
                f"Estimated {result.credits_estimated} credits needed, "
                f"but budget is {max_credits}."
            )

        plan: list[dict] = []

        for layer_idx, layer in enumerate(layers):
            file_path, _source = resolve_sample_for_layer(layer, search_roots=search_roots)
            if not file_path:
                result.warnings.append(
                    f"Unresolved sample for layer '{layer.role}' "
                    f"(query: {layer.search_query!r}). Dropped from plan."
                )
                continue

            result.resolved_samples[layer.role] = file_path

            # We don't know the absolute track index yet. create_midi_track's
            # result carries "index" (via Remote Script) — later steps bind
            # track_index to that via $from_step. The composer tools layer
            # passes existing_track_count in via a hint when available.
            track_step_id = f"aug_layer_{layer_idx}_track"
            plan.append({
                "step_id": track_step_id,
                "tool": "create_midi_track",
                "params": {"index": -1},  # append at end — Remote Script convention
                "description": f"Create MIDI track for {layer.role}",
                "role": layer.role,
            })

            track_ref = {"$from_step": track_step_id, "path": "index"}

            plan.append({
                "tool": "set_track_name",
                "params": {"track_index": track_ref, "name": f"+ {layer.role.title()}"},
                "description": f"Name new track: + {layer.role.title()}",
                "role": layer.role,
            })

            plan.append({
                "tool": "load_sample_to_simpler",
                "params": {"track_index": track_ref, "file_path": file_path},
                "description": f"Load sample into Simpler",
                "backend": "mcp_tool",
                "role": layer.role,
            })

            if layer.technique_id:
                plan.append({
                    "tool": "suggest_sample_technique",
                    "params": {"technique_id": layer.technique_id},
                    "description": f"Get technique recipe '{layer.technique_id}'",
                    "role": layer.role,
                })

            for dev_idx, device in enumerate(layer.processing):
                device_name = device.get("name", "")
                if not device_name:
                    continue
                dev_step_id = f"aug_layer_{layer_idx}_dev_{dev_idx}"
                plan.append({
                    "step_id": dev_step_id,
                    "tool": "insert_device",
                    "params": {"track_index": track_ref, "device_name": device_name},
                    "description": f"Insert {device_name}",
                    "role": layer.role,
                })
                for param_name, param_value in device.get("params", {}).items():
                    plan.append({
                        "tool": "set_device_parameter",
                        "params": {
                            "track_index": track_ref,
                            "device_index": {"$from_step": dev_step_id, "path": "device_index"},
                            "parameter_name": param_name,
                            "value": param_value,
                        },
                        "description": f"Set {device_name} {param_name} = {param_value}",
                        "role": layer.role,
                    })

            linear = max(0.0, min(1.0, 10 ** (layer.volume_db / 20.0) * 0.85))
            plan.append({
                "tool": "set_track_volume",
                "params": {"track_index": track_ref, "volume": round(linear, 3)},
                "description": f"Set {layer.role} volume to {layer.volume_db}dB",
                "role": layer.role,
            })
            if layer.pan != 0.0:
                plan.append({
                    "tool": "set_track_pan",
                    "params": {"track_index": track_ref, "pan": layer.pan},
                    "description": f"Set {layer.role} pan to {layer.pan}",
                    "role": layer.role,
                })

        result.plan = plan
        return result

    def get_plan(
        self,
        intent: CompositionIntent,
        search_roots: Optional[list] = None,
    ) -> dict:
        """Dry run — return the full composition plan without execution.

        Passes search_roots through to compose() so the dry-run accurately
        reflects which layers would resolve.
        """
        result = self.compose(intent, dry_run=True, max_credits=0, search_roots=search_roots)
        return result.to_dict()
