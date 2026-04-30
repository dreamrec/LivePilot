#!/usr/bin/env python3
"""
Markdown → YAML overlay converter for the packs namespace (Phase 3).

Handles the MECHANICAL conversions:
- cross-workflows.md → ~15 cross_pack_workflow YAMLs
- demo JSON sidecars → ~104 demo_project YAMLs
- pack markdown lesson subsections → lesson YAMLs (where present)

Pack-identity YAMLs are written by sonnet conversion agents (in parallel),
not by this script — pack identity content is too free-form for reliable
mechanical extraction.

Output: ~/.livepilot/atlas-overlays/packs/{identity,demo_projects,lessons,cross_workflows}/<slug>.yaml
"""
import sys, json, re, yaml
from pathlib import Path
from collections import OrderedDict

REPO_ROOT = Path("/Users/visansilviugeorge/Desktop/DREAM AI/LivePilot")
PRIVATE_PACKS_DIR = Path("/Users/visansilviugeorge/Desktop/DREAM AI/livepilot-dreamrec-extensions/skills/livepilot-packs/references")
OUT_ROOT = Path.home() / ".livepilot" / "atlas-overlays" / "packs"
DEMO_SIDECARS = OUT_ROOT / "_demo_parses"
PRESET_SIDECARS = OUT_ROOT / "_preset_parses"

# Ensure output dirs
for sub in ("identity", "demo_projects", "lessons", "cross_workflows"):
    (OUT_ROOT / sub).mkdir(parents=True, exist_ok=True)


class BlockDumper(yaml.SafeDumper):
    pass

def represent_str(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)
BlockDumper.add_representer(str, represent_str)


def slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[\s\W]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def write_yaml(path: Path, data: dict):
    with path.open("w") as f:
        yaml.dump(data, f, Dumper=BlockDumper, sort_keys=False,
                  default_flow_style=False, width=200, allow_unicode=True)


# ============================================================================
# 1. CROSS-WORKFLOWS — parse cross-workflows.md → emit cross_pack_workflow YAMLs
# ============================================================================

CROSS_WORKFLOWS_MD = PRIVATE_PACKS_DIR / "cross-workflows.md"


def parse_cross_workflows():
    """Parse cross-workflows.md → list of workflow dicts."""
    text = CROSS_WORKFLOWS_MD.read_text()
    # Each workflow is a `## <N>. <slug>` header followed by content until next ##
    workflows = []
    sections = re.split(r"^## (\d+)\. ([\w\-]+)\s*$", text, flags=re.MULTILINE)
    # sections is [intro, num1, slug1, body1, num2, slug2, body2, ...]
    for i in range(1, len(sections), 3):
        if i + 2 >= len(sections):
            break
        num, slug, body = sections[i], sections[i + 1], sections[i + 2]
        wf = {"slug": slug, "body": body.strip()}

        # Extract structured fields with regex
        for field, pattern in [
            ("packs_used", r"\*\*Packs:\*\*\s*([^\n]+)"),
            ("devices_used", r"\*\*Devices:\*\*\s*([^\n]+)"),
            ("aesthetic", r"\*\*Aesthetic:\*\*\s*([^\n]+)"),
        ]:
            m = re.search(pattern, body)
            if m:
                wf[field] = m.group(1).strip()

        # Signal flow — find "**Signal flow:**" block
        m = re.search(r"\*\*Signal flow:\*\*(.*?)(?=\n\n|\*\*When to reach)", body, re.DOTALL)
        if m:
            wf["signal_flow"] = m.group(1).strip()

        # When to reach
        m = re.search(r"\*\*When to reach:\*\*\s*([^\n]+(?:\n(?!\*\*).+)*)", body)
        if m:
            wf["when_to_reach"] = m.group(1).strip()

        # Gotcha
        m = re.search(r"\*\*Gotcha:\*\*\s*([^\n]+(?:\n(?!\*\*).+)*)", body)
        if m:
            wf["gotcha"] = m.group(1).strip()

        # Hidden gem
        m = re.search(r"\*\*Hidden gem:\*\*\s*([^\n]+(?:\n(?!\*\*).+)*)", body)
        if m:
            wf["hidden_gem"] = m.group(1).strip()

        # Avoid
        m = re.search(r"\*\*Avoid:\*\*\s*([^\n]+(?:\n(?!\*\*).+)*)", body)
        if m:
            wf["avoid"] = m.group(1).strip()

        workflows.append(wf)
    return workflows


