# LivePilot Bug Tracker

Living list of bugs + follow-ups captured during the deep audit + Dabrye-Core creative session (2026-04-17, session HEAD `16f3bfc` / release v1.10.6).

Bugs are categorized by surface:

- **A** = LivePilot server / Remote Script / LOM gaps
- **B** = Analyzers / critics (false positives, misattribution)
- **C** = Audit follow-ups from the fresh-audit pass
- **D** = Session-specific / creative tracking

Status flags: `🔴 open` · `🟡 in-progress` · `🟢 fixed` · `⚪️ wontfix / by-design`

---

## A. Server / LOM gaps

### BUG-A1 · `🟢 fixed (Batch 2)` · insert_device returned "Unknown command type"

**Reproducer:** `insert_device(track_index=3, device_name="Auto Filter", position=-1)` returned:
```
[NOT_FOUND] Unknown command type: insert_device (while running 'insert_device')
```

**Root cause (diagnosed):** NOT a missing handler — it already existed in `remote_script/LivePilot/devices.py` at `@register("insert_device")`. The bug was **install drift**: the installed Remote Script at `~/Music/Ableton/User Library/Remote Scripts/LivePilot/` was dated Apr 11 (before the handler was added Apr 14). Ableton loads Remote Scripts once at process start and caches them in `sys.modules`, so source-tree edits never reached the running Live process.

**Fix (landed):**
1. `remote_script/LivePilot/router.py` — `ping` response now embeds `remote_script_version` and the full `commands` list so stale installs are detectable.
2. `mcp_server/server.py::_check_remote_script_version()` — called in the lifespan context after connect; logs a loud warning if the installed version doesn't match the MCP server version ("Run 'npx livepilot --install' and restart Ableton Live").
3. Reinstalled the Remote Script at `~/Music/Ableton/User Library/Remote Scripts/LivePilot/` (devices.py 22KB→30KB, `version_detect.py` added, `clips.py` now contains `set_clip_pitch`). User must restart Ableton Live for the new code to take effect.
4. Regression test `test_bug_a1_ping_embeds_remote_script_version_and_commands`.

**Impact:** Future drift surfaces as a clear on-connect warning instead of mysterious "Unknown command type" errors mid-session.

---

### BUG-A2 · `🟡 fixable via M4L bridge` (was: wontfix) · Simpler Warp mode not exposed via Python LOM

**Reproducer:** `get_hidden_parameters(track=5, device=0)` returns all 83 Simpler params — no "Warp" / "Warp Mode". Python's Remote Script ControlSurface API doesn't surface it.

**Key insight:** Ableton's LOM has two tiers. Python-Remote-Script sees only the automatable parameter surface. **Max for Live's JavaScript LiveAPI can reach deeper model objects** (e.g. `SimplerDevice.sample.*`) where Warp actually lives. The existing `livepilot_bridge.js` already uses this pattern for `get_simpler_slices` and `replace_simpler_sample` — so the infrastructure is proven.

**Impact:** Today, user must click Warp in Simpler's Sample tab manually. Blocks automatic tempo-sync when loading samples.

**Fix path (recommended — Option 1: extend the M4L bridge):**

Add a new bridge command `simpler_set_warp` to `m4l_device/livepilot_bridge.js`:
```javascript
function cmd_simpler_set_warp(args) {
    // args: [track_index, device_index, warp_on (0/1), warp_mode (0..6)]
    var track_idx = parseInt(args[0]);
    var device_idx = parseInt(args[1]);
    var warp_on = parseInt(args[2]);
    var warp_mode = parseInt(args[3]);
    var path = "live_set tracks " + track_idx +
               " devices " + device_idx + " sample";
    cursor_a.goto(path);
    cursor_a.set("warping", warp_on);
    if (warp_on && warp_mode >= 0) {
        cursor_a.set("warp_mode", warp_mode);
    }
    send_response({ok: true, warping: warp_on, warp_mode: warp_mode});
}
```
Plus register in the `dispatch()` switch. Then a Python wrapper in `mcp_server/m4l_bridge.py`
(following the `replace_simpler_sample` pattern) and a `@mcp.tool` in `mcp_server/sample_engine/tools.py`.
Estimated: ~30 minutes work + .amxd re-freeze (per the `feedback_amxd_freeze_drift` memory).

**Fallback paths if `SimplerDevice.sample.warping` isn't accessible via Max JS:**

- **Option 2: Resample-and-replace pipeline** — create temp audio track → load sample as audio clip → enable warp via `set_clip_warp_mode` → consolidate to pre-warped .wav → `replace_simpler_sample` with new path → delete temp track. Automatable today with existing tools, but creates disk artifacts and is slower.
- **Option 3: Drum Rack wrapper** — wrap the sample in a Drum Rack chain (chain clips respect warp). Loses Simpler-specific ADSR/glide surface.
- **Option 4: Use Sampler instead of Simpler** — Live's bigger sampler may expose more params to LOM. Worth probing in a test session.
- **Option 5: Status quo** — 1 click in Simpler's Sample tab. Reliable, 2 seconds of user action.

**Dependency:** Bridge-side bump to `livepilot_bridge.js` requires .amxd re-freeze + version-string sync (per `feedback_amxd_freeze_drift`).

**UX polish (independent of the fix):** When we detect a tempo mismatch between Simpler sample and session — filename `<BPM>bpm` vs `tempo` — emit a friendly warning: "Simpler has a 86 BPM sample in a 90 BPM session. Either run `simpler_set_warp(warp_on=1, warp_mode=6)` or click Warp in the Sample tab."

---

### BUG-A3 · `🟡 likely fixable via M4L bridge` (was: wontfix) · Compressor sidechain INPUT ROUTING not programmable

**Reproducer:** `get_device_parameters(track=1, device=1)` on a Compressor returns `S/C On` parameter but no "Audio From" / input-routing source parameter.

**Impact:** Can't set up a sidechain duck fully programmatically. We can enable `S/C On` and the EQ, but the source track must be selected manually in the Compressor's routing dropdown.

**Same LOM-layer logic as BUG-A2:** Python's Remote Script only sees automatable parameters. Sidechain routing in Live 12 is typically exposed as a LiveAPI property (not an automatable parameter) on a device's routing descriptor. Max JS LiveAPI should reach it.

**Probe path to add in `livepilot_bridge.js`:**
```javascript
function cmd_compressor_set_sidechain(args) {
    // args: [track_index, device_index, source_type, source_channel]
    // source_type example: "Audio In", "Ext. In", "No Input", or another track's output
    // source_channel: "Post FX", "Pre FX", "Post Mixer" typically
    var path = "live_set tracks " + args[0] + " devices " + args[1];
    cursor_a.goto(path);

    // Modern Live Compressor exposes routing via these properties:
    // - sidechain_input_routing_type
    // - sidechain_input_routing_channel
    // Check availability first:
    try {
        cursor_a.set("sidechain_input_routing_type", args[2]);
        cursor_a.set("sidechain_input_routing_channel", args[3]);
        send_response({ok: true, sidechain: {type: args[2], channel: args[3]}});
    } catch(e) {
        send_response({error: "sidechain routing not accessible: " + e.message});
    }
}
```

**Fallback if not accessible:** Use the existing `set_track_routing` pattern (which DOES work for tracks) as a model and see if a `set_device_sidechain_routing` command can be generalized.

**Dependency:** Same `.amxd` re-freeze + version-string sync as BUG-A2.

---

### BUG-A4 · `🟢 fixed (Batch 2)` · get_clip_info missing audio-clip pitch offset

**Reproducer:** `get_clip_info(track=6, clip=0)` on the Splice audio clip returned:
```json
{"warping": true, "warp_mode": 4, "name": "...D#min", ...}
```
No `pitch_coarse` / `pitch_fine` / `gain` fields.

**Fix (landed) — `remote_script/LivePilot/clips.py::get_clip_info`:**
```python
if clip.is_audio_clip:
    result["warping"] = clip.warping
    result["warp_mode"] = clip.warp_mode
    for attr in ("pitch_coarse", "pitch_fine", "gain"):
        try:
            result[attr] = getattr(clip, attr)
        except AttributeError:
            pass   # some Live builds omit these on fresh clips
```
Regression tests: `test_bug_a4_get_clip_info_exposes_audio_pitch_and_gain` and `test_bug_a4_midi_clips_do_not_report_pitch_fields` (in `tests/test_remote_script_contracts.py`).

---

### BUG-A5 · `🟢 fixed (Batch 2)` · No programmatic way to set audio-clip pitch offset

**Fix (landed):** New `set_clip_pitch(ctx, track_index, clip_index, coarse=None, fine=None, gain=None)` MCP tool in `mcp_server/tools/clips.py` plus matching `@register("set_clip_pitch")` handler in `remote_script/LivePilot/clips.py`. Audio-only; MIDI clips raise ValueError. Ranges enforced: coarse −48..+48 semitones, fine −50..+50 cents, gain 0..1.

**Registry/docs synced:** tool count 320→321, `remote_commands.py` allowlist, `tool-catalog.md`, `test_tools_contract.py`, and the full release-checklist doc sweep.

Regression tests: `test_bug_a5_set_clip_pitch_writes_coarse_and_fine`, `test_bug_a5_set_clip_pitch_rejects_midi_clips`, `test_bug_a5_set_clip_pitch_requires_at_least_one_param`, `test_bug_a5_set_clip_pitch_rejects_out_of_range_coarse`.

**Unblocks:** BUG-D1 — automatic "transpose −1 semi to fix D#min sample in Dm session" correction now possible. Re-run the Dabrye D#min Splice clip experiment once Ableton is restarted to pick up the new Remote Script.

---

## B. Analyzers / critics

### BUG-B1 · `🟡 tuning needed` · detect_role_conflicts false positive on DRUMS + PERC

**Reproducer:** Session has tracks 0 "DRUMS" (Boom Bap Kit) and 4 "PERC" (Percussion Core Kit). `detect_role_conflicts` returns:
```json
{"role": "drums", "tracks": [0, 4], "severity": 0.5,
 "recommendation": "Layer drum parts into one Drum Rack or pan them apart"}
```

**Why it's wrong:** In hip-hop / Dabrye-core / Dilla / lo-fi, **intentional drum + perc layering** is the core aesthetic — not a conflict. The critic's heuristic treats any two drum-role tracks as competing, regardless of genre context.

**Fix direction:** In `mcp_server/tools/_composition_engine/critics.py` (or the pure engine module), gate drum-conflict severity by:
- Genre inference (if style tactics include "hip-hop", reduce severity)
- Pan separation (already done? If DRUMS center + PERC pan 0.25, severity should drop)
- Frequency separation check (kick-heavy vs hi-hat-heavy? check Drum Rack chain distributions)

**Impact:** Low (annoyance, not broken). But degrades trust in the critic for hip-hop users.

---

### BUG-B2 · `🟢 fixed (Batch 4)` · analyze_harmony mislabeled iv turnaround chord

**Reproducer:** RHODES clip beat 13.5 pitches `[G3, A#3, D4, F4, A4]` returned `{"chord_name": "D chord", ...}` instead of `Gm7` (= iv7 in Dm).

**Root cause:** `chord_name()` in `_theory_engine.py` only matched EXACT interval tuples in `CHORD_PATTERNS`. On miss, it returned `NOTE_NAMES[pcs[0]]` — the *numerically lowest pitch class*, not the bass note. Since `pcs_sorted = [2, 5, 7, 9, 10]`, `pcs[0] = 2` = D, so the chord was labeled "D chord".

**Fix (landed in `mcp_server/tools/_theory_engine.py::chord_name`):**
Four-pass chord identification:
1. Exact `CHORD_PATTERNS` match with bass-note-preferred root selection
2. Subset match → partial chord labeled with `(no X)` annotation
3. Superset match → extended chord labeled with `(add X)` annotation
4. Final fallback names the bass pitch (not the numerically lowest pc)

BUG-B2 input `[G3, Bb3, D4, F4, A4]` now returns **"G-minor seventh (add 9)"** (pass 3: G-Bb-D-F = minor seventh pattern + A as added 9/11 tension).

**Impact:** Medium — now closed.

---

### BUG-B3 · `🟡 tuning needed` · get_track_meters level vs left/right desync

**Reproducer:**
1. Stop playback
2. Call `get_track_meters(include_stereo=true)`
3. Some tracks return `{level: 0.81, left: 0, right: 0}`

**Why it's confusing:** `level` reports peak-hold (last loud moment), while `left`/`right` report instantaneous post-fader channel levels. On stopped playback they decouple.

**Fix direction:** One of:
- Document the semantic (cheap)
- Return `peak_hold` and `current_left` / `current_right` as distinct fields
- Suppress `left`/`right` when `is_playing` is false
- Or sync all readings to one sampling moment

**Impact:** Low. Creates diagnostic false alarms when debugging "is my filter killing the signal?" during stopped playback.

---

### BUG-B4 · `🔴 open` · Auto Filter LFO Amount display scale mismatch