def cross_workflow_to_yaml(wf):
    """Convert parsed workflow → YAML overlay dict matching schema."""
    eid = wf["slug"].replace("-", "_")
    name = wf["slug"].replace("-", " ").title()

    # Extract packs from "Packs:" line
    packs_used = []
    if wf.get("packs_used"):
        packs_used = [p.strip("` ") for p in re.findall(r"`([^`]+)`", wf["packs_used"])]

    # Extract devices similarly
    devices_used = []
    if wf.get("devices_used"):
        devices_used = [d.strip("` ") for d in re.findall(r"`([^`]+)`", wf["devices_used"])]

    # Build tags from packs + slug terms + aesthetic words
    tag_set = set()
    tag_set.add("cross_pack_workflow")
    tag_set.add("cross-pack-workflow")
    tag_set.add(eid)
    for p in packs_used:
        tag_set.add(p.replace("-", "_"))
        tag_set.add(p)
    # Aesthetic-derived tags (very simple — full enrichment happens in Phase 4)
    aesthetic_text = (wf.get("aesthetic") or "").lower()
    for keyword in ["dub_techno", "dub-techno", "ambient", "drone", "boc", "boards_of_canada",
                    "bibio", "burial", "henke", "monolake", "footwork", "trap", "boom_bap",
                    "jdilla", "dilla", "barbieri", "davachi", "basinski", "reich", "mica_levi",
                    "reznor", "ross", "no_input_mixer", "granular", "spectral", "feedback",
                    "iftah", "modular", "eurorack", "microtonal", "vocal", "vocoder"]:
        if keyword.replace("_", " ") in aesthetic_text or keyword in aesthetic_text:
            tag_set.add(keyword)

    body = OrderedDict()
    body["entity_id"] = eid
    body["entity_type"] = "cross_pack_workflow"
    body["name"] = name
    body["description"] = wf.get("aesthetic", name)
    body["tags"] = sorted(tag_set)
    body["requires_box"] = None
    body["packs_used"] = packs_used
    body["devices_used"] = devices_used
    body["aesthetic"] = wf.get("aesthetic", "")
    body["signal_flow"] = wf.get("signal_flow", "")
    body["when_to_reach"] = wf.get("when_to_reach", "")
    if wf.get("gotcha"):
        body["gotcha"] = wf["gotcha"]
    if wf.get("hidden_gem"):
        body["hidden_gem"] = wf["hidden_gem"]
    if wf.get("avoid"):
        body["avoid"] = wf["avoid"]
    body["sources"] = [f"cross-workflows.md §{wf['slug']}"]
    return body


# ============================================================================
# 2. DEMO JSON SIDECARS → demo_project YAMLs
# ============================================================================

def demo_sidecar_to_yaml(sidecar_path: Path):
    """Convert a demo JSON sidecar → demo_project YAML overlay."""
    data = json.loads(sidecar_path.read_text())
    # Filename: <pack-slug>__<demo-slug>.json
    fname = sidecar_path.stem
    if "__" in fname:
        pack_slug, demo_slug = fname.split("__", 1)
    else:
        pack_slug = "unknown"
        demo_slug = fname

    eid = f"{pack_slug}__{demo_slug}".replace("-", "_")[:80]  # unique within namespace

    # Display name from sidecar
    display_name = data.get("name", demo_slug)

    # Pull production-meaningful fields from sidecar
    bpm = data.get("bpm")
    scale = data.get("scale") or {}
    time_sig = data.get("time_signature")

    # Track summary
    tracks = data.get("tracks", [])
    track_count = len(tracks)
    track_names = [t.get("name") for t in tracks if t.get("name")][:20]
    midi_count = sum(1 for t in tracks if t.get("type") == "MidiTrack")
    audio_count = sum(1 for t in tracks if t.get("type") == "AudioTrack")
    return_count = sum(1 for t in tracks if t.get("type") == "ReturnTrack")
    group_count = sum(1 for t in tracks if t.get("type") == "GroupTrack")

    # All device classes used
    device_classes = []
    for t in tracks:
        for d in (t.get("devices") or []):
            device_classes.append(d.get("class", ""))
    from collections import Counter
    class_counts = Counter(c for c in device_classes if c)

    # Tags: pack slug + slug variants + bpm bucket + device classes
    tag_set = set()
    tag_set.add("demo_project")
    tag_set.add("demo-project")
    tag_set.add(pack_slug)
    tag_set.add(pack_slug.replace("_", "-"))
    tag_set.add(pack_slug.replace("-", "_"))
    tag_set.add(f"parent_pack_{pack_slug.replace('-', '_')}")
    if bpm:
        bpm_int = int(bpm)
        if bpm_int < 90:
            tag_set.add("slow_tempo")
        elif bpm_int < 110:
            tag_set.add("mid_tempo_low")
        elif bpm_int < 130:
            tag_set.add("mid_tempo_high")
        else:
            tag_set.add("fast_tempo")
        tag_set.add(f"bpm_{bpm_int}")
    if scale.get("name"):
        tag_set.add(f"scale_{slugify(str(scale['name']))}")
    for cls, _n in class_counts.most_common(8):
        if cls:
            tag_set.add(slugify(cls))

    body = OrderedDict()
    body["entity_id"] = eid
    body["entity_type"] = "demo_project"
    body["name"] = display_name
    body["description"] = (
        f"Demo project from the {pack_slug.replace('-', ' ')} pack. "
        f"BPM {int(bpm) if bpm else 'auto'}, "
        f"{midi_count} MIDI + {audio_count} audio + {return_count} return + {group_count} group tracks. "
        f"Devices: {', '.join(c for c, _ in class_counts.most_common(5))}."
    )
    body["tags"] = sorted(tag_set)
    body["requires_box"] = None
    body["parent_pack"] = pack_slug
    body["file_path"] = data.get("file", "")
    body["bpm"] = bpm
    body["scale_root"] = scale.get("root_note")
    body["scale_name"] = scale.get("name")
    body["time_signature"] = time_sig
    body["track_count"] = track_count
    body["track_breakdown"] = {
        "midi": midi_count,
        "audio": audio_count,
        "return": return_count,
        "group": group_count,
    }
    body["track_names"] = track_names
    body["device_class_counts"] = dict(class_counts.most_common(15))
    body["scenes"] = data.get("scenes") or []
    body["sources"] = [f"als-parse: {data.get('file', '')}"]
    return body


# ============================================================================
# Main run
# ============================================================================

def main():
    # 1. Cross-workflows
    print("=== CROSS-WORKFLOW CONVERSION ===")
    workflows = parse_cross_workflows()
    cw_count = 0
    for wf in workflows:
        yaml_data = cross_workflow_to_yaml(wf)
        out_path = OUT_ROOT / "cross_workflows" / f"{wf['slug']}.yaml"
        write_yaml(out_path, dict(yaml_data))
        cw_count += 1
    print(f"  {cw_count} cross_pack_workflow YAMLs written")

    # 2. Demo sidecars
    print()
    print("=== DEMO SIDECAR CONVERSION ===")
    demo_count = 0
    failed_demos = 0
    for sidecar in sorted(DEMO_SIDECARS.glob("*.json")):
        try:
            yaml_data = demo_sidecar_to_yaml(sidecar)
            out_name = f"{yaml_data['entity_id']}.yaml"
            out_path = OUT_ROOT / "demo_projects" / out_name
            write_yaml(out_path, dict(yaml_data))
            demo_count += 1
        except Exception as e:
            failed_demos += 1
            print(f"  FAIL {sidecar.name}: {e}")
    print(f"  {demo_count} demo_project YAMLs written ({failed_demos} failed)")

    # 3. Aggregate report
    print()
    print(f"=== TOTAL ===")
    print(f"  cross_workflows: {cw_count}")
    print(f"  demo_projects:   {demo_count}")
    print(f"  identity:        (deferred to sonnet conversion agents)")
    print(f"  lessons:         (next phase — extracted from pack markdowns)")
    print()
    print(f"  Output root: {OUT_ROOT}")


if __name__ == "__main__":
    main()