**Reproducer:** `batch_set_parameters` on Auto Filter with `{"name_or_index": "LFO Amount", "value": 0.25}` returns:
```json
{"name": "LFO Amount", "value": 0.25, "value_string": "6.2 %"}
```

**Why it's confusing:** The parameter VALUE is 0.25 (normalized 0-1) but the VALUE_STRING says "6.2 %". Existing Auto Filter instances (pre-session) had e.g. `LFO Amount: 0.42` with no `%` in the readout visible via get_device_parameters' earlier form. Unclear if:
- 0.25 actual value corresponds to a 6.2% depth in display (scaling factor present)
- value_string display is buggy
- The parameter interpretation changed between Auto Filter v1 → AutoFilter2

**Fix direction:** Document the mapping between normalized parameter values and their human-readable displays. The value_string IS the source of truth for the user — make sure docs reflect that "LFO Amount 0.25 = 6.2% depth".

**Impact:** Low (display-only), but makes automation recipes hard to reason about without testing.

---

### BUG-B5 · `🟢 fixed (Batch 4)` · analyze_harmony chord naming on incomplete chords

**Reproducer:** Pad Lush clip 0 "Intro Wash" pitches `[D3, F3, C4]` returned `{"chord_name": "C chord", ...}` instead of `Dm7(no5)`.

**Root cause:** Same `chord_name()` fallback bug as BUG-B2. Pitch classes `{0, 2, 5}` (C, D, F) sorted numerically puts C first (pc 0), so the fallback returned "C chord".

**Fix (landed with BUG-B2 in Batch 4):** Subset-match pass now catches partial chords. D (bass, pc 2) → intervals `{0, 3, 10}` → subset of minor-seventh pattern `{0, 3, 7, 10}` → returns **"D-minor seventh (no 5)"**.

Regression tests (all in `tests/test_theory_engine.py::TestChordName`):
- `test_bug_b2_gm7_with_added_tension_rooted_on_bass`
- `test_bug_b5_dm7_no5_rooted_on_bass_not_c`
- `test_partial_minor_triad_still_rooted_on_bass`
- `test_major_triad_with_added_ninth`
- `test_exact_match_still_wins_over_subset_guess`
- `test_empty_pitches_returns_unknown`

**Impact:** Medium — now closed. Composition critics get correct chord names on pad/sustain clips that drop the fifth.

---

### BUG-B6 · `🟡 design limitation` · detect_stuckness ignores current session state

**Reproducer:** `detect_stuckness()` returns `{"confidence": 0, "level": "flowing", "signals": [], "diagnosis": ""}` even though:
- `detect_repetition_fatigue` reports `fatigue_level: 0.93` with 8 motif overuse issues
- `analyze_mix` flags `support_too_loud` (Texture track)
- No clip automation in any section (arrangement flatness signal)

**Why it's limiting:** `detect_stuckness` only analyzes the action ledger (user's recent clicks/undos), not current session state critic output. When a user just opened a project or made no recent changes, stuckness will always report "flowing" regardless of actual session health.

**Fix direction:** Extend `detect_stuckness` to merge action-ledger signals with current-state critic signals. Weight them: ledger-based signals (active user-is-stuck behavior) count heavier than state-based signals (project-is-stuck shape). Add `state_fatigue_score` to the output.

**Impact:** Medium. Rescue / Wonder Mode routing depends on stuckness detection. When fatigue is 0.93 but stuckness is 0, Wonder Mode would never auto-trigger.

---

### BUG-B7 · `🔴 open` · get_motif_graph returns 90KB payload — exceeds inline limits

**Reproducer:** `get_motif_graph()` on a 10-track session with 49 clips returns a 90,430-char JSON (Handler system wrote it to disk because it exceeded token limits).

**Why it's a bug:** No pagination, no limit parameter. Every motif with its occurrence details is included — for larger sessions this blows through context and tool-result limits.

**Fix direction:** Add `limit` and `offset` parameters (default limit = 50 motifs). Add `summary_only` mode that returns motif IDs + scores without occurrence arrays.

**Impact:** Medium. Makes the tool unusable on real production sessions.

---

### BUG-B8 · `🔴 open` · rank_hook_candidates returns duplicate "motif_unknown" hooks

**Reproducer:** `rank_hook_candidates(limit=5)` returns entries like:
```json
[
  {"hook_id": "track_10-vox_lch_...", "location": "10-VOX_LCH_..."},
  {"hook_id": "motif_unknown", "location": ""},
  {"hook_id": "motif_unknown", "location": ""},
  {"hook_id": "motif_unknown", "location": ""},
  {"hook_id": "motif_unknown", "location": ""}
]
```

**Why it's wrong:** Four motif-based hooks all have the same `hook_id` ("motif_unknown") and empty `location`. The motif IDs from `get_motif_graph` (motif_000, motif_001, etc.) aren't propagating to hook candidates — they're being collapsed to a generic "unknown" label.

**Fix direction:** In the hook-ranking engine (likely in `mcp_server/hook_hunter/`), when iterating motif hook candidates, preserve `motif_id` from the source motif and populate `location` with the track/clip origin.

**Impact:** Medium. Hook development workflows can't address specific motifs when all are labeled "unknown".

---

### BUG-B9 · `🔴 open` · Auto Filter vs Auto Filter Legacy parameter scale mismatch

**Reproducer:** Bass track (track 6) has device "Auto Filter Legacy" (class `AutoFilter`) with parameters:
- `Frequency`: min 20, max 135 (Ableton's internal 20-135 index, NOT normalized)
- `LFO Amount`: min 0, max 30 (NOT normalized 0-1)
- `Env. Modulation`: min -127, max 127
- `Resonance`: min 0, max 1.25 (NOT 0-1)

Compare to the newer "Auto Filter" (class `AutoFilter2`) which uses 0-1 normalized everywhere.

**Why it's a bug:** Tools that assume 0-1 parameter ranges (automation recipes, LFO recipes, filter sweeps) will drastically misconfigure Auto Filter Legacy. Setting `Frequency = 0.75` on legacy gets clamped to 20 (the minimum of 20-135 range) → filter closes completely → track goes silent.

**Fix direction:**
1. In `atlas_search` / `atlas_device_info`, tag `class_name == "AutoFilter"` (legacy) as having non-normalized params
2. Automation-recipe compiler should read `min`/`max` from `get_device_parameters` and scale curves accordingly, not assume 0-1
3. Also applies to Ableton's older **Dynamic Tube, Vocoder, Compressor I, Gate** — all pre-2010 devices with absolute units

**Impact:** High on mixed-vintage sessions. Silent in most new projects that use modern devices, but existing templates / older projects will misbehave.

---

### BUG-B10 · `🔴 open` · build_song_brain identity_core is lazy fallback

**Reproducer:** `build_song_brain()` on a session with 10 named tracks ("Pad Lush", "Glitch Chops", "Atmo FX", etc.), clear D minor key, 119 BPM, named scenes ("Intro Dust" → "Sun Peak") returns:
```json
{"identity_core": "Dominant texture: drums", "identity_confidence": 0.47}
```

**Why it's weak:** The engine defaults to "Dominant texture: drums" because drum tracks have the most notes. But the user's intent is clearly melodic/harmonic (Pad Lush is the most-named track with 43 arrangement clips, vocal hook is the Splice feature). Low confidence (0.47) suggests the engine knows it's unsure.

**Fix direction:** When confidence < 0.6, the identity engine should fall back to:
1. Most-featured track by clip count OR arrangement presence
2. Most-named section / most repeated motif
3. Explicit name in scene 0 ("Intro Dust" → likely "dust-toned")
4. Combine: tempo + key + primary-role description ("D minor 119 BPM electronic with vocal hook lead")

**Impact:** Medium. Song identity feeds downstream engines; weak identity = weak reasoning.

---

### BUG-B11 · `🟢 fixed (commit 7142319)` · SongBrain section_purposes internal inconsistency

**Reproducer:** `build_song_brain()` returns section "Deep Flow" with:
```json
{"emotional_intent": "payoff", "is_payoff": false}
```

**Why it's wrong:** A section labeled `emotional_intent: "payoff"` should have `is_payoff: true` by definition — that's what the label *means*. Having `is_payoff: false` when the intent IS payoff is a clear internal contradiction.

**Fix direction:** After labeling `emotional_intent`, derive `is_payoff` as `emotional_intent == "payoff"`. Single source of truth.

**Impact:** Medium. `payoff_targets` field returns `[]` in the same response while Deep Flow is labeled payoff — suggests downstream logic uses `is_payoff` not `emotional_intent`, creating silent disagreement.

---

### BUG-B12 · `🟢 fixed (commit 7142319)` · build_song_brain includes empty 8th section

**Reproducer:** `build_song_brain()` section_purposes includes:
```json
{"section_id": "", "label": "", "emotional_intent": "contrast", "energy_level": 0, "is_payoff": false}
```

**Why it's wrong:** The session has a trailing empty scene 7 (no name, no clips). Song brain builds a "section" for it with empty string ID/label and energy 0, pollutes the energy_arc, and skews section_purpose counts.

**Fix direction:** Filter sections where `name == ""` AND no clips across tracks. Empty scenes aren't sections.

**Impact:** Low-medium. Pollutes the energy_arc `[0.7, 0.9, 0.9, 0.5, 0.6, 0.9, 0.4, 0]` — that trailing 0 throws off "front-loaded / back-loaded" heuristics.

---

### BUG-B13 · `🔴 open` · energy_shape description mismatches arc

**Reproducer:** `explain_song_identity()` returns:
```json
{"energy_shape": "front-loaded — peaks early"}
```
But the actual `energy_arc` is `[0.7, 0.9, 0.9, 0.5, 0.6, 0.9, 0.4, 0]` — peaks occur at positions 1, 2, AND 5. Position 5 ("Sun Peak") is 62% through the arrangement, not "early."

**Why it's wrong:** The classifier likely checks "is the first third above average?" → yes, because positions 0-2 are all ≥ 0.7. But it misses that position 5 is also a peak. "Peaks early" obscures the real shape (dual-peak with valley at positions 3-4).

**Fix direction:** Instead of checking just "where is the peak", look for the count and distribution of peaks (> 0.8) and valleys. Label shapes as: "rising", "falling", "arch (single peak)", "dual-peak", "plateau", "front-loaded".

**Impact:** Medium. The label feeds user-facing explanation and could mislead creative decisions.

---

### BUG-B14 · `🟢 fixed (commit 7142319)` · open_questions false positive — "No intro section"

**Reproducer:** `build_song_brain()` returns:
```json
"open_questions": [
  {"question": "No intro section — does the track need an opening?", "priority": 0.4}
]
```
But the session HAS "Intro Dust" as scene 0. The engine found it and even labeled it `emotional_intent: "tension"` — but not `"intro"`. So the open-question check asks "is any section labeled intro?" → no → flags as missing.

**Why it's wrong:** The check should consider the scene NAME (containing "intro") OR the emotional_intent (being "intro"). Intro-by-name is a stronger signal than intro-by-function.

**Fix direction:** Check for "intro" in section names OR emotional_intent OR section index 0 with lower energy than position 1. Any of those = has intro.

**Impact:** Low-medium. Wastes a slot in open_questions on a non-issue.

---

### BUG-B15 · `🟢 fixed (commit 7142319)` · analyze_transition archetype_section_mismatch ignores "any_section_change" wildcard

**Reproducer:** `analyze_transition(from="Intro Dust", to="Groove Build")` returns:
```json
{
  "archetype": {
    "name": "fill_and_reset",
    "use_cases": ["verse_to_chorus", "chorus_to_verse", "any_section_change"]
  },
  "issues": [{
    "issue_type": "archetype_section_mismatch",
    "severity": 0.5,
    "evidence": "Archetype 'fill_and_reset' (use_cases=[...]) doesn't match section pair intro -> build"
  }]
}
```

**Why it's wrong:** The archetype's use_cases explicitly includes **"any_section_change"** — a wildcard that matches any pair. The critic ignores that wildcard and checks only exact pair matches, firing a false positive.

**Fix direction:** In the mismatch critic, check:
```python
if "any_section_change" in archetype.use_cases:
    return  # wildcard matches, no issue
```

**Impact:** Medium. Creates false transition issues on perfectly sensible archetype selections.

---

### BUG-B17 · `🔴 open` · distill_reference_principles returns empty output

**Reproducer:** `distill_reference_principles(reference_description="cold 90s hip-hop with ghostly vocal chops and dusty drums", style_name="dabrye")` returns:
```json
{"reference_id": "2910e05eca", "principles": [], "emotional_posture": "",
 "density_motion": "", "arrangement_patience": "", "texture_treatment": "",
 "foreground_background": "", "width_strategy": "", "payoff_architecture": "",
 "principle_count": 0}
```
A reference_id is generated but every principle field is empty.

**Why it's a bug:** Tool accepts input, generates an ID, but produces nothing. Two probable causes:
1. The "dabrye" style has no entry in the style_tactics corpus (confirmed — `get_style_tactics` only knows burial/daft_punk/techno/ambient/trap/lo-fi)
2. The `reference_description` text parser doesn't actually distill from free-text — it only looks up style names

**Fix direction:**
- Either implement text-based distillation (use the description's semantic keywords: "cold", "ghostly", "dusty" → texture_treatment/emotional_posture), OR
- Return a clear error like "No principles found for style 'dabrye'; supported styles: [...]" instead of an empty-field success response

**Impact:** Medium. The tool is silently useless for any style not in the 6-entry corpus.

---

### BUG-B18 · `🔴 open` · get_style_tactics corpus disconnected from memory

**Reproducer:** `get_style_tactics(artist_or_genre="prefuse73")` returns:
```json
{"tactics": [], "note": "No tactics found for 'prefuse73'. Available built-in styles: burial, daft punk, techno, ambient, trap, lo-fi"}
```
But `memory_list()` shows the user has **3 saved Prefuse73 techniques** from April 2026:
- "Prefuse73 Complete Session — Full Production Workflow"
- "Prefuse73 Glitch-Hop Beat"
- "Prefuse73 Advanced — Phase Shift + Polyrhythm + Effect Chains"

**Why it's a bug:** Saved memories should feed back into style tactics. Currently memory and style_tactics are separate stores with no cross-pollination. Users who build up style libraries via `memory_learn` get nothing back from `get_style_tactics`.

**Fix direction:** Extend `get_style_tactics` to also query `memory_store` for entries tagged with the artist/genre name. Merge results, labeling source ("built-in" vs "user-saved").

**Impact:** Medium-High. Undercuts the value proposition of the memory system — users can save techniques but can't surface them as style tactics.

---

### BUG-B19 · `🔴 open` · build_reference_profile + analyze_reference_gaps limited to 6 built-in styles

**Reproducer:** `build_reference_profile(style="prefuse73")` returns `NOT_FOUND`. Same for `analyze_reference_gaps(style="prefuse73")`.

**Why it's limiting:** The reference engine ONLY works with the 6 built-in styles. Custom styles, user-provided descriptions, or memory-saved templates are not sources. That's a huge gap — reference-based workflow is one of LivePilot's headline features.

**Fix direction:**
- Same as BUG-B18 — hydrate reference profiles from memory store
- For audio-file-based workflow (`reference_path=<file>`), that works independently of the style corpus and should be exercised to confirm

**Impact:** High. The whole reference engine is locked to 6 styles for non-audio workflow.

---

### BUG-B20 · `🔴 open (duplicate root)` · suggest_momentum_rescue wraps BUG-B6 (detect_stuckness blind to session state)

**Reproducer:** `suggest_momentum_rescue(mode="direct")` returns:
```json
{"stuckness": {"confidence": 0, "level": "flowing"}, "suggestions": [],
 "note": "Session is flowing well — no rescue needed"}
```

Despite session having: 0.93 repetition fatigue + `peak_too_early` emotional arc issue + 6 transition issues.

**Why it's a bug:** `suggest_momentum_rescue` is a thin wrapper over `detect_stuckness`. Same blindness as BUG-B6 — it only reads the action ledger, not the current session state.

**Fix direction:** Same as BUG-B6 — extend stuckness detection to include state critic signals. Fix in one place, both tools benefit.

**Impact:** Medium. Rescue suggestion is a core safety net. When fatigue is high but ledger is empty, users get zero help.

---

### BUG-B21 · `🔴 open` · Three different energy metrics across engines

**Reproducer:** Same session, three different "energy" readings for the 7 sections:

| Section | `get_section_graph.energy` | `get_emotional_arc.tension` | `get_performance_state.energy_level` |
|---|---|---|---|
| Intro Dust | 0.7 | 0.56 | **0.2** |
| Groove Build | 0.9 | 0.72 | **0.6** |
| Deep Flow | 0.9 | 0.72 | **0.4** |
| Breakdown | 0.5 | 0.4 | **0.3** |
| Re-Entry | 0.6 | 0.48 | **0.7** |
| Sun Peak | 0.9 | 0.72 | **0.7** |
| Outro Dust | 0.4 | 0.32 | **0.2** |

**Why it's a bug:** Three engines compute "energy" independently. They're not just scaled differently — the *ordering* differs (e.g. "Deep Flow" is a peak in composition but mid-tier in performance). Downstream engines that mix these signals (e.g. "energy-aware scene handoff") get contradictory inputs.

**Fix direction:**
1. Unify on one canonical energy model in a shared module (`mcp_server/tools/_composition_engine/sections.py` has the base). Other engines should derive.
2. OR document the three metrics as distinct (density-energy, tension-energy, performance-energy) and rename them so their differences are visible in field names.

**Impact:** High. Root-cause for multiple downstream inconsistencies (BUG-E4/E5 below are instances of this).

---

### BUG-B22 · `🔴 open` · get_phrase_grid phrase note_density 0 for active section

**Reproducer:** Section 1 ("Groove Build") has `tracks_active: [0,1,2,3,5,6,7,8,9]` (9 tracks playing, density 0.9). `get_phrase_grid(section_index=1)` returns:
```json
{"phrases": [
  {"phrase_id": "sec_01_phr_00", "start_bar": 8, "end_bar": 12, "note_density": 36.5},
  {"phrase_id": "sec_01_phr_01", "start_bar": 12, "end_bar": 16, "note_density": 0, "has_variation": true}
]}
```
Second phrase (bars 12-16) has note_density = 0 despite being in the highest-density section.

**Why it's a bug:** Likely reading notes in the wrong window (off-by-one error on bar→time conversion) or from the wrong track. The session has 49 clips total — bars 12-16 inside "Groove Build" should have plenty of notes.

**Fix direction:** Audit the phrase-note-counting logic in `mcp_server/tools/_composition_engine/sections.py::detect_phrases`. Confirm it's enumerating ALL active tracks in the section, not just one.

**Impact:** Medium. `phrase` objects with note_density 0 falsely signal "phrase is empty" to downstream critics.

---

### BUG-B24 · `🔴 open` · classify_progression returns "?" for valid transform

**Reproducer:** `classify_progression(chords=["Dm", "Gm", "Am", "Dm"])` returns:
```json
{"transforms": ["LR", "?", "LR"], "pattern": "LR?LR", "classification": "diatonic cycle fragment"}
```
The middle transform (Gm → Am) returns "?" — the neo-Riemannian transform engine couldn't classify it. Yet the overall classification is "diatonic cycle fragment" (ignoring the unresolved middle).

**Why it's a bug:** Gm → Am is a whole-step root shift that IS classifiable (chromatic mediant by doubled L/P). Returning "?" means the transform vocabulary is incomplete. The classification then lies — "diatonic cycle fragment" with a "?" in the middle is contradictory.

**Fix direction:** Extend the transform set in `_composition_engine/harmony.py` (or wherever the transform alphabet lives) to cover whole-step root shifts. Add "step" or "cycle" transforms.

**Impact:** Medium. Progression classification is used by downstream creative reasoning.

---

### BUG-B25 · `🟡 tuning question` · find_voice_leading_path returns non-smooth leading

**Reproducer:** `find_voice_leading_path(from="Dm", to="Bb", max_steps=4)` returns:
```json
{"path": ["D minor", "Bb major"], "steps": 1,
 "voice_leading": [{"movement": "D4→A#4, F4→D5, A4→F5"}]}
```
D4→A#4 is a **minor 6th jump upward** — not smooth voice leading. For Dm→Bb, the smooth path would be: D→D (common tone, stay), F→F (common tone), A→Bb (semitone) — keeping 2 voices and moving 1 semitone in the third.

**Why it's questionable:** "Shortest" in the tool's sense is "fewest transforms" (single L transform), but voice leading should prefer smooth voicings. The output shows unnecessary large leaps.

**Fix direction:** Add a post-process step that optimizes voice assignments for minimum total interval movement. Or document that "shortest" means transforms-count, not voice-movement.

**Impact:** Low-Medium. The path is correct; the voicing isn't pianist-friendly.

---

### BUG-B26 · `🔴 open` · harmonize_melody bass stuck on tonic pedal

**Reproducer:** `harmonize_melody(track=3, clip=0, voices=4)` on Pad Lush's Intro Wash returns:
```json
{"bass": [
  {"pitch": 38, ...}, {"pitch": 38}, {"pitch": 38}, {"pitch": 38}, {"pitch": 38}, {"pitch": 33}
]}
```
5 of 6 bass notes are **D2 (38)** — the tonic. One is C#2 (33). Bass line has no motion.

**Why it's a bug:** 4-voice harmonization should produce a bass line that follows chord roots. The melody notes shift across Dm and D-F-C chords, so the bass should walk: D for Dm, G for iv (Gm), or at least the chord root for each harmonization point. Stuck on tonic = not harmonizing, just pedaling.

**Fix direction:** In the harmonization engine, after selecting a chord per melody note, assign the bass to the chord's root (or 3rd for inversions) rather than always the scale tonic.

**Impact:** High. Harmonize_melody is broken as a creative tool — produces unusable output.

---

### BUG-B27 · `🔴 open` · harmonize_melody soprano duplicates original melody

**Reproducer:** Same call as B26. Input melody (from Pad Lush clip): `[D3, F3, A3, D3, F3, C4]` = `[50, 53, 57, 50, 53, 60]`. Output soprano:
```json
[{"pitch": 50}, {"pitch": 53}, {"pitch": 57}, {"pitch": 50}, {"pitch": 53}, {"pitch": 60}]
```
**Exactly the input melody.**

**Why it's a bug:** In 4-voice harmonization (SATB), soprano should be a distinct voice — typically the MELODY in hymn-style harmonization, OR a harmonization above the melody when the melody is placed elsewhere. Returning the exact input as soprano means the "harmonization" is just the 3 lower voices (bass, tenor, alto) added — which could be correct IF the melody is copied to soprano deliberately. But the field is labeled "soprano" distinct from "melody_notes" suggesting they should differ.

**Fix direction:** Either (a) document that soprano is always the melody line, or (b) generate an actual upper-voice harmonization above the melody when the melody is in an inner voice.

**Impact:** Medium. Confusing output — user has to interpret whether soprano is melody-duplicate or a separate voice.

---

### BUG-B28 · `🟡 weak output` · generate_countermelody returns near-static pedal

**Reproducer:** `generate_countermelody(track=3, clip=0, species=1)` returns counter_notes with pitches `[50, 48, 50, 53, 50, 48]` — 3 distinct values across 6 positions, mostly D and C around the same octave as the bass.

**Why it's weak:** Species 1 counterpoint should explore contrary motion and use the full range. A counter that sits on tonic/7th with only 3 pitches is closer to a pedal ostinato than an actual contrapuntal line.

**Fix direction:** Species counterpoint algorithm should enforce:
1. Contrary motion on strong beats
2. Pitch range exploration (at least 5 distinct pitches for 6 melody notes)
3. Variety in motion types (steps, skips)

**Impact:** Medium. Makes the generative tool less useful for composition.

---

### BUG-B31 · `🟢 fixed (commit 7142319)` · develop_hook ignores discovered primary hook when hook_id is default

**Reproducer:** `develop_hook(mode="chorus")` (no hook_id provided) returns:
```json
{"hook_id": "", "hook_description": "the hook", "tactics": [
  "Double the hook with octave or harmony",
  "Add supporting harmonic movement underneath the melodic contour and pitch",
  "Increase rhythmic density around the hook",
  "Layer complementary textures that frame the melodic contour and pitch"
]}
```
Generic advice with empty hook_id.

**Why it's a bug:** `find_primary_hook()` DOES return a primary hook for this session (`hook_id: "track_10-vox_lch_..."`). `develop_hook` with no explicit hook_id should default to the primary hook, not "the hook" (generic). The session state has what it needs — the engine just doesn't connect the dots.

**Fix direction:** In `develop_hook`, when `hook_id` is empty, call `find_primary_hook()` internally and use that ID.

**Impact:** Medium. Users have to manually chain find_primary_hook → develop_hook instead of single-call.

---

### BUG-B35 · `🟡 critic tuning` · analyze_sound_design flags simple Kick as "too_few_blocks"

**Reproducer:** `analyze_sound_design(track=0)` on Kick (DS Kick + Saturator) returns:
```json
{"issues": [
  {"issue_type": "no_modulation_sources", "severity": 0.3},
  {"issue_type": "too_few_blocks", "severity": 0.5, "evidence": "Only 1 controllable block(s) — patch lacks timbral sculpting potential"}
]}
```

**Why it's misleading:** Kicks are SUPPOSED to be simple. A DS Kick + Saturator chain is textbook electronic kick design. Flagging it as "weak identity" treats a kick like a pad and misses the instrument-type context.

**Fix direction:** Weight the "too_few_blocks" and "no_modulation_sources" critics by track role. For drums, kicks, and bass — simple is correct. For pads, leads, and textures — complexity is expected.

**Impact:** Medium. Same family as BUG-B1 — role/context-unaware critics produce false positives.

---

### BUG-B36 · `🔴 open` · plan_sound_design_move doesn't cross-reference mix issues

**Reproducer:** `analyze_mix` flagged Texture (track 7) for `support_too_loud` severity 0.57. But `plan_sound_design_move(track=7)` returns:
```json
{"moves": [], "move_count": 0, "issue_count": 0}
```

**Why it's a bug:** The track has a KNOWN issue in a sibling engine (mix), but sound-design plan just reports empty. A user running `plan_sound_design_move` on a problematic track gets no guidance, even though there IS a documented fix.

**Fix direction:** When `plan_sound_design_move` finds zero sound-design issues but there ARE mix issues on the track, return a pointer:
```json
{"moves": [], "issue_count": 0,
 "hint": "No sound-design issues, but mix critic flagged 'support_too_loud'. Try plan_mix_move."}
```

**Impact:** Low-Medium. Discoverability bug — the tool silently misses cross-engine issues.

---

### BUG-B37 · `🔴 CRITICAL` · evaluate_sample_fit can't find session key despite Dm confirmed everywhere

**Reproducer:** Session is in **D minor** (confirmed by `analyze_harmony`, `identify_scale`, `suggest_next_chord` — all return Dm with high confidence). `evaluate_sample_fit(file_path=..., intent="vocal")` returns:
```json
{"critics": {
  "key_fit": {"score": 0.5, "recommendation": "Song key unknown — cannot evaluate fit", "rating": "fair"}
}}
```
"Song key unknown" despite the whole session being in Dm.

**Why it's critical:** Sample-fit evaluation is core workflow. If it can't determine the song key, it can't recommend key-compatible samples. This is a disconnected engine — sample_engine has its own song-key inference that doesn't use the harmonic engines' data.

**Fix direction:** In `mcp_server/sample_engine/critics.py` (or wherever `key_fit` lives), replace the in-house key inference with a call to `identify_scale` or `analyze_harmony` on a primary harmonic track. OR: accept an optional `song_key` param and let the caller pass it in.

**Impact:** **High.** Breaks a flagship workflow. The tool's own output even suggests the sample IS in Dm — that should trivially match session Dm.

---

### BUG-B39 · `🔴 open` · atlas_chain_suggest returns empty chain for standard role

**Reproducer:** `atlas_chain_suggest(role="bass", genre="electronic")` returns:
```json
{"role": "bass", "genre": "electronic", "chain": []}
```

**Why it's a bug:** A query for a core role ("bass") + common genre ("electronic") should return a recommended device chain (synth → compressor → saturation → EQ, etc.). Returns empty — the tool can't suggest chains even for its most basic use case.

**Fix direction:** The chain-suggestion logic in `mcp_server/atlas/` is probably missing a data source or has an empty fallback. Verify that atlas enrichment data includes role→chain templates, OR have the tool fall back to `atlas_suggest(intent=role)` and build a basic chain from the top instrument + standard FX.

**Impact:** High. Tool is documented as "Suggest a full device chain for a track role" — doesn't deliver.

---

### BUG-B40 · `🔴 open` · atlas_compare returns sparse data despite atlas_device_info having rich info

**Reproducer:** `atlas_compare(device_a="Wavetable", device_b="Drift", role="pad")` returns:
```json
{
  "device_a": {"name": "Wavetable", "tags": [], "genres": {}, "description": "", "cpu_weight": "unknown", "sweet_spot": "", "use_cases": [...]},
  "device_b": {...similar sparsity...},
  "recommendation": "Both devices are equally suited for pad"
}
```

But `atlas_device_info("Wavetable")` returns rich character_tags, detailed sonic_description, genre_affinity, starter_recipes, etc.

**Why it's a bug:** `atlas_compare` isn't reading from the same enriched atlas source that `atlas_device_info` uses. The "comparison" can't do its job with empty tags/description — it just defaults to "Both devices are equally suited."

**Fix direction:** Have `atlas_compare` call the same enrichment-aware lookup that `atlas_device_info` uses. Then compute real strengths/weaknesses from the comparable fields (character_tags overlap, genre_affinity overlap, cpu_weight diff).

**Impact:** Medium. Makes atlas_compare unhelpful for decision-making.

---

### BUG-B41 · `🟡 search ranking` · atlas_search ranks "Bass" device highest for "warm analog bass"

**Reproducer:** `atlas_search(query="warm analog bass")` returns:
```json
{"results": [
  {"name": "Bass", "score": 100, "character_tags": ["deep","powerful","focused","punchy","low_end"]},
  {"name": "Dynamic Tube", "score": 50, "character_tags": ["warm","dynamic","tube","responsive","musical"]},
  {"name": "Overdrive", "score": 50, "character_tags": ["warm","crunchy","amp_like"]},
  ...
]}
```

**Why it's odd:** For query "warm analog bass":
- "Bass" device has NONE of the query words in its character tags, yet scores 100
- Analog synth (which the user is actually using on the Bass track!) doesn't appear in top 5
- Drift (another analog-emulating synth) doesn't appear

The scoring clearly weights the device NAME "Bass" as a perfect match for the word "bass" in the query, ignoring that "warm" and "analog" don't match at all.

**Fix direction:** Weight tag-match and description-match higher relative to name-match. For query "warm analog bass", the Analog synth device should rank top because its tags include warmth AND it's an analog-emulating instrument AND it's useful for bass.

**Impact:** Medium. Users asking for sonic characteristics get name-match results instead.

---

### BUG-B43 · `🔴 open` · research_technique returns phantom "Unknown Device" findings

**Reproducer:** `research_technique(query="sidechain bass to kick for tight low end", scope="targeted")` returns:
```json
{"findings": [
  {"source_type": "device_atlas", "relevance": 0, "content": "Device: Unknown",
   "metadata": {"device_name": "", "category": ""}}
 ],
 "technique_card": {"method": "Research findings for: sidechain bass to kick for tight low end",
                    "verification": ["Check sidechain results with analyzer", "Check bass results with analyzer"]},
 "confidence": 0}
```

**Why it's broken:**
1. Findings has one phantom entry with `relevance: 0`, `content: "Device: Unknown"`, empty device_name/category — that's a malformed/default entry, not actual search output
2. `technique_card.method` is a template-string substitution, not actual research
3. `confidence: 0` — the tool itself reports no useful results
4. verification steps are generic placeholders derived from query keywords

**Expected:** For "sidechain bass to kick", the atlas should return:
- Compressor device info (sidechain capability, threshold/ratio/attack recipes)
- Glue Compressor info
- Ableton's native sidechain routing guide
- Related memory techniques

The tool's own output lists relevant devices in the `technique_card.devices` array (Compressor, Glue Compressor, Auto Filter, Operator, Analog) — so it DOES know the devices, but doesn't flow them into `findings`.

**Fix direction:** Audit `mcp_server/tools/_research_engine.py` — the atlas-search step is likely returning raw enrichment data but the findings builder is ignoring it and emitting a default "Unknown Device" template.

**Impact:** High. The whole research engine returns junk for a core workflow.

---

### BUG-B44 · `🔴 open` · create_preview_set "strong" variant missing compiled_plan

**Reproducer:** `create_preview_set(request_text="make this more magical and dusty")` returns 3 variants:
- **safe** — has `compiled_plan` with `move_id: "make_punchier"`, 2 steps
- **strong** — has `move_id: "make_kick_bass_lock"` but **NO compiled_plan field**
- **unexpected** — has `compiled_plan` with `move_id: "reduce_repetition_fatigue"`, 1 step

**Why it's a bug:** Per livepilot-core skill's Wonder Mode routing section:
> "Do not describe a branch as previewable unless it has a valid `compiled_plan`"

The strong variant is shown with `status: "pending"` and `executable`-implying labels ("Best balance of impact and safety") — but silently lacks a compiled_plan. A user committing this variant would hit a missing-plan error.

**Fix direction:** In `mcp_server/preview_studio/engine.py`, when building variants, ensure every variant gets a compiled plan OR explicitly marks `executable: false` with a reason.

**Impact:** Medium. Leads to silent execution failures or misleading UI.

---

### BUG-B45 · `🔴 open` · create_preview_set variants have empty user-facing description fields

**Reproducer:** Each variant in the preview set returns:
```json
{
  "summary": "",
  "what_changed": "",
  "render_ref": "",
  "why_it_matters": "Best balance of impact and safety",
  "what_preserved": "Maintains Glitch Chops (lead role)..."
}
```

**Why it's a bug:** `why_it_matters` is populated (useful!) and `what_preserved` is populated. But `what_changed` is empty — the USER needs to know what the variant actually CHANGES, not just why it matters. That's the primary decision criterion. `summary` and `render_ref` also empty.

**Fix direction:** The compiled_plan has step descriptions like "Read current levels for all tracks", "Verify all tracks still producing audio". Aggregate the plan's step descriptions OR the move's `intent` field into `what_changed`. Example:
```python
variant["what_changed"] = compiled_plan.get("intent", "") or \
                          " → ".join(s["description"] for s in compiled_plan["steps"])
```

**Impact:** Medium-High. Preview sets are core UX. Variants without `what_changed` = unusable for creative decisions.

---

### BUG-B46 · `🔴 open` · generate_constrained_variants returns empty-move variants

**Reproducer:** `generate_constrained_variants(request_text="reduce energy without losing groove", constraints=["subtraction_only"])` returns 3 variants all with:
```json
{"move_id": "", "what_preserved": "... | Constraints: subtraction_only"}
```
Compare to unconstrained `create_preview_set` which populated real `move_id` values (make_punchier, make_kick_bass_lock, reduce_repetition_fatigue).

**Why it's a bug:** The constraint filter appears to eliminate ALL available moves that match "subtraction_only", leaving variants with no executable plan. The tool says `"note": "Variants with violating plans have been filtered"` — but instead of reporting zero variants, it still returns 3 shell variants with empty move_ids.

**Fix direction:** Either:
1. Make the constraint filter more lenient — if no move matches, find the closest "subtraction-like" move (e.g., `tighten_low_end` involves reducing sub mud)
2. Return an empty variants list + explanatory note: "No moves match constraints [subtraction_only] — try loosening constraints"
3. Mark the variants explicitly as `executable: false` with a `blocked_reason` field

**Impact:** Medium. Constrained variant generation is silent about its failures.

---

### BUG-B49 · `🔴 open` · analyze_sample does filename-only analysis despite M4L bridge being available

**Reproducer:** `analyze_sample(file_path="/Users/.../JJP_90SS2_86_vocal_lead_hurt_you_Dm.wav")` returns:
```json
{"key": "Dm", "key_confidence": 0.5, "bpm": 86, "bpm_confidence": 0.5,
 "material_type": "vocal", "material_confidence": 0.4,
 "frequency_center": 0, "frequency_spread": 0, "brightness": 0,
 "transient_density": 0, "duration_seconds": 0, "has_clear_downbeat": false}
```

Every spectral/temporal field is zero. Key/BPM/material come from filename parsing (confidence 0.5 = filename-only).

**Why it's a bug:** The tool's own docstring says "Falls back to filename-only analysis if M4L bridge unavailable." But `check_flucoma` confirms all 6 FluCoMa streams active. The bridge IS available. The tool is defaulting to filename-only even when proper analysis should be possible.

**Fix direction:** In `mcp_server/sample_engine/analyzer.py`, when `file_path` is given, read the file via soundfile/librosa (offline — no M4L needed) and compute:
- duration (trivial — read frames / sample rate)
- spectral centroid + spread (numpy FFT)
- transient density (onset detection via librosa)
- has_clear_downbeat (tempo estimation)

M4L bridge isn't even the right dependency for file-based analysis — that's what `analyze_loudness` does offline via numpy.

**Impact:** High. Sample analysis is the foundation for sample-engine decisions. Returning zeros means every downstream critic has no real data.

---

### BUG-B51 · `🔴 open` · compare_phrase_impact returns identical scores for distinct sections

**Reproducer:** `compare_phrase_impact(section_indices=[2, 5], target="drop")` on Deep Flow (sec_02) vs Sun Peak (sec_05):
```json
{"rankings": [
  {"section_index": 2, "section_name": "Deep Flow", "composite_impact": 0.285,
   "arrival_strength": 0.3, "anticipation_strength": 0.2, "contrast_quality": 0,
   "repetition_fatigue": 0.5, "section_clarity": 0.7, "groove_continuity": 0.7,
   "payoff_balance": 0.25},
  {"section_index": 5, "section_name": "Sun Peak", "composite_impact": 0.285, ...identical}
],
"delta_analysis": {"strongest": "Deep Flow", "weakest": "Sun Peak",
                   "composite_delta": 0, "biggest_gap_dimension": ""}}
```

Every single dimension is identical. Different sections, different clip content, but the phrase analyzer can't tell them apart.

**Why it's a bug:** Deep Flow has active tracks `[0,1,2,3,4,5,6,7,8]` and Sun Peak has `[0,1,2,3,4,5,6,7,8]` — same track set but different clips (confirmed by different arrangement clip names for Pad Lush across sections). The phrase analyzer is likely only reading section-level energy/density (both 0.9 — identical) rather than the actual clip/note contents.

**Fix direction:** In `score_phrase_impact` (the per-section tool that `compare_phrase_impact` wraps), read the actual NOTE data from clips in each section to differentiate. Section energy+density alone isn't enough — two sections with the same density can have very different impact (e.g., a busy verse vs a held chorus chord).

**Impact:** Medium. `compare_phrase_impact` can't actually compare when sections have similar energy/density.

---

### BUG-B52 · `🟢 fixed (commit 7142319)` · export_clip_midi ignores custom filename parameter

**Reproducer:** `export_clip_midi(track_index=3, clip_index=0, filename="/tmp/livepilot_debug_pad_intro.mid")` returns:
```json
{"file_path": "/Users/visansilviugeorge/Documents/LivePilot/outputs/midi/livepilot_debug_pad_intro.mid",
 "note_count": 6, "duration_beats": 30, "tempo": 119}
```

The file wrote to the default `~/Documents/LivePilot/outputs/midi/` directory, not the specified `/tmp/` path. Only the basename was respected; the dirname was overridden.

**Why it's a bug:** The `filename` parameter is documented as "Auto-generates filename from track/clip if not provided." When provided, users expect their path to be honored. Instead, the tool splits the input into dirname+basename, discards the dirname, and uses its own default output directory.

**Fix direction:** In `mcp_server/tools/_midi_io_engine.py::export_clip_midi`, respect the full absolute path when provided. If the user writes `/tmp/foo.mid`, write to `/tmp/foo.mid`, not `~/Documents/LivePilot/outputs/midi/foo.mid`.

**Impact:** Low-Medium. Users who try to export to specific locations get silent redirect. Creates unexpected files in the Documents tree.

---

### BUG-B54 · `🔴 open (cascades from B17)` · generate_reference_inspired_variants produces shell variants end-to-end

**Reproducer:** Chain:
1. `distill_reference_principles(reference_description="cold 90s hip-hop...")` → returns `principles: []` (BUG-B17)
2. `map_reference_principles_to_song()` → returns `mappings: []`, `mapping_count: 0`
3. `generate_reference_inspired_variants(request_text="...")` → returns 3 variants with `principles_applied: []`, `move_id: ""`, empty `what_changed` / `summary`

**Why it's a bug:** The entire reference-engine chain — distill → map → generate_variants — silently degrades to empty output. Each step accepts the upstream empty data and passes empty data forward. The user gets 3 shell "variants" that claim to be "reference-inspired" but have no reference material driving them.

**Fix direction:** Add failure cascade detection. If `distill_reference_principles` returns empty, subsequent tools should:
- Refuse to run and return an explanatory error
- OR fall back to a generic variant builder (not branded as reference-inspired)
- OR emit a prominent warning in the output that the reference chain is broken

**Impact:** High. This is a multi-step workflow that can look like it's working while producing nothing useful.

---

### BUG-B53 · `🟡 cross-tool inconsistency` · wonder_mode variants are rich, create_preview_set variants are shells

**Reproducer:** Same session, two similar tools produce dramatically different quality:

**`enter_wonder_mode(request_text="...")`** variant output:
```json
{"variant_id": "wm_..._strong", "move_id": "open_chorus",
 "what_changed": "Targets energy (+0.4), width (+0.3), contrast (+0.3)",
 "compiled_plan": {"move_id": "open_chorus", "step_count": 8, "steps": [...]},
 "score": 0.799, "score_breakdown": {"taste": 0.6, "identity": 0.7, "novelty": 0.946, "coherence": 1},
 "distinctness_reason": "Different approach: set_track_pan, set_track_send, set_track_volume"}
```

**`create_preview_set(request_text="...")`** variant output (strong):
```json
{"variant_id": "ps_..._strong", "move_id": "make_kick_bass_lock",
 "what_changed": "",        // empty
 "compiled_plan": null,     // MISSING entirely
 "score": 0, ...}           // no breakdown
```

**Why it's a bug:** Both tools generate creative variants. Wonder mode is CORRECT: rich compiled_plan + what_changed + scoring. Preview set has the same three variants (safe/strong/unexpected) shape but missing most fields (BUG-B44 + BUG-B45).

**Root cause hypothesis:** Two different code paths in `mcp_server/preview_studio/engine.py` — one for wonder mode, one for direct preview. They should share a common variant-builder.

**Fix direction:** Unify variant construction. Wonder mode's flow is the correct template — preview_set should use the same logic.

**Impact:** Medium. Users invoking `create_preview_set` directly (outside wonder mode) get inferior output.

---

### BUG-B50 · `🟡 partial implementation` · build_reference_profile style corpus is incomplete

**Reproducer:** `build_reference_profile(style="burial")` returns partial data:
```json
{"source_type": "style",
 "loudness_posture": 0, "spectral_contour": {}, "width_depth": {},
 "density_arc": [0.75],
 "section_pacing": [{"label": "sparse_intro"}, {"label": "gradual_buildup"}, {"label": "sudden_strip_back"}],
 "harmonic_character": "atmospheric_filtered",
 "transition_tendencies": ["conceal", "drift", "punctuate"]}
```

**Why it's partial:** "burial" IS in the built-in style list (confirmed working for `get_style_tactics`), and the section_pacing / harmonic_character / transition_tendencies fields HAVE data. But `loudness_posture: 0`, `spectral_contour: {}`, `width_depth: {}` are empty — so reference gap analysis against Burial can't compare loudness or spectral character.

**Fix direction:** Extend the built-in style corpus (`mcp_server/reference_engine/styles.py` or similar) with loudness_posture + spectral_contour + width_depth for each style. For Burial: approx -12 LUFS integrated, dark spectrum (centroid ~2kHz), wide + deep stereo depth.

**Impact:** Medium. Reference gap analysis works partially — structural comparisons work, spectral/loudness don't.

---

### BUG-B42 · `🟡 critic tuning` · build_world_model.weak_foundation false-positive during stopped playback

**Reproducer:** `build_world_model()` during `is_playing: false` returns:
```json
{"sonic": {"spectrum": {...all zeros...}, "rms": 0},
 "issues": {"sonic": [{
   "type": "weak_foundation", "severity": 0.6,
   "evidence": ["sub band energy: 0.00 with bass tracks present"]
 }]}}
```

**Why it's wrong:** The sub band energy is 0 because **playback is stopped**, not because the mix has weak foundation. The critic fires based on spectrum data without checking playback state.

**Fix direction:** In `mcp_server/tools/_agent_os_engine/critics.py::run_sonic_critic`, check `is_playing` before computing spectrum-based critics. When not playing, either skip the sonic critic OR return a "playback_required" issue.

**Impact:** Medium. Users probing `build_world_model` on a static session get misleading "weak_foundation" warnings.

---

### BUG-B38 · `🔴 open (known stub)` · evaluate_sample_fit frequency_fit critic is a stub

**Reproducer:** Same call as B37. Output includes:
```json
"frequency_fit": {
  "score": 0.5,
  "recommendation": "No spectral data — verify frequency fit by ear",
  "adjustments": [{"note": "stub — spectral overlap analysis not yet implemented"}]
}
```

**Why it's a bug (or, unfinished feature):** The tool explicitly returns a "stub" marker. This feature isn't implemented but runs in production returning a default 0.5 score.

**Fix direction:** Either:
1. Implement spectral overlap analysis (read master spectrum + sample spectrum, compute overlap)
2. Remove the critic entirely until implemented (don't return 0.5 as if it's meaningful)
3. Gate the stub behind `capability.available == false` so it returns "unavailable" rather than "fair"

**Impact:** Low (known stub, not a regression) but degrades evaluate_sample_fit's meaningfulness.

---

### BUG-B23 · `🔴 open` · suggest_next_chord figure/quality mismatch

**Reproducer:** `suggest_next_chord(track=3, clip=0)` on the Pad Lush D-minor clip returns:
```json
{
  "key": "D minor",
  "suggestions": [
    {"figure": "IV", "chord_name": "G-minor triad", "quality": "minor", "midi_pitches": [67, 70, 74]},
    {"figure": "V", "chord_name": "A-minor triad", "quality": "minor", "midi_pitches": [69, 72, 76]}
  ]
}
```

**Musical issues:**
1. **IV in D minor is Gm** (G-Bb-D) — correct pitches (67 G, 70 Bb, 74 D). Label IV (uppercase = major) mismatches quality "minor" → should be **iv** (lowercase for minor).
2. **V in D minor is A major** (A-C#-E) in common-practice. The tool returns A minor (A-C-E, 69/72/76). In modal/natural minor this is **v** (lowercase). Again uppercase figure mismatches minor quality.

**Why it's a bug:** Roman numeral figures (IV/V) conventionally use uppercase for major chords and lowercase for minor. The tool returns uppercase figures with minor qualities — pick one convention or match them correctly.

**Fix direction:** In the figure-labeling logic, derive case from chord quality: if triad is minor → lowercase figure (iv, v, vi, etc.). If major → uppercase (IV, V, VI). If diminished → lowercase + "°".

**Impact:** Low-medium. Musicians reading the figures get confused; downstream progression critics that trust the figure may misclassify.

---

### BUG-B16 · `🔴 open` · get_session_story returns empty after build_song_brain

**Reproducer:** Just called `build_song_brain()` which returned `brain_id: "a7e6ef3b70a9"` with full identity_summary. Immediately after, `get_session_story()` returns:
```json
{"song_id": "", "identity_summary": "Dominant texture: drums", ...,
 "threads": [], "recent_turns": [], "mood_arc": [], "total_turns": 0}
```

**Why it's confusing:** Some fields ARE populated (identity_summary matches) but `song_id` is empty, `threads` empty, `recent_turns` empty. Is the session story a separate data store from song_brain? Or is it expected to hydrate from ledger + threads which are empty because no moves were recorded?

**Fix direction:**
1. If session_story is meant to be the canonical narrative, it should pull `song_id`/`mood_arc` from the last-built SongBrain
2. If it's ledger-based, document clearly that it's empty on fresh sessions with no action history
3. At minimum, include `song_brain_id` field so clients know which brain was used

**Impact:** Low. Not a user-blocker but wastes trust — the partial population reads as "something's wrong."

---

## E. Cross-engine data consistency

### BUG-E1 · `🟢 fixed (Batch 3)` · project_brain.role_graph empty — section_id key mismatch

**Reproducer:** `build_project_brain()` returned `role_graph: {"roles": [], "confidence": {"overall": 0, ...}}` while `analyze_composition()` on the same session returned 49 role assignments.

**Root cause:** `build_role_graph` expects a `notes_map` keyed on the same section IDs that `build_section_graph_from_scenes` emits (`sec_{i:02d}` using the raw enumerate index). `build_project_brain` in `tools.py` was building the notes_map keyed on the scene display name instead (`scene.get("section_id") or scene.get("name") or f"scene_{idx}"`). Every `notes_map.get("sec_00", {})` lookup missed, `active_tracks` stayed empty, and role inference produced zero entries.

Second related issue: `_ce_build_sections` skips unnamed scenes, which means section IDs can be non-contiguous (`sec_00`, `sec_02`). The notes_map loop must skip unnamed scenes *and* use the raw enumerate index to keep the IDs aligned.

**Fix (landed):** `mcp_server/project_brain/tools.py::build_project_brain` now builds `notes_map` with the same `f"sec_{scene_idx:02d}"` scheme, skipping unnamed scenes but preserving the raw index. Regression tests `test_notes_map_keys_match_section_ids` and `test_empty_scene_names_advance_section_counter_consistently` in `tests/test_project_brain.py` enforce the alignment invariant.

**Impact:** Medium. Engines that rely on `project_brain` for role info now see the same data as `analyze_composition`.

---

### BUG-E3 · `🟢 fixed (Batch 5)` · get_harmony_field hijacked by percussion tracks

**Reproducer (live Dabrye session, section "Intro Dust"):**
`get_harmony_field(section_index=0)` returned `{"key": "C", "mode": "major", "chord_progression": ["C chord"] × 4}` while `analyze_harmony(track=3, clip=0)` on the Pad Lush clip in the same section returned `{"key": "D minor", "chords": ["D-minor triad", ...]}`. Two tools, same section, contradictory answers.

**Root cause (diagnosed on live session):** `get_harmony_field` iterated `section.tracks_active` in track-index order and took the **first track with notes** to lock in scale info (`if not scale_info:` guard). Track 1 "Perc Hats" came before track 3 "Pad Lush" in active_tracks. Perc Hats' Ghost Hats clip contained four MIDI notes all at pitch 60 (C4) with 0.1-beat durations — a single-pitch staccato percussion trigger. `detect_key` on that pool matched "C major" (C is in the C major scale and there's no disambiguation), then the loop never consulted the Pad Lush track's actual D/F/A harmony.

**Fix (landed):**
1. New helper `harmonic_score(notes, track_name)` in `mcp_server/tools/_composition_engine/harmony.py` returning 0.0–1.0. Combines unique pitch classes, median duration, pitch range, minimum pitch, and track-name hints (`"kick"/"hat"/"perc"/"drum"` etc. vs `"pad"/"bass"/"lead"/"keys"`).
2. `mcp_server/tools/composition.py::get_harmony_field` now builds a scored candidate list of all active tracks, sorts by score desc, **aggregates notes from every track ≥ 0.3** for key detection, and uses the **top-scoring single track** for chord extraction. Falls back to highest-scoring track if nothing passes threshold.

**Verification (live session):** To be re-measured after plugin-cache sync. Scoring on the real data: Perc Hats `0.15` (below threshold), Pad Lush `0.95` (above) — aggregator consults only the pad.

Regression tests (`tests/test_composition_engine.py::TestHarmonicScoreBugE3` + `tests/test_composition_tools.py::TestGetHarmonyFieldE3`):
- Percussion hits score <0.3
- Sustained Dm triad scores >0.6
- Track-name nudges bounded in [0,1]
- Monophonic bass passes threshold (harmonic, not drum)
- Long drone note not misclassified as drum
- Pad decisively beats perc in the Dabrye reproducer
- Integration: full `get_harmony_field` on fake-Ableton with perc + pad returns D/F/A tonic, not "C major"
- Integration: chord_progression reflects pad content, not perc

**Impact:** High — now closed. Every harmonic critic that uses `get_harmony_field` (transition analysis, voice-leading, chromatic-mediant suggestions) gets the true key.

---

### BUG-E4 · `🔴 open` · get_performance_state role labels differ from analyze_composition

**Reproducer:** Same sections, different role labels:

| Section | analyze_composition.section_type | get_performance_state.role |
|---|---|---|
| Intro Dust | intro | intro ✓ |
| Groove Build | build | build ✓ |
| Deep Flow | **drop** | **verse** |
| Breakdown | breakdown | breakdown ✓ |
| Re-Entry | verse | **chorus** |
| Sun Peak | **drop** | **chorus** |
| Outro Dust | outro | outro ✓ |

**Why it's wrong:** 3 of 7 sections disagree. "Drop" vs "verse" vs "chorus" — these aren't equivalent terms. The performance engine and composition engine have independent role inference logic that produces contradictory labels.

**Fix direction:** Same as BUG-B21 — unify section-role classification in one place (`_composition_engine.sections`) and have performance engine import it instead of re-deriving.

**Impact:** High. A critic told to "make the chorus punchier" would act on section 5 (Sun Peak) via performance engine but section 2 (Deep Flow) via composition engine. Silent misfire.

---

### BUG-E6 · `🔴 open` · build_world_model vs check_flucoma disagree on FluCoMa availability

**Reproducer:**
```
check_flucoma() → {"flucoma_available": true, "active_streams": 6,
                    "streams": {"spectral_shape": true, "mel_bands": true, "chroma": true,
                                "onset": true, "novelty": true, "loudness": true}}
build_world_model().technical → {"flucoma_available": false}
```

**Why it's wrong:** One says yes, the other says no, with 6 confirmed active streams sending data.

**Fix direction:** `build_world_model.technical.flucoma_available` should call `check_flucoma` internally OR read the same bridge state. Currently it's inferring availability from a different signal (maybe the `capability_state.flucoma` domain which isn't populated correctly).

**Impact:** Medium. Downstream engines using `build_world_model.technical` to decide whether to request FluCoMa data will falsely skip it.

---

### BUG-E5 · `🔴 open` · get_performance_state energy_level values differ from get_section_graph.energy

See BUG-B21 for the full cross-engine energy table. This is the specific manifestation in the performance engine — it reports energies `[0.2, 0.6, 0.4, 0.3, 0.7, 0.7, 0.2]` while the section graph reports `[0.7, 0.9, 0.9, 0.5, 0.6, 0.9, 0.4]`. Not just scaled, but reordered (Deep Flow is peak in composition, mid-tier in performance).

**Impact:** High. Same root cause as B21/E4. One engine's peak is another engine's dip.

---

### BUG-E2 · `🟢 fixed (Batch 3)` · project_brain.automation_graph empty — didn't scan clip envelopes

**Reproducer:** `build_project_brain()` returned `automation_graph.automated_params: []` while `get_clip_automation(track=3, clip=0)` on the same Pad Lush clip returned 3 real envelopes (Send A, Osc 1 Pos, Filter 1 Freq).

**Root cause:** `build_automation_graph` was only scanning `track_infos[].devices[].parameters[].is_automated` — a flag that reflects mapping state (whether a parameter is routable to automation), NOT whether an actual envelope exists on any clip. Automation envelopes in Live live on the Clip object, not on the device parameter. The previous logic could never find them.

**Fix (landed):**
1. `mcp_server/project_brain/tools.py::build_project_brain` — walk each session clip slot, call `get_clip_automation(track, clip)`, aggregate the envelope descriptors into a list keyed by `sec_{scene_idx:02d}`.
2. `mcp_server/project_brain/builder.py::build_project_state_from_data` — accepts new `clip_automation` param and forwards to automation graph builder.
3. `mcp_server/project_brain/automation_graph.py::build_automation_graph` — now accepts `clip_automation`. Clip envelopes are the source of truth; device-hint entries are only added if they don't duplicate an envelope entry. Each entry is tagged `source="clip_envelope"` or `source="device_hint"` for downstream disambiguation.
4. `density_by_section` is now computed from real per-section envelope counts (normalized by max) instead of the section-density × track-ratio approximation. Falls back to old logic if no clip data.

Regression tests (in `tests/test_project_brain.py::TestBugE2AutomationGraphWiring`):
- `test_clip_envelopes_populate_automation_graph`
- `test_no_duplicate_when_both_device_hint_and_envelope_match`
- `test_density_by_section_reflects_real_envelope_counts`

**Impact:** Medium. Critics that reason about "is this track under-automated?" now see reality.

---

## C. Audit follow-ups (from fresh-audit pass, v1.10.6)

### BUG-C1 · `🔴 open (deferred)` · analyzer.py refactor skipped

`mcp_server/tools/analyzer.py` is 971 LOC. Deferred from the 1.10.6 engine-modularization pass because the file has `@mcp.tool()` decorations and relocating them could disturb FastMCP's tool-registration order.

**Fix direction:** Same package-facade pattern as `_composition_engine` and `_agent_os_engine`, but leave the `@mcp.tool()` functions in a single sub-module and split only the helpers (cursor management, patch utilities, spectrum adapters).

---

### BUG-C2 · `⚪️ low-priority` · sample_engine/techniques.py size

`mcp_server/sample_engine/techniques.py` is 908 LOC but it's a data catalog (30+ `_register(...)` calls). Splitting doesn't improve anything materially — the data just spreads across more files.

**Fix direction:** If split, minimum surgery: two files — `_catalog.py` (registry + public API) and `_data.py` (all `_register()` calls). Low ROI.

---

### BUG-C3 · `🟡 open` · FastMCP private-internals coupling

`mcp_server/server.py::_get_all_tools()` reaches into FastMCP private attributes (`_tool_manager._tools` for 0.x, `_local_provider._components` for 3.x) to iterate the tool registry. Pinned to `fastmcp>=3.0.0,<3.3.0` specifically because of this fragility.

**Fix direction:**
1. File the upstream FR (see BUG-C4)
2. When upstream adds a public API, migrate + remove the version ceiling

---

### BUG-C4 · `🔴 open` · Upstream FastMCP FR not filed

Draft lives at `docs/FASTMCP_UPSTREAM_FR.md` (local-only per `docs/*.md` gitignore). Needs to be filed as a GitHub issue on https://github.com/jlowin/fastmcp asking for a public tool-enumeration API.

**Action:** `gh issue create --repo jlowin/fastmcp --body-file docs/FASTMCP_UPSTREAM_FR.md --title "Feature request: public tool-enumeration API"`

---

## D. Current session (Dabrye Core) creative trackers

### BUG-D1 · `🟡 needs listen-test` · Splice vocal D#min vs Dm session

Track 6 is the Splice audio clip `AU_THF2_128_vocal_full_female_chorus_brains_in_the_body_dry_D#min.wav`. Filename claims D#min but session is Dm.

**Decision tree:**
1. Unmute, listen — if the D# reads as ambient fog (at volume 0.48, no sends, dry), keep as-is
2. If it reads as dissonant, open the clip's Sample tab, set Transpose (coarse) to **−1 semitone**
3. Alternative if Option 2 glitches the audio: insert a pitch-shift M4L device

Blocked on BUG-A4 + A5 to automate detection/correction.

---

### BUG-D2 · `🔴 open (creative opportunity)` · No clip automation

`build_project_brain`'s automation_graph is empty — no filter sweeps, volume curves, or energy arc in any clip. Missing classic Dabrye-style automation moves:
- Filter sweep on RHODES before VOX LEAD entry ("vacuum before reveal")
- Volume crescendo on PERC into a drop
- Delay feedback automation on VOX LEAD for dub-style handoffs

**Action:** After VOX LEAD is unmuted + balanced, write automation envelopes to fill the emotional-arc gap (currently scored 0.637 with payoff_strength 0.0).

---

### BUG-D3 · `🟢 fixed (user-side)` · VOX LEAD Simpler Warp

**Originally open:** Simpler was in Classic/Trigger mode with 86 BPM sample in 90 BPM session → 4.7% tempo drift.
**Fixed:** User clicked Warp toggle in Simpler's Sample tab (Complex Pro mode), 2026-04-17.

---

## Session-resolved bugs (1.10.6 release)

These were closed during the v1.10.6 cleanup — listed here for historical reference.

- ✅ **79 silent `except Exception: pass` sites** across `mcp_server/` — converted to `logger.debug("<func> failed: %s", exc)` breadcrumbs
- ✅ **Credit-floor docstring lying** in `SpliceGRPCClient.download_sample()` — defensive guard added via `can_afford(1, budget=1)` check
- ✅ **Version drift** across 13 files — bumped 1.10.5 → 1.10.6 everywhere including .amxd binary patch
- ✅ **livepilot.mcpb committed to git** — `git rm --cached` + added to `.gitignore`
- ✅ **CI single Python version** — added 3.11 alongside 3.12 (covers Ableton 12.3 embedded Python)
- ✅ **OSC convention undocumented** — added contract comments to both `livepilot_bridge.js` and `mcp_server/m4l_bridge.py`
- ✅ **`_composition_engine.py` (1530 LOC)** — split into 6-module package with facade (`models`, `sections`, `critics`, `gestures`, `harmony`, `analysis`)
- ✅ **`_agent_os_engine.py` (947 LOC)** — split into 6-module package (`models`, `world_model`, `critics`, `evaluation`, `techniques`, `taste`); `_clamp` promoted to models to resolve circular-dep

---

## Debug session notes — 2026-04-17 (second session, 119 BPM project)

Second project loaded in the same session (Prefuse73-adjacent, 10 tracks, 49 clips, 7 named sections: Intro Dust → Groove Build → Deep Flow → Breakdown → Re-Entry → Sun Peak → Outro Dust). Exercised a wide set of MCP tools to surface bugs. 6 new bugs logged (B5-B9, E1-E2).

### Project fingerprint
- 119 BPM, 4/4
- 10 tracks (Kick, Perc Hats, Congas, Pad Lush, Glitch Chops, Snare Rim, Bass, Texture, Atmo FX, Splice vocal)
- 2 return tracks (A-Verb Space, B-Delay Dub)
- 8 scenes (one empty), 49 total clips
- **Key: D minor** (confirmed 0.874 confidence via Pad Lush MIDI)
- **Auto-detected key from master bus: C# major** (possible analyzer misdetection on D-minor content — not a bug necessarily, but worth noting)

### Things that work well (good signals — don't regress these)

- ✅ `analyze_composition` correctly identified 7 sections + 49 role assignments across all sections
- ✅ `identify_scale` returns modal ladder: D minor 0.874 → 7 modal alternatives at 0.751 (same pitch collection, different tonics). Proper Krumhansl-Schmuckler behavior.
- ✅ `get_clip_automation` correctly enumerates envelopes when queried directly: Pad Lush "Intro Wash" has 3 envelopes (Send A, Wavetable Osc 1 Pos, Wavetable Filter 1 Freq)
- ✅ `propose_next_best_move` returns sensible semantic-move ranks sorted by match_score
- ✅ `analyze_mix` flagged legitimate `support_too_loud` on Texture (vol 0.60 vs avg 0.38)
- ✅ `get_master_spectrum` returns real content with low age_ms while session was playing
- ✅ `find_and_load_device` works cleanly when `insert_device` fails (graceful fallback path validated)
- ✅ `memory_list` returns 12 existing techniques across sessions — including prior Prefuse73 work, a "CRITICAL: verify track meters" preference, and the 2026-04-17 bug tracker + Dabrye template

### Session observations (findings, not bugs)

- **Pad Lush** uses Wavetable (InstrumentVector) + Saturator (Drive 51%, Dry/Wet 45%) + Echo (Duck On enabled, L/R Div -3/-3 asymmetric, Wobble On amount 0.15). Well-sculpted wet pad.
- **Bass** uses UltraAnalog (OSC1 saw octave -1 level 85%, OSC2 sine octave -2 level 70%, F1 LPF 24dB drive 2 freq 28%, glide 15%) + Auto Filter Legacy. Classic analog bass architecture.
- **Texture track** is the loudest at 0.60 — candidate for gain staging
- **Scenes 1+2 (Groove Build + Deep Flow) both at energy 0.9** → legitimate `no_adjacent_contrast` form issue
- **Scenes 3+4 (Breakdown + Re-Entry) at 0.5/0.6** → another `no_adjacent_contrast` issue
- **Splice vocal** (track 9) contains the same `JJP_90SS2_86_vocal_lead_hurt_you_Dm` sample reused from the Dabrye session
- **Fatigue level: 0.93** across the 8-motif arrangement — but loop-based scene design = high motif recurrence by design, so the critic is over-triggering here (possible BUG-B1-adjacent tuning issue)

### Current bug totals

| Category | Open | Fixed | Notes |
|---|---|---|---|
| **A** server/LOM gaps | 2 | 3 | **Batch 2**: A1 (install-drift handshake), A4 (get_clip_info pitch), A5 (set_clip_pitch) closed. A2, A3 remain (M4L-bridge route). |
| **B** critics/analyzers | **39** | **7** | **Batch 4**: B2 (iv turnaround mislabeled) + B5 (partial chord mis-rooted) — chord_name rewrite with bass-note priority, subset/superset matching. |
| **C** audit follow-ups | 4 | 0 | v1.10.6 deferred items |
| **D** creative trackers | 2 | 1 | Dabrye session D3 fixed (VOX LEAD Warp); D1 now unblocked by A5 |
| **E** cross-engine consistency | 3 | 3 | **Batch 5**: E3 (harmony_field aggregates harmonic tracks, filters percussion). Batch 3: E1, E2. E4-E6 remain. |
| **Total** | **49** | **15** | Batch 5 shipped — `harmonic_score()` helper + `get_harmony_field` aggregation rewrite. Batch 4: chord_name rewrite. Batch 3: project_brain data wiring. Batch 2: remote-script version handshake + audio-clip pitch/gain (320→321). Batch 1: 6 song_brain / transition / hook / midi_io fixes. Plus v1.10.6 D3. |

### Additional findings (wave 3 — song brain + transitions + theory + FluCoMa)

**Big positive discovery:** Arrangement view is **fully built out** on this session — Pad Lush alone has 43 arrangement clips across 960 beats with poetic names ("Intro Wash — distant pad", "Sun Wash — harmonic bed", "Full Wash — the one chord moment", "Float — the stillness", "Sun Chord — the harmonic peak", "Farewell — the pad says goodbye"). Session view clips + arrangement view are both populated — scene view feels like the "working draft" and arrangement view is "the final pass." LivePilot's composition critics only read session view, missing this richness.

**Working correctly (confirmed):**
- ✅ `build_song_brain` returns structured model with identity, sacred elements, energy arc, open questions
- ✅ `detect_identity_drift` correctly reports 0 drift when no changes since last brain
- ✅ `analyze_transition` produces structured archetype + scoring + targeted issues (despite BUG-B15)
- ✅ `get_transition_analysis` enumerates all 6 adjacent-section boundaries with specific recommendations per boundary
- ✅ `detect_theory_issues` correctly finds zero issues for a legitimate D minor pad clip (no parallel fifths, in-key, clean)
- ✅ `check_safety` properly escalates `delete_track` to "caution" + requires_confirmation=true when affecting 10 tracks
- ✅ `get_automation_recipes` returns 15 recipes (filter_sweep_up/down, dub_throw, tape_stop, build_rise, sidechain_pump, fade_in/out, tremolo, auto_pan, stutter, breathing, washout, vinyl_crackle, stereo_narrow) — **rich creative library**
- ✅ `analyze_for_automation` correctly identifies device types (Drift → timbre_evolution, Auto Filter → filter_sweep, sends → dub_throw) and maps to recipe names
- ✅ `get_arrangement_clips` returns precise clip timing (43 entries on Pad Lush with start/end times, lengths, loop states)
- ✅ `get_spectral_shape` (FluCoMa) returns real descriptor values (centroid 979 Hz, spread 1390, skewness 3.98, crest 35.57) — FluCoMa bridge IS functional for this tool

**Unverified — playback-state dependent (re-verify when audio confirmed playing):**
- ⚠️ `get_chroma` returned all zeros (session may have paused between probes)
- ⚠️ `get_onsets` returned `detected: false`
- ⚠️ `get_mel_spectrum` values are 1e-6 range (essentially silent)
- ⚠️ `analyze_for_automation` returned spectrum all zeros
- These are consistent with playback stopped during the probe, not tool bugs. Re-verify with confirmed-playing audio.

---

### Additional findings (wave 4 — reference engine + generative + performance + phrase)

**Biggest finding — 3 engines disagree on section "energy" and "role"** (BUG-B21/E4/E5). Composition engine, performance engine, and emotional arc engine each compute these fields independently with different algorithms. They even disagree on *ordering* (Deep Flow is a peak in composition but mid-tier in performance). Anything that mixes signals from multiple engines silently misfires.

**Reference engine is substantially limited** (BUG-B17/B18/B19):
- Only 6 built-in styles: burial, daft punk, techno, ambient, trap, lo-fi
- Prefuse73 (which the user has 3 saved techniques for!) returns NOT_FOUND
- `distill_reference_principles` accepts any description text but returns empty fields — text-to-principle distillation is either unimplemented or gated on style lookup
- Memory store and style_tactics store are disconnected — saved techniques don't feed back as tactics

**BUG-E3 — `get_harmony_field` returns WRONG KEY** for the same underlying clip that `analyze_harmony` correctly analyzes. Section 0 "Intro Dust" comes back as C major with 4 identical "C chord" entries, while direct analysis of the Pad Lush MIDI returns D minor with proper chord content. The section-level harmony engine is reading the wrong data source.

**Working correctly (wave 4 positives):**
- ✅ `get_section_graph` returns the same 7 sections as `analyze_composition` (internally consistent)
- ✅ `generate_euclidean_rhythm(3, 8)` produces correct tresillo pattern `[1,0,0,1,0,0,1,0]` with proper timing, identifies the named rhythm
- ✅ `suggest_next_chord` detects D minor correctly, suggests IV and V (despite figure-case bug B23)
- ✅ `plan_scene_handoff(0→1)` returns structured 5-step gesture sequence with energy path `[0.2, 0.3, 0.4, 0.5, 0.6]`
- ✅ `get_performance_safe_moves` returns 8 safe + 2 energy moves with proper blocked_moves list (`arrangement_edit`, `clip_create_delete`, `device_chain_surgery`, `note_edit`, `track_create_delete`) — good safety discipline
- ✅ `detect_payoff_failure`: `overall_health: "healthy"`, 0 failures — reasonable
- ✅ `get_sample_opportunities`: flags "no Simpler/Sampler devices — samples could add character" with confidence 0.4 (legit since track 9 is the only audio track)
- ✅ `get_emotional_arc` returns tension_curve + legit `peak_too_early` issue (position 2/7)
- ✅ `check_safety("delete_track")` properly escalates to caution + requires confirmation when affecting 10 tracks
- ✅ `get_action_ledger_summary`, `get_promotion_candidates`, `get_section_outcomes` properly empty for a fresh session (no false data)

### Additional findings (wave 5 — generative + theory + translation + sound design + sample fit)

**Biggest finding — `evaluate_sample_fit` can't detect the session key** (BUG-B37). Core workflow for sample recommendation is crippled because the sample engine has its own (broken) key inference that doesn't use the harmonic engines' data. This is the third distinct "can't detect key" or "wrong key" bug after E3 (harmony_field wrong key) and the master-bus C# vs Dm detection. **Root cause: 3+ engines independently compute "what key is this song in" with different algorithms.**

**Harmonization engine is broken** (BUG-B26/B27):
- 4-voice output with bass stuck on tonic pedal (5 of 6 bass notes are D2)
- Soprano line is an exact duplicate of the input melody (not a harmonization)
- Creative tool unusable as-is

**Evaluate_sample_fit's frequency_fit critic is an explicit stub** (BUG-B38) — returns default 0.5 score with the adjustments array containing `"note": "stub — spectral overlap analysis not yet implemented"`. Running in production.

**Working correctly in wave 5 (strong signals):**
- ✅ `classify_progression(Dm-Gm-Am-Dm)` correctly identifies "diatonic cycle fragment" (despite one transform returning "?", the classification heuristic still works)
- ✅ `navigate_tonnetz(Dm, depth=2)` returns structured P/L/R + all 9 depth-2 transforms (PP, PL, PR, LP, LL, LR, RP, RL, RR)
- ✅ `suggest_chromatic_mediants(Dm)` returns 6 valid mediants + cinematic picks (Bb minor, F# minor)
- ✅ `find_voice_leading_path(Dm→Bb)` finds 1-transform L path (tuning issue with voice smoothness, not correctness)
- ✅ `transform_motif([2,2,-1,2], "inversion")` correctly inverts to `[-2,-2,1,-2]` — verified by checking output pitches
- ✅ `generate_tintinnabuli` returns voices following Pärt's nearest-triad-tone rule (with a couple questionable choices, minor issues)
- ✅ `transform_section("insert_bridge_before_final_chorus")` returns dry-run before/after section graph — 7 → 8 sections, bar delta +8, proper non-mutating preview
- ✅ `score_phrase_impact(section=5, target="drop")` returns multi-dimensional score (arrival, anticipation, contrast, fatigue, clarity, groove, payoff)
- ✅ `score_transition` returns structured boundary-clarity + payoff + redirection + identity + cliche-risk breakdown
- ✅ `check_translation` returns `overall_robustness: "robust"` with mono-safe + small-speaker-safe + low-end-stable + front-element-present all true
- ✅ `measure_hook_salience` includes natural-language `interpretation` field — nice UX touch
- ✅ `plan_mix_move` correctly proposes `gain_staging` for Texture (tracks back to analyze_mix finding)
- ✅ `get_mix_summary` lightweight 10-track summary with anchor tracks, loudest/quietest
- ✅ `evaluate_sample_fit` produces both `surgeon_plan` and `alchemist_plan` — rich tool output despite the key-detection bug

---

### Additional findings (wave 6 — atlas + browser + generative + world model + FluCoMa)

**CONFIRMED: FluCoMa tools ARE available and working** (`check_flucoma` returns `active_streams: 6` with all 6 named streams `true`). The earlier zero-output observations were 100% playback-state-dependent — not tool bugs. The FluCoMa subsystem is healthy; `get_chroma`/`get_onsets`/`get_mel_spectrum`/`analyze_for_automation` spectrum all return zeros only because `is_playing: false` at probe time.

**NEW systemic finding — atlas vs atlas_device_info data parity broken** (BUG-B40). The atlas has rich enrichment data (character_tags, genre_affinity, starter_recipes, gotchas, sonic_description, complexity, synthesis_type, introduced_in). But `atlas_compare` doesn't read that enrichment — it gets a stripped-down view. Same data, different access paths produce different answers.

**Rich enrichment proof — `atlas_device_info("Wavetable")` is outstanding:**
- character_tags: `["modern", "versatile", "lush", "massive", "evolving"]`
- use_cases: leads/pads/bass/textures/plucks
- genre_affinity: primary (edm/pop/future_bass), secondary (synthwave/cinematic/ambient/dnb)
- **10 key_parameters** with ranges, sweet_spots, and type info
- **3 starter_recipes** with exact param values (Supersaw Lead, Glassy Pad, Digital Bass)
- **5 pairs_well_with** relationships with rationale
- **5 gotchas** with practical advice (CPU cost of unison, mod matrix power, etc.)
- complexity level, synthesis_type, introduced_in version

This is DEEP corpus knowledge. The data is there. Access paths need consolidation.

**Working correctly in wave 6 (strong signals):**
- ✅ `atlas_suggest(intent="evolving pad")` returns 5 synths (Analog, Drift, Emit, Meld, Poli) with parameter recipes per device
- ✅ `atlas_device_info("Wavetable")` returns the richest corpus entry I've seen — 10 params, 3 recipes, 5 gotchas, 5 pairings
- ✅ `atlas_search("warm analog bass")` returns 5 results with enrichment + scoring (despite ranking bug B41)
- ✅ `get_browser_tree` returns the full 11-category tree (instruments 32, audio_effects 70, drums **684**, samples **22,291**, user_library 10, plugins 4 — rich data)
- ✅ `get_automation_state(track=3, device=0)` on Wavetable returns 93 total params, 0 automated — lightweight and accurate
- ✅ `search_samples("dark vocal chop", key="Dm")` returns 5 Splice results with full metadata (hash, bpm, key, tags, pack, duration, price)
- ✅ `list_semantic_moves(domain="mix")` returns 6 mix moves with targets/protect/risk + 7 domain list
- ✅ `layer_euclidean_rhythms` correctly stacks tresillo (3/8) + cinquillo (5/8) + brazilian necklace (7/16) with proper naming
- ✅ `generate_phase_shift(3 voices, shift 0.125)` produces 44 notes with velocity-encoded voicing
- ✅ `generate_additive_process(direction="forward", reps=2)` produces 4-stage build — 20 notes
- ✅ `generate_automation_curve("exponential", duration=8, density=32)` returns 32 precise curve points
- ✅ `get_device_presets("Drift")` returns **250+ presets** organized by category — massive corpus
- ✅ `get_anti_preferences` + `get_taste_graph` + `explain_taste_inference` properly empty for a fresh session (no phantom data)
- ✅ `compile_goal_vector` validates targets + splits measurable/unmeasurable dimensions correctly
- ✅ `build_world_model` returns topology + sonic + technical + role inference + structured issues (with B42 and E6 inconsistency caveats)
- ✅ `check_flucoma` — proper diagnostic return with per-stream availability

**Interesting discovery — `get_browser_tree` returned `current_project` category with 21 .als files** — the user has 21 LivePilot-adjacent projects on disk, including `prefuse73 demo.als`, `dabrye 73.als`, `dabrye prefuse 1.9.21.als`, `boc demo debug.als`, `shybuia house.als`, `manele.als` (Romanian genre!), `aicaldos.als`, `LIVEPILOT V2.als` and more. Rich body of work; each is a potential reference source for the style_tactics corpus (currently limited to 6 built-in styles — see BUG-B18/B19).

---

### Additional findings (wave 7 — preview studio + experiment + research + compose + device forge)

**Biggest finding — `research_technique` is essentially broken** (BUG-B43). For a clear query like "sidechain bass to kick", it returns a phantom "Unknown Device" finding with confidence 0 and a template-substitution `technique_card` that has no real research content. The atlas HAS the data (Compressor info, sidechain recipes) but the research flow doesn't connect to it.

**Preview studio has shape but missing flesh** (BUG-B44, B45, B46):
- Variants missing compiled_plan where they shouldn't
- `what_changed` field empty — users can't see what variants actually do
- Constrained variants can't find matching moves → emit empty-move shells

**`analyze_sample` never opens the file** (BUG-B49). Despite FluCoMa being fully available and the user's entire ecosystem depending on sample analysis, the tool returns filename-parsed key/bpm with every spectral/temporal field set to zero. Should use offline librosa/soundfile for duration, spectral centroid, onset density.

**`compose` works but conservatively when credits=0** — correctly generated 5-layer plan with Splice queries, then dropped all layers when credits budget prohibited downloads. Ended with a single-step plan (set_tempo). Working as designed but the output is degenerate for users without credit budget.

**Working correctly in wave 7 (strong signals):**
- ✅ `list_genexpr_templates`: 15 templates across 8 categories — Lorenz/Henon (chaos), Karplus-Strong/phase-distortion/wavefolder/bitcrusher (synthesis+distortion), FDN/granular-delay/chorus/ring-mod (delay/mod), stochastic-resonance (texture). Rich GenExpr DSP library for M4L generation.
- ✅ `plan_arrangement(style="hiphop", target_bars=128)`: produces **complete 8-section blueprint** (intro 12b → verse 24b → chorus 12b → verse 24b → chorus 12b → bridge 12b → chorus 12b → outro 12b = 120 bars) with per-section energy/density targets, tracks_entering/exiting, sample_hints, AND gesture_plan (7 transitions with gesture_templates like "pre_arrival_vacuum", "re_entry_spotlight", "outro_decay_dissolve"). Beautiful structured output.
- ✅ `apply_creative_constraint_set(["subtraction_only", "no_new_tracks"])`: confirms both constraints with descriptions + reasons — good UX
- ✅ `suggest_sample_technique` for the Hurt You vocal: 3 rich techniques
  - `vocal_chop_rhythm` (Burial-style staccato) — 7 steps
  - `vocal_harmony_stack` (Bon Iver Prismizer) — 4 steps
  - `syllable_instrument` (vocal as instrument) — 5 steps
  Each has name, difficulty, philosophy, inspiration, step_count, steps_preview. This is the technique library showing its best form.
- ✅ FluCoMa tools (re-verified): `get_novelty` = 0.0135 real, `get_momentary_loudness` = -104.6 LUFS (playback paused = low), `get_spectral_shape` centroid 998Hz + crest 38 — all real data
- ✅ `get_browser_items("instruments/Drift")` — 13 folders with is_folder flags for tree navigation
- ✅ `analyze_sound_design` on 4 more tracks (Perc Hats/Glitch Chops/Bass/Atmo FX) — structured patch models. Most have 0 issues (reasonable — tracks are well-designed). Perc Hats flagged as "generic_chain" (Erosion+Echo lacks filter/saturation for character).
- ✅ `create_experiment(move_ids=["make_punchier", "tighten_low_end"])` — clean experiment with 2 branches, proper IDs
- ✅ `discard_preview_set` + `discard_experiment` — cleanup returns `{"discarded": true}` confirming state clears
- ✅ `build_reference_profile(style="burial")` returns actual structured data (unlike "prefuse73" which NOT_FOUND'd in earlier wave) — partial but working

**Interesting observation:** `get_technique_card("dusty kick")` returned 0 cards despite the user's memory containing Prefuse73/Dabrye techniques that absolutely involve dusty kicks. Another instance of BUG-B18 (style_tactics/technique_card disconnected from memory store).

---

### Additional findings (wave 8 — wonder mode + hook dev + gesture + action ledger + MIDI I/O + fabric eval)

**Biggest positive finding — `enter_wonder_mode` produces excellent output.** Session ID ws_b3ce483b9b9f returned 3 variants (strong/safe/unexpected) each with:
- Full compiled_plan (5-8 steps with verify_after)
- Populated what_changed (e.g., "Targets energy (+0.4), width (+0.3), contrast (+0.3)")
- Score + score_breakdown (taste/identity/novelty/coherence)
- distinctness_reason per variant ("Different family: sound_design")
- Warnings when devices are missing ("No Saturator on Pad Lush — using volume+reverb for warmth")

This is what `create_preview_set` SHOULD be producing. The shared variant-builder has bugs in the preview_set path (B44, B45) but works correctly in wonder_mode (B53 — cross-tool inconsistency).

**Cleanup confirmed:** `discard_wonder_session(ws_b3ce483b9b9f)` returns `{"discarded": true, "thread_still_open": true}` — the creative thread `ecb79c394a` stays open by design (per the tool description: "the problem isn't solved").

**Working correctly in wave 8 (strong signals):**
- ✅ `enter_wonder_mode` — rich diagnosis + 3 quality variants with compiled plans
- ✅ `develop_hook(hook_id="track_...", mode="variation")` — 4 concrete tactics: transpose, invert/retrograde, rhythmic displacement, fragmentation (BUG-B31 is specifically about the empty-hook_id path, not the general tool)
- ✅ `measure_hook_salience(hook_id)` — structured scoring with interpretation
- ✅ `plan_gesture(intent="reveal", target_tracks=[9], start_bar=16)` — proper gesture plan with curve_family (exponential), direction (up), parameter_hints (filter_cutoff, send_level, utility_width)
- ✅ `apply_gesture_template("pre_arrival_vacuum")` — returns 2 nested gestures (inhale bars 36-39, release bars 40-41) with all fields populated
- ✅ `resume_last_intent` — correctly finds the wonder thread I just opened
- ✅ `get_turn_budget(mode="improve")` — returns 6 resource pools (latency, risk, novelty, changes, undos, research) with proper defaults
- ✅ `get_recent_actions(limit=20)` — proper ledger with 20 entries showing my probe history; some marked `"ok": false, "error": "INVALID_PARAM"` for my probes of empty clip slots (expected)
- ✅ `get_last_move` returns `{}` when no moves in ledger (honest empty)
- ✅ `get_session_memory` returns empty entries list (no session memory yet)
- ✅ `evaluate_with_fabric(engine="sonic")` — score 0.6304, keep_change=true, goal_progress 0.014, measured deltas per dimension, memory_candidate=true
- ✅ `export_clip_midi` — wrote 6 notes, 30 beats, tempo 119 to disk (despite BUG-B52 filename path issue)
- ✅ `discard_wonder_session` — clean cleanup with thread preservation

**Per-track sound design wrap-up:**
- Track 2 Congas: 3 issues (no_modulation_sources, too_few_blocks, no_modulation — stacked flags for same cause)
- Track 5 Snare Rim: 2 issues (too_few_blocks + no_modulation — same BUG-B35 pattern — critics don't understand simple drums are supposed to be simple)

---

### Additional findings (wave 9 — arrangement reads + reference comparisons + taste/ranking + memory ops + display values)

**This was a green wave.** Most tools probed work correctly. The single new bug (B54) is a cascade of B17 (distill_reference_principles returning empty), which causes the entire reference-engine chain to silently degrade.

**Standout positive findings (deep confirmation):**
- ✅ **`get_display_values` is an excellent debugging tool** — on Analog synth it returned all 172 parameters with human-readable strings:
  - `"F1 Freq": "193 Hz"` (filter freq in actual Hz)
  - `"AMP1 Level": "-7.7 dB"` (level in dB)
  - `"OSC1 Shape": "Saw"` (enum name instead of index)
  - `"OSC1 Octave": "-1"` (signed int)
  - `"LFO1 Speed": "0.4 Hz"` (frequency)
  - `"FEG1 Attack": "7 ms"` (time in ms)
  - For Saturator: `"Drive": "2.0 dB"`, `"Type": "Analog Clip"`, `"Dry/Wet": "30 %"`
  - This is **exactly what's needed to close BUG-B4 and BUG-B9** — the display_value strings show actual units. Tools that set parameters should always read value_string back after setting, not rely on raw 0-1 normalization.
- ✅ **`get_scene_matrix` returns the full session grid** (10 tracks × 8 scenes with clip states, names, colors) — complete structural overview
- ✅ **`memory_get(a50d7cc1-...)` returns the FULL Dabrye Core template** I saved — qualities + payload + track_roles + scenes + creative_moves_applied + pending_manual_steps. Perfect round-trip.
- ✅ **`memory_favorite` works** — marked bug tracker as `favorite: true, rating: 5`, updated_at advanced
- ✅ **`explain_preference_vs_identity`** produces rich breakdown: taste_score 0.96 + identity_score 0.7 + composite 0.791 + recommendation + tension explanation + weight notes (0.65 identity / 0.35 taste)
- ✅ **`rank_by_taste_and_identity`** — 3 candidates ranked with composite + per-score explanations + per-candidate recommendation ("recommended" vs "consider")
- ✅ **`rank_moves_by_taste`** — ranks 3 moves by taste_score with full metadata preserved
- ✅ **`evaluate_mix_move`** — PROPERLY enforced hard rule: rejected my test because measurable delta on "punch" was -0.0389 (worse). `hard_rule_failures: ["HARD RULE: measurable delta <= 0"]`, `keep_change: false`, `decision_mode: "measured_reject"`. This is safety-critical logic working correctly.
- ✅ **`compare_to_reference`** (offline, no Ableton needed) — returns proper LUFS deltas, centroid deltas, band_deltas, stereo_width
- ✅ **`get_arrangement_notes`** returns arrangement-view MIDI data (6 notes in Pad Lush Intro Wash arrangement clip, pitches 50/53/57/60 = D-F-A-C — same material as session clip, confirmed)
- ✅ **`get_plugin_parameters`, `get_plugin_presets`** correctly ERROR when called on non-plugin devices with clear error messages: *"Device is InstrumentVector, not a plugin... Check get_device_info().is_plugin first"*
- ✅ **`get_warp_markers`** for the vocal audio clip — returns 2 markers at (beat 0, sample 0) and (beat 32.03, sample 22.35) — confirming the Ableton warp maths (22.35s × 86 BPM/60 = 32.03 beats, tempo-matched to 32-beat clip at 90 BPM session)
- ✅ **`get_freeze_status`** — simple boolean query works
- ✅ **`get_taste_dimensions`** — returns 8 structured dimensions (transition_boldness, automation_density, dryness_preference, harmonic_boldness, width_preference, native_vs_plugin, density_tolerance, fx_intensity) with evidence_count 0 on a fresh session

---

### Highest-leverage fixes (if we fix bugs next session)

1. **BUG-E1 + E2 (project_brain missing data)** — `project_brain` is supposed to be the canonical V2 engine state. Missing role+automation data silently degrades every engine that depends on it. Fixing these two gives the V2 orchestration layer its full information picture.
2. **BUG-B9 (Auto Filter Legacy scale)** — Can silently silence tracks when automation recipes assume 0-1 normalization on 20-135 or 0-30 scales. Real field risk.
3. **BUG-A2 / A3 (M4L bridge extensions)** — 30 minutes each, flips "wontfix" → "fixable" for Simpler Warp + Compressor sidechain routing.
4. **BUG-B5 + B2 (chord naming on partial chords)** — Same root-inference bug hit twice. One fix closes both.

---

## How to use this file across sessions

New session startup:
```bash
cat /Users/visansilviugeorge/Desktop/DREAM\ AI/LivePilot/BUGS.md
```

To tell a fresh Claude session to pick up where we left off:
> "Read BUGS.md in the LivePilot repo. Let's work through bug {X}." (e.g. BUG-A1, BUG-B1, BUG-D2)

When a bug is fixed, update the status flag to `🟢 fixed` and either move it to the resolved section at the bottom or keep inline for traceability. Add new bugs with incrementing IDs in their category.
